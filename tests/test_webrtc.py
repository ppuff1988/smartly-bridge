"""Tests for WebRTC Token management and views."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.smartly_bridge.auth import NonceCache
from custom_components.smartly_bridge.const import DOMAIN
from custom_components.smartly_bridge.webrtc import (
    WebRTCSession,
    WebRTCToken,
    WebRTCTokenManager,
    get_default_ice_servers,
    get_ice_servers_with_turn,
)

# ============================================================================
# WebRTCToken Tests
# ============================================================================


class TestWebRTCToken:
    """Tests for WebRTCToken dataclass."""

    def test_token_creation(self):
        """Test token creation with all fields."""
        now = time.time()
        token = WebRTCToken(
            token="test_token_123",
            entity_id="camera.front_door",
            client_id="test_client",
            created_at=now,
            expires_at=now + 300,
        )

        assert token.token == "test_token_123"
        assert token.entity_id == "camera.front_door"
        assert token.client_id == "test_client"
        assert token.created_at == now
        assert token.expires_at == now + 300

    def test_token_not_expired(self):
        """Test token is not expired when within TTL."""
        now = time.time()
        token = WebRTCToken(
            token="test_token",
            entity_id="camera.test",
            client_id="client",
            created_at=now,
            expires_at=now + 300,
        )

        assert not token.is_expired()

    def test_token_expired(self):
        """Test token is expired when past TTL."""
        now = time.time()
        token = WebRTCToken(
            token="test_token",
            entity_id="camera.test",
            client_id="client",
            created_at=now - 400,
            expires_at=now - 100,
        )

        assert token.is_expired()

    def test_remaining_seconds_positive(self):
        """Test remaining seconds when token is valid."""
        now = time.time()
        token = WebRTCToken(
            token="test_token",
            entity_id="camera.test",
            client_id="client",
            created_at=now,
            expires_at=now + 300,
        )

        remaining = token.remaining_seconds()
        assert 299 <= remaining <= 300

    def test_remaining_seconds_zero_when_expired(self):
        """Test remaining seconds is 0 when expired."""
        now = time.time()
        token = WebRTCToken(
            token="test_token",
            entity_id="camera.test",
            client_id="client",
            created_at=now - 400,
            expires_at=now - 100,
        )

        assert token.remaining_seconds() == 0

    def test_to_dict(self):
        """Test token serialization to dictionary."""
        now = time.time()
        token = WebRTCToken(
            token="test_token_xyz",
            entity_id="camera.living_room",
            client_id="client_123",
            created_at=now,
            expires_at=now + 300,
        )

        result = token.to_dict()

        assert result["token"] == "test_token_xyz"
        assert result["entity_id"] == "camera.living_room"
        assert result["expires_at"] == int(now + 300)
        assert 299 <= result["expires_in"] <= 300


# ============================================================================
# WebRTCSession Tests
# ============================================================================


class TestWebRTCSession:
    """Tests for WebRTCSession dataclass."""

    def test_session_creation(self):
        """Test session creation with defaults."""
        session = WebRTCSession(
            token="session_token",
            entity_id="camera.garage",
            client_id="client_abc",
        )

        assert session.token == "session_token"
        assert session.entity_id == "camera.garage"
        assert session.client_id == "client_abc"
        assert session.state == "new"
        assert session.local_sdp is None
        assert session.remote_sdp is None
        assert session.ice_candidates == []

    def test_session_touch_updates_activity(self):
        """Test that touch() updates last_activity."""
        session = WebRTCSession(
            token="token",
            entity_id="camera.test",
            client_id="client",
        )
        original_activity = session.last_activity

        time.sleep(0.01)
        session.touch()

        assert session.last_activity > original_activity

    def test_session_not_idle(self):
        """Test session is not idle when recently active."""
        session = WebRTCSession(
            token="token",
            entity_id="camera.test",
            client_id="client",
        )

        assert not session.is_idle(timeout=600)

    def test_session_idle(self):
        """Test session is idle when inactive for too long."""
        session = WebRTCSession(
            token="token",
            entity_id="camera.test",
            client_id="client",
        )
        session.last_activity = time.time() - 700  # 700 seconds ago

        assert session.is_idle(timeout=600)

    def test_add_ice_candidate(self):
        """Test adding ICE candidates."""
        session = WebRTCSession(
            token="token",
            entity_id="camera.test",
            client_id="client",
        )

        candidate = {
            "candidate": "candidate:123 1 udp 2130706431 192.168.1.1 54321 typ host",
            "sdpMid": "0",
            "sdpMLineIndex": 0,
        }

        session.add_ice_candidate(candidate)

        assert len(session.ice_candidates) == 1
        assert session.ice_candidates[0] == candidate

    def test_to_dict(self):
        """Test session serialization."""
        session = WebRTCSession(
            token="abcdefghijklmnop_extra",
            entity_id="camera.backyard",
            client_id="client_xyz",
        )
        session.state = "connected"

        result = session.to_dict()

        assert result["session_id"] == "abcdefghijklmnop"  # First 16 chars
        assert result["entity_id"] == "camera.backyard"
        assert result["state"] == "connected"
        assert "created_at" in result
        assert "last_activity" in result


# ============================================================================
# WebRTCTokenManager Tests
# ============================================================================


class TestWebRTCTokenManager:
    """Tests for WebRTCTokenManager."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        return hass

    @pytest.fixture
    async def token_manager(self, mock_hass):
        """Create a token manager for testing."""
        manager = WebRTCTokenManager(mock_hass, token_ttl=300, session_timeout=600)
        await manager.start()
        yield manager
        await manager.stop()

    @pytest.mark.asyncio
    async def test_start_stop(self, mock_hass):
        """Test manager start and stop."""
        manager = WebRTCTokenManager(mock_hass)

        await manager.start()
        assert manager._cleanup_task is not None

        await manager.stop()
        assert manager._cleanup_task is None

    @pytest.mark.asyncio
    async def test_generate_token(self, token_manager):
        """Test token generation."""
        token = await token_manager.generate_token(
            entity_id="camera.front_door",
            client_id="test_client",
        )

        assert token.token is not None
        assert len(token.token) > 20  # URL-safe base64, at least 32 bytes
        assert token.entity_id == "camera.front_door"
        assert token.client_id == "test_client"
        assert not token.is_expired()

    @pytest.mark.asyncio
    async def test_validate_token_success(self, token_manager):
        """Test successful token validation."""
        token = await token_manager.generate_token(
            entity_id="camera.test",
            client_id="client",
        )

        validated = await token_manager.validate_token(token.token)

        assert validated is not None
        assert validated.token == token.token

    @pytest.mark.asyncio
    async def test_validate_token_not_found(self, token_manager):
        """Test validation of non-existent token."""
        result = await token_manager.validate_token("non_existent_token")
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_token_expired(self, mock_hass):
        """Test validation of expired token."""
        manager = WebRTCTokenManager(mock_hass, token_ttl=1)  # 1 second TTL
        await manager.start()

        token = await manager.generate_token(
            entity_id="camera.test",
            client_id="client",
        )

        await asyncio.sleep(1.1)  # Wait for expiration

        result = await manager.validate_token(token.token)
        assert result is None

        await manager.stop()

    @pytest.mark.asyncio
    async def test_validate_token_entity_mismatch(self, token_manager):
        """Test validation with wrong entity_id."""
        token = await token_manager.generate_token(
            entity_id="camera.front_door",
            client_id="client",
        )

        result = await token_manager.validate_token(
            token.token,
            entity_id="camera.back_door",  # Wrong entity
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_consume_token_creates_session(self, token_manager):
        """Test that consuming token creates session."""
        token = await token_manager.generate_token(
            entity_id="camera.garage",
            client_id="client_123",
        )

        session = await token_manager.consume_token(token.token)

        assert session is not None
        assert session.entity_id == "camera.garage"
        assert session.client_id == "client_123"
        assert session.state == "new"

    @pytest.mark.asyncio
    async def test_consume_token_removes_token(self, token_manager):
        """Test that consumed token cannot be reused."""
        token = await token_manager.generate_token(
            entity_id="camera.test",
            client_id="client",
        )

        # First consumption should succeed
        session = await token_manager.consume_token(token.token)
        assert session is not None

        # Second consumption should fail
        session2 = await token_manager.consume_token(token.token)
        assert session2 is None

    @pytest.mark.asyncio
    async def test_consume_token_entity_verification(self, token_manager):
        """Test entity verification during consumption."""
        token = await token_manager.generate_token(
            entity_id="camera.front",
            client_id="client",
        )

        # Wrong entity should fail
        session = await token_manager.consume_token(
            token.token,
            entity_id="camera.back",
        )
        assert session is None

        # Token should still be valid (not consumed due to mismatch)
        session2 = await token_manager.consume_token(
            token.token,
            entity_id="camera.front",  # Correct entity
        )
        assert session2 is not None

    @pytest.mark.asyncio
    async def test_get_session(self, token_manager):
        """Test getting session by token."""
        token = await token_manager.generate_token(
            entity_id="camera.test",
            client_id="client",
        )
        await token_manager.consume_token(token.token)

        session = token_manager.get_session(token.token)

        assert session is not None
        assert session.entity_id == "camera.test"

    @pytest.mark.asyncio
    async def test_get_session_by_partial_token(self, token_manager):
        """Test getting session by partial token (session_id)."""
        token = await token_manager.generate_token(
            entity_id="camera.test",
            client_id="client",
        )
        await token_manager.consume_token(token.token)

        partial = token.token[:16]
        session = token_manager.get_session_by_partial_token(partial)

        assert session is not None
        assert session.entity_id == "camera.test"

    @pytest.mark.asyncio
    async def test_update_session_state(self, token_manager):
        """Test updating session state."""
        token = await token_manager.generate_token(
            entity_id="camera.test",
            client_id="client",
        )
        await token_manager.consume_token(token.token)

        updated = await token_manager.update_session_state(
            token_str=token.token,
            state="connecting",
            remote_sdp="v=0\r\n...",
        )

        assert updated is not None
        assert updated.state == "connecting"
        assert updated.remote_sdp == "v=0\r\n..."

    @pytest.mark.asyncio
    async def test_close_session(self, token_manager):
        """Test closing a session."""
        token = await token_manager.generate_token(
            entity_id="camera.test",
            client_id="client",
        )
        await token_manager.consume_token(token.token)

        result = await token_manager.close_session(token.token)

        assert result is True
        assert token_manager.get_session(token.token) is None

    @pytest.mark.asyncio
    async def test_close_nonexistent_session(self, token_manager):
        """Test closing a non-existent session."""
        result = await token_manager.close_session("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_stats(self, token_manager):
        """Test getting manager statistics."""
        # Create some tokens and sessions
        token1 = await token_manager.generate_token("camera.1", "client")
        await token_manager.generate_token("camera.2", "client")  # token2 for stats count
        await token_manager.consume_token(token1.token)

        stats = token_manager.get_stats()

        assert stats["active_tokens"] == 1  # token2 is still active
        assert stats["active_sessions"] == 1  # token1 was consumed
        assert stats["token_ttl"] == 300
        assert stats["session_timeout"] == 600

    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens(self, mock_hass):
        """Test cleanup of expired tokens."""
        manager = WebRTCTokenManager(mock_hass, token_ttl=1)
        await manager.start()

        token = await manager.generate_token("camera.test", "client")

        await asyncio.sleep(1.5)
        await manager._cleanup()

        assert await manager.validate_token(token.token) is None

        await manager.stop()

    @pytest.mark.asyncio
    async def test_cleanup_idle_sessions(self, mock_hass):
        """Test cleanup of idle sessions."""
        manager = WebRTCTokenManager(mock_hass, session_timeout=1)
        await manager.start()

        token = await manager.generate_token("camera.test", "client")
        session = await manager.consume_token(token.token)
        session.last_activity = time.time() - 2  # Simulate idle

        await manager._cleanup()

        assert manager.get_session(token.token) is None

        await manager.stop()


# ============================================================================
# ICE Servers Tests
# ============================================================================


class TestICEServers:
    """Tests for ICE server configuration."""

    def test_get_default_ice_servers(self):
        """Test default ICE servers include STUN."""
        servers = get_default_ice_servers()

        assert len(servers) >= 1
        assert any("stun:" in s["urls"] for s in servers)

    def test_get_ice_servers_with_turn(self):
        """Test ICE servers with TURN configuration."""
        servers = get_ice_servers_with_turn(
            turn_url="turn:turn.example.com:3478",
            turn_username="user",
            turn_credential="pass",
        )

        # Should have STUN servers plus TURN
        assert len(servers) >= 2

        # Find TURN server
        turn_server = next((s for s in servers if "turn:" in s.get("urls", "")), None)
        assert turn_server is not None
        assert turn_server["username"] == "user"
        assert turn_server["credential"] == "pass"

    def test_get_ice_servers_without_turn(self):
        """Test ICE servers without TURN (incomplete config)."""
        servers = get_ice_servers_with_turn(
            turn_url="turn:turn.example.com:3478",
            turn_username=None,  # Missing credentials
            turn_credential=None,
        )

        # Should only have STUN servers
        turn_servers = [s for s in servers if "turn:" in s.get("urls", "")]
        assert len(turn_servers) == 0


# ============================================================================
# WebRTC Views Tests
# ============================================================================


class TestWebRTCViews:
    """Tests for WebRTC HTTP views."""

    @pytest.fixture
    def mock_hass_with_webrtc(self):
        """Create mock hass with WebRTC manager."""
        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret_key_for_hmac_signing",
                        "allowed_cidrs": "10.0.0.0/8",
                        "trust_proxy": "never",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": MagicMock(check=AsyncMock(return_value=True)),
                "webrtc_manager": MagicMock(),
            }
        }
        hass.states = MagicMock()
        hass.states.get = MagicMock(return_value=MagicMock(attributes={}))
        return hass

    def _create_hmac_headers(
        self,
        method: str,
        path: str,
        body: bytes = b"{}",
        secret: str = "test_secret_key_for_hmac_signing",
    ) -> dict[str, str]:
        """Create HMAC authentication headers."""
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())

        body_hash = hashlib.sha256(body).hexdigest()
        message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
        signature = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "X-Client-Id": "test_client",
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": signature,
        }

    @pytest.mark.asyncio
    async def test_token_view_invalid_entity_id(self, mock_hass_with_webrtc):
        """Test token request with invalid entity ID."""
        from custom_components.smartly_bridge.views.webrtc import SmartlyWebRTCTokenView

        request = MagicMock()
        request.match_info = {"entity_id": "light.invalid"}  # Not a camera
        request.app = {"hass": mock_hass_with_webrtc}

        view = SmartlyWebRTCTokenView(request)
        response = await view.post()

        # Check it's a bad request response
        assert response.status == 400

    @pytest.mark.asyncio
    async def test_token_view_missing_entity(self, mock_hass_with_webrtc):
        """Test token request with empty entity ID."""
        from custom_components.smartly_bridge.views.webrtc import SmartlyWebRTCTokenView

        request = MagicMock()
        request.match_info = {"entity_id": ""}
        request.app = {"hass": mock_hass_with_webrtc}

        view = SmartlyWebRTCTokenView(request)
        response = await view.post()

        assert response.status == 400


