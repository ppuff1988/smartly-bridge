"""WebRTC Token management and signaling for Smartly Bridge.

This module provides secure token-based authentication for WebRTC
P2P connections, allowing Platform to establish direct video streams
with cameras without continuous HMAC overhead.

Flow:
1. Platform requests token via HMAC-authenticated endpoint
2. Token is returned with 5-minute validity
3. Platform uses token to initiate WebRTC signaling
4. P2P connection established for video streaming
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .const import (
    WEBRTC_SESSION_TIMEOUT,
    WEBRTC_TOKEN_BYTES,
    WEBRTC_TOKEN_TTL,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class WebRTCToken:
    """WebRTC session token.

    Attributes:
        token: The secure random token string.
        entity_id: Camera entity ID this token is valid for.
        client_id: The authenticated client ID that requested the token.
        created_at: Unix timestamp when token was created.
        expires_at: Unix timestamp when token expires.
    """

    token: str
    entity_id: str
    client_id: str
    created_at: float
    expires_at: float

    def is_expired(self) -> bool:
        """Check if token has expired."""
        return time.time() > self.expires_at

    def remaining_seconds(self) -> int:
        """Get remaining valid seconds."""
        return max(0, int(self.expires_at - time.time()))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "token": self.token,
            "entity_id": self.entity_id,
            "expires_at": int(self.expires_at),
            "expires_in": self.remaining_seconds(),
        }


@dataclass
class WebRTCSession:
    """Active WebRTC session.

    Represents an ongoing WebRTC connection between Platform and
    a camera entity.

    Attributes:
        token: The token used to create this session.
        entity_id: Camera entity ID.
        client_id: The authenticated client ID.
        created_at: Unix timestamp when session was created.
        last_activity: Unix timestamp of last activity.
        state: Current session state (new, connecting, connected, disconnected).
        local_sdp: Local SDP answer.
        remote_sdp: Remote SDP offer from client.
        ice_candidates: List of ICE candidates.
    """

    token: str
    entity_id: str
    client_id: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    state: str = "new"  # new, connecting, connected, disconnected
    local_sdp: str | None = None
    remote_sdp: str | None = None
    ice_candidates: list[dict[str, Any]] = field(default_factory=list)

    def touch(self) -> None:
        """Update last activity time."""
        self.last_activity = time.time()

    def is_idle(self, timeout: float = WEBRTC_SESSION_TIMEOUT) -> bool:
        """Check if session has been idle too long."""
        return time.time() - self.last_activity > timeout

    def add_ice_candidate(self, candidate: dict[str, Any]) -> None:
        """Add an ICE candidate to the session."""
        self.ice_candidates.append(candidate)
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "session_id": self.token[:16],  # Partial token for reference
            "entity_id": self.entity_id,
            "state": self.state,
            "created_at": int(self.created_at),
            "last_activity": int(self.last_activity),
        }


class WebRTCTokenManager:
    """Manager for WebRTC tokens and sessions.

    Handles token generation, validation, and session lifecycle.
    Tokens are single-use and expire after a configurable TTL.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        token_ttl: int = WEBRTC_TOKEN_TTL,
        session_timeout: int = WEBRTC_SESSION_TIMEOUT,
    ) -> None:
        """Initialize the token manager.

        Args:
            hass: Home Assistant instance.
            token_ttl: Token validity period in seconds.
            session_timeout: Session idle timeout in seconds.
        """
        self.hass = hass
        self._token_ttl = token_ttl
        self._session_timeout = session_timeout
        self._tokens: dict[str, WebRTCToken] = {}
        self._sessions: dict[str, WebRTCSession] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the token manager cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        _LOGGER.info("WebRTC token manager started")

    async def stop(self) -> None:
        """Stop the token manager and cleanup all sessions."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        # Clean up all sessions
        async with self._lock:
            for session in list(self._sessions.values()):
                await self._close_session(session)
            self._sessions.clear()
            self._tokens.clear()

        _LOGGER.info("WebRTC token manager stopped")

    async def generate_token(
        self,
        entity_id: str,
        client_id: str,
    ) -> WebRTCToken:
        """Generate a new WebRTC token.

        Creates a secure random token that can be used to initiate
        a WebRTC session for the specified camera.

        Args:
            entity_id: Camera entity ID (e.g., 'camera.front_door').
            client_id: Authenticated client ID from HMAC verification.

        Returns:
            WebRTCToken with token string and expiration info.
        """
        async with self._lock:
            # Generate secure random token (256-bit)
            token_str = secrets.token_urlsafe(WEBRTC_TOKEN_BYTES)
            now = time.time()

            token = WebRTCToken(
                token=token_str,
                entity_id=entity_id,
                client_id=client_id,
                created_at=now,
                expires_at=now + self._token_ttl,
            )

            self._tokens[token_str] = token
            _LOGGER.debug(
                "Generated WebRTC token for %s (client: %s), expires in %ds",
                entity_id,
                client_id,
                self._token_ttl,
            )

            return token

    async def validate_token(
        self,
        token_str: str,
        entity_id: str | None = None,
    ) -> WebRTCToken | None:
        """Validate a WebRTC token without consuming it.

        Args:
            token_str: Token string to validate.
            entity_id: Optional entity ID to verify token is for correct camera.

        Returns:
            WebRTCToken if valid, None otherwise.
        """
        async with self._lock:
            token = self._tokens.get(token_str)

            if token is None:
                _LOGGER.debug("Token not found: %s...", token_str[:8])
                return None

            if token.is_expired():
                del self._tokens[token_str]
                _LOGGER.debug("Token expired: %s...", token_str[:8])
                return None

            if entity_id and token.entity_id != entity_id:
                _LOGGER.warning(
                    "Token entity mismatch: expected %s, got %s",
                    token.entity_id,
                    entity_id,
                )
                return None

            return token

    async def consume_token(
        self,
        token_str: str,
        entity_id: str | None = None,
    ) -> WebRTCSession | None:
        """Consume token and create session.

        Token can only be used once to create a session.
        After consumption, the token is removed and cannot be reused.

        Args:
            token_str: Token string.
            entity_id: Optional entity ID for verification.

        Returns:
            WebRTCSession if token is valid, None otherwise.
        """
        async with self._lock:
            token = self._tokens.pop(token_str, None)

            if token is None:
                _LOGGER.debug("Token not found for consumption: %s...", token_str[:8])
                return None

            if token.is_expired():
                _LOGGER.debug("Token expired during consumption: %s...", token_str[:8])
                return None

            if entity_id and token.entity_id != entity_id:
                _LOGGER.warning(
                    "Token entity mismatch during consumption: expected %s, got %s",
                    token.entity_id,
                    entity_id,
                )
                # Put token back since it wasn't consumed
                self._tokens[token_str] = token
                return None

            session = WebRTCSession(
                token=token_str,
                entity_id=token.entity_id,
                client_id=token.client_id,
            )

            self._sessions[token_str] = session
            _LOGGER.info(
                "Created WebRTC session for %s (client: %s)",
                token.entity_id,
                token.client_id,
            )

            return session

    def get_session(self, token_str: str) -> WebRTCSession | None:
        """Get existing session by token.

        Args:
            token_str: Token string used to create the session.

        Returns:
            WebRTCSession if found, None otherwise.
        """
        session = self._sessions.get(token_str)
        if session:
            session.touch()
        return session

    def get_session_by_partial_token(self, partial_token: str) -> WebRTCSession | None:
        """Get session by partial token (session_id).

        Args:
            partial_token: First 16 characters of the token.

        Returns:
            WebRTCSession if found, None otherwise.
        """
        for token_str, session in self._sessions.items():
            if token_str.startswith(partial_token):
                session.touch()
                return session
        return None

    async def update_session_state(
        self,
        token_str: str,
        state: str,
        local_sdp: str | None = None,
        remote_sdp: str | None = None,
    ) -> WebRTCSession | None:
        """Update session state and SDP.

        Args:
            token_str: Token string for the session.
            state: New session state.
            local_sdp: Local SDP answer (optional).
            remote_sdp: Remote SDP offer (optional).

        Returns:
            Updated WebRTCSession if found, None otherwise.
        """
        async with self._lock:
            session = self._sessions.get(token_str)
            if session is None:
                return None

            session.state = state
            if local_sdp is not None:
                session.local_sdp = local_sdp
            if remote_sdp is not None:
                session.remote_sdp = remote_sdp
            session.touch()

            _LOGGER.debug(
                "Updated session state for %s: %s",
                session.entity_id,
                state,
            )

            return session

    async def close_session(self, token_str: str) -> bool:
        """Close and remove a session.

        Args:
            token_str: Token string for the session to close.

        Returns:
            True if session was found and closed, False otherwise.
        """
        async with self._lock:
            session = self._sessions.pop(token_str, None)
            if session:
                await self._close_session(session)
                return True
            return False

    async def _close_session(self, session: WebRTCSession) -> None:
        """Internal session cleanup.

        Args:
            session: Session to clean up.
        """
        session.state = "disconnected"
        _LOGGER.info(
            "Closed WebRTC session for %s (client: %s)",
            session.entity_id,
            session.client_id,
        )

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired tokens and inactive sessions."""
        while True:
            await asyncio.sleep(60)
            await self._cleanup()

    async def _cleanup(self) -> None:
        """Remove expired tokens and inactive sessions."""
        async with self._lock:
            # Clean expired tokens
            expired_tokens = [k for k, v in self._tokens.items() if v.is_expired()]
            for token_str in expired_tokens:
                del self._tokens[token_str]

            # Clean inactive sessions
            inactive_sessions = [
                k for k, v in self._sessions.items() if v.is_idle(self._session_timeout)
            ]
            for token_str in inactive_sessions:
                session = self._sessions.pop(token_str)
                await self._close_session(session)

            if expired_tokens or inactive_sessions:
                _LOGGER.debug(
                    "Cleaned up %d expired tokens, %d inactive sessions",
                    len(expired_tokens),
                    len(inactive_sessions),
                )

    def get_stats(self) -> dict[str, Any]:
        """Get token manager statistics.

        Returns:
            Dictionary with token and session counts.
        """
        return {
            "active_tokens": len(self._tokens),
            "active_sessions": len(self._sessions),
            "token_ttl": self._token_ttl,
            "session_timeout": self._session_timeout,
        }


def get_default_ice_servers() -> list[dict[str, Any]]:
    """Get default ICE server configuration.

    Returns a list of public STUN servers for NAT traversal.
    For production deployments with strict NAT, consider adding
    TURN servers.

    Returns:
        List of ICE server configurations.
    """
    return [
        {"urls": "stun:stun.l.google.com:19302"},
        {"urls": "stun:stun1.l.google.com:19302"},
        {"urls": "stun:stun2.l.google.com:19302"},
    ]


def get_ice_servers_with_turn(
    turn_url: str | None = None,
    turn_username: str | None = None,
    turn_credential: str | None = None,
) -> list[dict[str, Any]]:
    """Get ICE servers including optional TURN server.

    Args:
        turn_url: TURN server URL (e.g., 'turn:turn.example.com:3478').
        turn_username: TURN authentication username.
        turn_credential: TURN authentication credential.

    Returns:
        List of ICE server configurations.
    """
    servers = get_default_ice_servers()

    if turn_url and turn_username and turn_credential:
        servers.append(
            {
                "urls": turn_url,
                "username": turn_username,
                "credential": turn_credential,
            }
        )

    return servers
