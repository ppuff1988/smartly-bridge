"""Authentication and HMAC signature handling for Smartly Bridge."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from aiohttp import web

from .const import (
    HEADER_CLIENT_ID,
    HEADER_HA_INSTANCE_ID,
    HEADER_NONCE,
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
    NONCE_TTL,
    TIMESTAMP_TOLERANCE,
)

if TYPE_CHECKING:
    pass


@dataclass
class AuthResult:
    """Result of authentication check."""

    success: bool
    error: str | None = None
    client_id: str | None = None


class NonceCache:
    """In-memory nonce cache with TTL-based expiration."""

    def __init__(self, ttl: int = NONCE_TTL) -> None:
        """Initialize the nonce cache."""
        self._cache: dict[str, float] = {}
        self._ttl = ttl
        self._cleanup_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the cleanup task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def check_and_add(self, nonce: str) -> bool:
        """Check if nonce exists, add if not. Returns True if nonce is new."""
        async with self._lock:
            now = time.time()
            if nonce in self._cache:
                return False  # Nonce already used (replay attack)
            self._cache[nonce] = now
            return True

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired nonces."""
        while True:
            await asyncio.sleep(60)  # Run cleanup every minute
            await self._cleanup()

    async def _cleanup(self) -> None:
        """Remove expired nonces."""
        async with self._lock:
            now = time.time()
            expired = [k for k, v in self._cache.items() if now - v > self._ttl]
            for key in expired:
                del self._cache[key]


class RateLimiter:
    """Sliding window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        """Initialize the rate limiter."""
        self._max_requests = max_requests
        self._window = window_seconds
        self._requests: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, client_id: str) -> bool:
        """Check if request is allowed. Returns True if allowed."""
        async with self._lock:
            now = time.time()
            window_start = now - self._window

            # Get or create request list for client
            if client_id not in self._requests:
                self._requests[client_id] = []

            # Remove old requests outside the window
            self._requests[client_id] = [t for t in self._requests[client_id] if t > window_start]

            # Check if under limit
            if len(self._requests[client_id]) >= self._max_requests:
                return False

            # Add current request
            self._requests[client_id].append(now)
            return True

    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests in current window."""
        now = time.time()
        window_start = now - self._window

        if client_id not in self._requests:
            return self._max_requests

        current = [t for t in self._requests[client_id] if t > window_start]
        return max(0, self._max_requests - len(current))


def compute_signature(
    secret: str,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> str:
    """Compute HMAC-SHA256 signature."""
    body_hash = hashlib.sha256(body).hexdigest()
    message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
    signature = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return signature


def verify_signature(
    secret: str,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes,
    provided_signature: str,
) -> bool:
    """Verify HMAC-SHA256 signature using constant-time comparison."""
    expected = compute_signature(secret, method, path, timestamp, nonce, body)
    return hmac.compare_digest(expected, provided_signature)


def check_timestamp(timestamp_str: str, tolerance: int = TIMESTAMP_TOLERANCE) -> bool:
    """Check if timestamp is within acceptable range."""
    try:
        timestamp = int(timestamp_str)
        now = int(time.time())
        return abs(now - timestamp) <= tolerance
    except (ValueError, TypeError):
        return False


def check_ip(
    client_ip: str,
    allowed_cidrs: str,
) -> bool:
    """Check if client IP is in allowed CIDR ranges."""
    if not allowed_cidrs or not allowed_cidrs.strip():
        return True  # No restriction if empty

    try:
        ip = ipaddress.ip_address(client_ip)
        cidrs = [c.strip() for c in allowed_cidrs.split(",") if c.strip()]

        for cidr in cidrs:
            try:
                network = ipaddress.ip_network(cidr, strict=False)
                if ip in network:
                    return True
            except ValueError:
                continue

        return False
    except ValueError:
        return False


def get_client_ip(request: web.Request) -> str:
    """Get client IP from request, considering X-Forwarded-For."""
    # Check X-Forwarded-For header first (for reverse proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain
        return forwarded.split(",")[0].strip()

    # Fall back to direct connection
    if request.transport:
        peername = request.transport.get_extra_info("peername")
        if peername:
            return peername[0]

    return ""


async def verify_request(
    request: web.Request,
    client_secret: str,
    nonce_cache: NonceCache,
    allowed_cidrs: str,
) -> AuthResult:
    """Verify incoming request authentication."""
    # Check IP
    client_ip = get_client_ip(request)
    if not check_ip(client_ip, allowed_cidrs):
        return AuthResult(success=False, error="ip_not_allowed")

    # Get headers
    client_id = request.headers.get(HEADER_CLIENT_ID)
    timestamp = request.headers.get(HEADER_TIMESTAMP)
    nonce = request.headers.get(HEADER_NONCE)
    signature = request.headers.get(HEADER_SIGNATURE)

    if not all([client_id, timestamp, nonce, signature]):
        return AuthResult(success=False, error="missing_headers")

    # Check timestamp
    if not check_timestamp(timestamp):
        return AuthResult(success=False, error="invalid_timestamp")

    # Check nonce
    if not await nonce_cache.check_and_add(nonce):
        return AuthResult(success=False, error="nonce_reused")

    # Read body
    body = await request.read()

    # Verify signature
    if not verify_signature(
        client_secret,
        request.method,
        request.path,
        timestamp,
        nonce,
        body,
        signature,
    ):
        return AuthResult(success=False, error="invalid_signature")

    return AuthResult(success=True, client_id=client_id)


def sign_outgoing_request(
    secret: str,
    instance_id: str,
    body: bytes,
    client_id: str = "",
    path: str = "/webhook/ha-event",
) -> dict[str, str]:
    """Generate headers for outgoing request to Platform.

    Args:
        secret: Client secret for HMAC signature
        instance_id: Home Assistant instance ID
        body: Request body bytes
        client_id: Client ID for authentication
        path: URL path without query string and without trailing slash
    """
    timestamp = str(int(time.time()))
    nonce = str(uuid.uuid4())

    signature = compute_signature(
        secret,
        "POST",
        path,
        timestamp,
        nonce,
        body,
    )

    headers = {
        HEADER_TIMESTAMP: timestamp,
        HEADER_NONCE: nonce,
        HEADER_SIGNATURE: signature,
        HEADER_HA_INSTANCE_ID: instance_id,
        "Content-Type": "application/json",
    }

    # Add X-Client-Id if provided
    if client_id:
        headers[HEADER_CLIENT_ID] = client_id

    return headers