# ============================================================================
# Integration Tests
# ============================================================================


class TestWebRTCIntegration:
    """Integration tests for WebRTC flow."""

    @pytest.mark.asyncio
    async def test_full_webrtc_flow(self):
        """Test complete WebRTC token -> session -> hangup flow."""
        hass = MagicMock()
        manager = WebRTCTokenManager(hass)
        await manager.start()

        # 1. Generate token
        token = await manager.generate_token(
            entity_id="camera.front_door",
            client_id="platform_client",
        )
        assert token.token is not None
        assert not token.is_expired()

        # 2. Validate token (Platform would do this before consuming)
        validated = await manager.validate_token(token.token, "camera.front_door")
        assert validated is not None

        # 3. Consume token to create session
        session = await manager.consume_token(token.token)
        assert session is not None
        assert session.state == "new"

        # 4. Update session with SDP
        updated = await manager.update_session_state(
            token_str=session.token,
            state="connecting",
            remote_sdp="v=0\r\no=- 123 456 IN IP4 127.0.0.1\r\n...",
        )
        assert updated.state == "connecting"
        assert updated.remote_sdp is not None

        # 5. Add ICE candidates
        session.add_ice_candidate(
            {
                "candidate": "candidate:1 1 UDP 2130706431 192.168.1.1 54321 typ host",
                "sdpMid": "0",
                "sdpMLineIndex": 0,
            }
        )
        assert len(session.ice_candidates) == 1

        # 6. Mark as connected
        await manager.update_session_state(
            token_str=session.token,
            state="connected",
            local_sdp="v=0\r\n...",
        )

        # 7. Close session
        result = await manager.close_session(session.token)
        assert result is True
        assert manager.get_session(session.token) is None

        await manager.stop()

    @pytest.mark.asyncio
    async def test_concurrent_token_generation(self):
        """Test concurrent token generation is safe."""
        hass = MagicMock()
        manager = WebRTCTokenManager(hass)
        await manager.start()

        # Generate 100 tokens concurrently
        tasks = [manager.generate_token(f"camera.cam_{i}", f"client_{i}") for i in range(100)]

        tokens = await asyncio.gather(*tasks)

        # All tokens should be unique
        token_strings = [t.token for t in tokens]
        assert len(set(token_strings)) == 100

        await manager.stop()

    @pytest.mark.asyncio
    async def test_token_cannot_be_reused_after_consumption(self):
        """Test token single-use enforcement."""
        hass = MagicMock()
        manager = WebRTCTokenManager(hass)
        await manager.start()

        token = await manager.generate_token("camera.test", "client")

        # First consumption succeeds
        session1 = await manager.consume_token(token.token)
        assert session1 is not None

        # Second consumption fails
        session2 = await manager.consume_token(token.token)
        assert session2 is None

        # Validation also fails (token is gone)
        validated = await manager.validate_token(token.token)
        assert validated is None

        await manager.stop()


