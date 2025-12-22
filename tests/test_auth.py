"""Tests for authentication module."""

from __future__ import annotations

import time

import pytest

from custom_components.smartly_bridge.auth import (
    NonceCache,
    RateLimiter,
    check_ip,
    check_timestamp,
    compute_signature,
    verify_signature,
)


class TestComputeSignature:
    """Tests for compute_signature function."""

    def test_compute_signature_basic(self):
        """Test basic signature computation."""
        secret = "test_secret"
        method = "POST"
        path = "/api/smartly/control"
        timestamp = "1700000000"
        nonce = "test-nonce-uuid"
        body = b'{"entity_id": "light.test"}'

        signature = compute_signature(secret, method, path, timestamp, nonce, body)

        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 hex digest length

    def test_compute_signature_deterministic(self):
        """Test that signature computation is deterministic."""
        args = ("secret", "POST", "/path", "123", "nonce", b"body")

        sig1 = compute_signature(*args)
        sig2 = compute_signature(*args)

        assert sig1 == sig2

    def test_compute_signature_different_inputs(self):
        """Test that different inputs produce different signatures."""
        base_args = ["secret", "POST", "/path", "123", "nonce", b"body"]

        signatures = set()
        for i, _ in enumerate(base_args):
            args = base_args.copy()
            args[i] = args[i] + "_modified" if isinstance(args[i], str) else args[i] + b"x"
            sig = compute_signature(*args)
            signatures.add(sig)

        # All signatures should be different
        assert len(signatures) == len(base_args)


class TestVerifySignature:
    """Tests for verify_signature function."""

    def test_verify_signature_valid(self):
        """Test verification of valid signature."""
        secret = "test_secret"
        method = "POST"
        path = "/api/smartly/control"
        timestamp = "1700000000"
        nonce = "test-nonce"
        body = b'{"test": "data"}'

        signature = compute_signature(secret, method, path, timestamp, nonce, body)

        assert verify_signature(secret, method, path, timestamp, nonce, body, signature) is True

    def test_verify_signature_invalid(self):
        """Test verification of invalid signature."""
        secret = "test_secret"
        method = "POST"
        path = "/api/smartly/control"
        timestamp = "1700000000"
        nonce = "test-nonce"
        body = b'{"test": "data"}'

        assert (
            verify_signature(secret, method, path, timestamp, nonce, body, "invalid_signature")
            is False
        )

    def test_verify_signature_wrong_secret(self):
        """Test verification fails with wrong secret."""
        method = "POST"
        path = "/api/smartly/control"
        timestamp = "1700000000"
        nonce = "test-nonce"
        body = b'{"test": "data"}'

        signature = compute_signature("secret1", method, path, timestamp, nonce, body)

        assert verify_signature("secret2", method, path, timestamp, nonce, body, signature) is False


class TestCheckTimestamp:
    """Tests for check_timestamp function."""

    def test_check_timestamp_valid(self):
        """Test valid timestamp within tolerance."""
        current_time = str(int(time.time()))
        assert check_timestamp(current_time) is True

    def test_check_timestamp_past_within_tolerance(self):
        """Test timestamp in past but within tolerance."""
        past_time = str(int(time.time()) - 15)  # 15 seconds ago
        assert check_timestamp(past_time, tolerance=30) is True

    def test_check_timestamp_future_within_tolerance(self):
        """Test timestamp in future but within tolerance."""
        future_time = str(int(time.time()) + 15)  # 15 seconds ahead
        assert check_timestamp(future_time, tolerance=30) is True

    def test_check_timestamp_too_old(self):
        """Test timestamp too old."""
        old_time = str(int(time.time()) - 60)  # 60 seconds ago
        assert check_timestamp(old_time, tolerance=30) is False

    def test_check_timestamp_too_future(self):
        """Test timestamp too far in future."""
        future_time = str(int(time.time()) + 60)  # 60 seconds ahead
        assert check_timestamp(future_time, tolerance=30) is False

    def test_check_timestamp_invalid_format(self):
        """Test invalid timestamp format."""
        assert check_timestamp("not_a_number") is False
        assert check_timestamp("") is False
        assert check_timestamp(None) is False