# ============================================================================
# TURN Server Configuration Tests
# ============================================================================


class TestTURNConfiguration:
    """Tests for TURN server configuration integration."""

    @pytest.mark.asyncio
    async def test_ice_servers_with_turn_from_config(self):
        """Test ICE servers generation from config with TURN settings."""
        # Generate ICE servers with TURN
        ice_servers = get_ice_servers_with_turn(
            turn_url="turn:turn.example.com:3478",
            turn_username="testuser",
            turn_credential="testpass",
        )

        # Should have STUN servers + TURN server
        assert len(ice_servers) == 4
        assert ice_servers[0]["urls"] == "stun:stun.l.google.com:19302"
        assert ice_servers[3]["urls"] == "turn:turn.example.com:3478"
        assert ice_servers[3]["username"] == "testuser"
        assert ice_servers[3]["credential"] == "testpass"

    @pytest.mark.asyncio
    async def test_ice_servers_without_turn_from_config(self):
        """Test ICE servers generation when TURN is not configured."""
        # Generate ICE servers (should only return STUN)
        ice_servers = get_ice_servers_with_turn(
            turn_url="",
            turn_username="",
            turn_credential="",
        )

        # Should only have STUN servers
        assert len(ice_servers) == 3
        assert all("stun" in server["urls"] for server in ice_servers)

    @pytest.mark.asyncio
    async def test_partial_turn_config_ignored(self):
        """Test that incomplete TURN config is ignored safely."""
        # Missing credential
        ice_servers = get_ice_servers_with_turn(
            turn_url="turn:turn.example.com:3478",
            turn_username="testuser",
            turn_credential=None,
        )
        assert len(ice_servers) == 3  # Only STUN servers

        # Missing username
        ice_servers = get_ice_servers_with_turn(
            turn_url="turn:turn.example.com:3478",
            turn_username=None,
            turn_credential="testpass",
        )
        assert len(ice_servers) == 3

        # Missing URL
        ice_servers = get_ice_servers_with_turn(
            turn_url=None,
            turn_username="testuser",
            turn_credential="testpass",
        )
        assert len(ice_servers) == 3