class TestCheckIp:
    """Tests for check_ip function."""

    def test_check_ip_empty_cidrs_allows_all(self):
        """Test that empty CIDR list allows all IPs."""
        assert check_ip("192.168.1.100", "") is True
        assert check_ip("10.0.0.1", "  ") is True
        assert check_ip("8.8.8.8", "") is True

    def test_check_ip_in_cidr(self):
        """Test IP within allowed CIDR."""
        assert check_ip("192.168.1.100", "192.168.0.0/16") is True
        assert check_ip("10.0.0.1", "10.0.0.0/8") is True
        assert check_ip("172.16.5.10", "172.16.0.0/12") is True

    def test_check_ip_not_in_cidr(self):
        """Test IP not within allowed CIDR."""
        assert check_ip("8.8.8.8", "192.168.0.0/16") is False
        assert check_ip("192.168.1.1", "10.0.0.0/8") is False

    def test_check_ip_multiple_cidrs(self):
        """Test IP against multiple CIDRs."""
        cidrs = "10.0.0.0/8,192.168.0.0/16,172.16.0.0/12"

        assert check_ip("10.1.2.3", cidrs) is True
        assert check_ip("192.168.100.1", cidrs) is True
        assert check_ip("172.20.1.1", cidrs) is True
        assert check_ip("8.8.8.8", cidrs) is False

    def test_check_ip_invalid_ip(self):
        """Test invalid IP address."""
        assert check_ip("not_an_ip", "10.0.0.0/8") is False
        assert check_ip("", "10.0.0.0/8") is False

    def test_check_ip_single_host(self):
        """Test single host CIDR (/32)."""
        assert check_ip("192.168.1.100", "192.168.1.100/32") is True
        assert check_ip("192.168.1.101", "192.168.1.100/32") is False


class TestNonceCache:
    """Tests for NonceCache class."""

    @pytest.mark.asyncio
    async def test_nonce_cache_add_new(self):
        """Test adding new nonce."""
        cache = NonceCache(ttl=60)

        result = await cache.check_and_add("nonce1")
        assert result is True

    @pytest.mark.asyncio
    async def test_nonce_cache_reject_duplicate(self):
        """Test rejecting duplicate nonce."""
        cache = NonceCache(ttl=60)

        await cache.check_and_add("nonce1")
        result = await cache.check_and_add("nonce1")

        assert result is False

    @pytest.mark.asyncio
    async def test_nonce_cache_different_nonces(self):
        """Test different nonces are accepted."""
        cache = NonceCache(ttl=60)

        assert await cache.check_and_add("nonce1") is True
        assert await cache.check_and_add("nonce2") is True
        assert await cache.check_and_add("nonce3") is True

    @pytest.mark.asyncio
    async def test_nonce_cache_start_stop(self):
        """Test starting and stopping cache cleanup."""
        cache = NonceCache(ttl=60)

        await cache.start()
        assert cache._cleanup_task is not None

        await cache.stop()
        assert cache._cleanup_task is None


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_within_limit(self):
        """Test requests within limit are allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        for _ in range(5):
            assert await limiter.check("client1") is True

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_over_limit(self):
        """Test requests over limit are blocked."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)

        # Use up the limit
        for _ in range(3):
            await limiter.check("client1")

        # Should be blocked
        assert await limiter.check("client1") is False

    @pytest.mark.asyncio
    async def test_rate_limiter_separate_clients(self):
        """Test rate limiting is per-client."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # Client 1 uses up limit
        await limiter.check("client1")
        await limiter.check("client1")
        assert await limiter.check("client1") is False

        # Client 2 should still have allowance
        assert await limiter.check("client2") is True

    @pytest.mark.asyncio
    async def test_rate_limiter_get_remaining(self):
        """Test getting remaining requests."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        assert limiter.get_remaining("client1") == 5

        await limiter.check("client1")
        await limiter.check("client1")

        assert limiter.get_remaining("client1") == 3
