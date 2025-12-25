"""Tests for HTTP API endpoints."""

from __future__ import annotations

import json
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.const import (
    API_PATH_CONTROL,
    API_PATH_SYNC,
    DOMAIN,
    HEADER_CLIENT_ID,
    HEADER_NONCE,
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
)


class TestControlEndpoint:
    """Tests for /api/smartly/control endpoint."""

    @pytest.mark.asyncio
    async def test_control_missing_headers(self):
        """Test control endpoint rejects request without auth headers."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.http import SmartlyControlView

        # Create mock request without headers
        request = MagicMock()
        request.headers = {}
        request.method = "POST"
        request.path = API_PATH_CONTROL
        request.app = {"hass": MagicMock()}
        request.read = AsyncMock(return_value=b"{}")

        # Setup hass.data
        hass = request.app["hass"]
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": RateLimiter(60, 60),
            }
        }

        view = SmartlyControlView(request)
        response = await view.post()

        assert response.status == 401

    @pytest.mark.asyncio
    async def test_control_invalid_signature(self):
        """Test control endpoint rejects invalid signature."""
        import time
        import uuid

        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.http import SmartlyControlView

        # Create mock request with invalid signature
        request = MagicMock()
        request.headers = {
            HEADER_CLIENT_ID: "test_client",
            HEADER_TIMESTAMP: str(int(time.time())),
            HEADER_NONCE: str(uuid.uuid4()),
            HEADER_SIGNATURE: "invalid_signature",
        }
        request.method = "POST"
        request.path = API_PATH_CONTROL
        request.app = {"hass": MagicMock()}
        request.read = AsyncMock(return_value=b"{}")
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)

        # Setup hass.data
        hass = request.app["hass"]
        nonce_cache = NonceCache()
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                    }
                ),
                "nonce_cache": nonce_cache,
                "rate_limiter": RateLimiter(60, 60),
            }
        }

        view = SmartlyControlView(request)
        response = await view.post()

        assert response.status == 401

    @pytest.mark.asyncio
    async def test_control_rate_limited(self):
        """Test control endpoint enforces rate limiting."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.http import SmartlyControlView

        # Create rate limiter that's exhausted
        rate_limiter = RateLimiter(max_requests=0, window_seconds=60)

        # Create mock request
        request = MagicMock()
        request.headers = {
            HEADER_CLIENT_ID: "test_client",
            HEADER_TIMESTAMP: "0",
            HEADER_NONCE: "nonce",
            HEADER_SIGNATURE: "sig",
        }
        request.method = "POST"
        request.path = API_PATH_CONTROL
        request.app = {"hass": MagicMock()}
        request.read = AsyncMock(return_value=b"{}")
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)

        # Setup hass.data with mock that passes auth
        hass = request.app["hass"]
        nonce_cache = NonceCache()
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                    }
                ),
                "nonce_cache": nonce_cache,
                "rate_limiter": rate_limiter,
            }
        }

        # Mock verify_request to return success
        with patch("custom_components.smartly_bridge.http.verify_request") as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client")

            view = SmartlyControlView(request)
            response = await view.post()

        assert response.status == 429


class TestSyncEndpoint:
    """Tests for /api/smartly/sync/structure endpoint."""

    @pytest.mark.asyncio
    async def test_sync_returns_structure(self):
        """Test sync endpoint returns floor/area/device/entity structure."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.http import SmartlySyncView

        # Create mock request
        request = MagicMock()
        request.headers = {
            HEADER_CLIENT_ID: "test_client",
        }
        request.method = "GET"
        request.path = API_PATH_SYNC
        request.app = {"hass": MagicMock()}
        request.read = AsyncMock(return_value=b"")
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)

        # Setup hass.data
        hass = request.app["hass"]
        nonce_cache = NonceCache()
        rate_limiter = RateLimiter(60, 60)

        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                    }
                ),
                "nonce_cache": nonce_cache,
                "rate_limiter": rate_limiter,
            }
        }

        # Mock verify_request and get_structure
        with (
            patch("custom_components.smartly_bridge.http.verify_request") as mock_verify,
            patch("custom_components.smartly_bridge.http.get_structure") as mock_structure,
        ):

            mock_verify.return_value = MagicMock(success=True, client_id="test_client")
            mock_structure.return_value = {
                "floors": [
                    {
                        "floor_id": "floor_1",
                        "name": "First Floor",
                        "icon": None,
                        "level": 1,
                    }
                ],
                "areas": [],
                "devices": [],
                "entities": [],
            }

            # Also mock the registry imports inside the get method
            with (
                patch("homeassistant.helpers.entity_registry.async_get"),
                patch("homeassistant.helpers.device_registry.async_get"),
                patch("homeassistant.helpers.area_registry.async_get"),
                patch("homeassistant.helpers.floor_registry.async_get"),
            ):

                view = SmartlySyncView(request)
                response = await view.get()

        assert response.status == 200
        body = json.loads(response.body)
        assert "floors" in body
        assert "areas" in body
        assert "devices" in body
        assert "entities" in body


class TestApiPaths:
    """Tests for API path constants."""

    def test_control_path(self):
        """Test control API path."""
        assert API_PATH_CONTROL == "/api/smartly/control"

    def test_sync_path(self):
        """Test sync API path."""
        assert API_PATH_SYNC == "/api/smartly/sync/structure"


class TestViewRegistration:
    """Tests for HTTP view registration."""

    def test_register_views(self, mock_hass):
        """Test views are registered correctly."""
        from custom_components.smartly_bridge.http import register_views

        register_views(mock_hass)

        # Control, Sync Structure, Sync States
        assert mock_hass.http.register_view.call_count == 3


class TestStatesEndpoint:
    """Tests for /api/smartly/sync/states endpoint."""

    @pytest.mark.asyncio
    async def test_states_returns_all_states(self, mock_hass, mock_config_entry):
        """Test states endpoint returns all entity states."""
        from unittest.mock import AsyncMock, MagicMock

        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.const import DOMAIN
        from custom_components.smartly_bridge.http import SmartlySyncStatesView

        # Setup integration data
        nonce_cache = NonceCache()
        await nonce_cache.start()
        rate_limiter = RateLimiter(max_requests=60, window_seconds=60)

        mock_hass.data[DOMAIN] = {
            "config_entry": mock_config_entry,
            "nonce_cache": nonce_cache,
            "rate_limiter": rate_limiter,
        }

        # Mock entity state
        mock_state = MagicMock()
        mock_state.state = "on"
        mock_state.attributes = {"brightness": 255}
        mock_state.last_changed = MagicMock()
        mock_state.last_changed.isoformat = MagicMock(return_value="2025-12-25T10:00:00+00:00")
        mock_state.last_updated = MagicMock()
        mock_state.last_updated.isoformat = MagicMock(return_value="2025-12-25T10:00:00+00:00")

        mock_hass.states.get = MagicMock(return_value=mock_state)

        # Mock request with valid auth
        mock_request = MagicMock()
        mock_request.app = {"hass": mock_hass}
        mock_request.headers = {
            "X-Client-Id": mock_config_entry.data["client_id"],
            "X-Timestamp": str(int(time.time())),
            "X-Nonce": str(uuid.uuid4()),
            "X-Signature": "valid_signature",
        }
        mock_request.method = "GET"
        mock_request.path = "/api/smartly/sync/states"
        mock_request.read = AsyncMock(return_value=b"")

        # Mock auth verification
        with patch("custom_components.smartly_bridge.http.verify_request") as mock_verify:
            mock_verify.return_value = MagicMock(
                success=True, client_id=mock_config_entry.data["client_id"], error=None
            )

            with patch("custom_components.smartly_bridge.http.get_allowed_entities") as mock_get:
                mock_get.return_value = ["light.test"]

                view = SmartlySyncStatesView(mock_request)
                response = await view.get()

                assert response.status == 200

        await nonce_cache.stop()

    @pytest.mark.asyncio
    async def test_states_auth_required(self, mock_hass):
        """Test states endpoint requires authentication."""
        from unittest.mock import MagicMock

        from custom_components.smartly_bridge.const import DOMAIN
        from custom_components.smartly_bridge.http import SmartlySyncStatesView

        # Setup without proper auth
        mock_hass.data[DOMAIN] = {}

        mock_request = MagicMock()
        mock_request.app = {"hass": mock_hass}
        mock_request.headers = {}

        view = SmartlySyncStatesView(mock_request)
        response = await view.get()

        assert response.status == 500  # Integration not configured


class TestControlEndpointFullFlow:
    """Tests for full control endpoint flow."""

    @pytest.mark.asyncio
    async def test_control_invalid_json(self, mock_hass, mock_config_entry):
        """Test control endpoint with invalid JSON."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.const import DOMAIN
        from custom_components.smartly_bridge.http import SmartlyControlView

        nonce_cache = NonceCache()
        await nonce_cache.start()

        mock_hass.data[DOMAIN] = {
            "config_entry": mock_config_entry,
            "nonce_cache": nonce_cache,
            "rate_limiter": RateLimiter(60, 60),
        }

        # Create mock request with invalid JSON
        mock_request = MagicMock()
        mock_request.app = {"hass": mock_hass}
        mock_request.method = "POST"
        mock_request.path = API_PATH_CONTROL
        mock_request.json = AsyncMock(side_effect=json.JSONDecodeError("", "", 0))
        mock_request.transport = MagicMock()
        mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)

        # Create valid auth headers
        import hashlib
        import hmac

        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())
        body_hash = hashlib.sha256(b"").hexdigest()
        message = f"POST\n{API_PATH_CONTROL}\n{timestamp}\n{nonce}\n{body_hash}"
        signature = hmac.new(
            mock_config_entry.data["client_secret"].encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        mock_request.headers = {
            HEADER_CLIENT_ID: mock_config_entry.data["client_id"],
            HEADER_TIMESTAMP: timestamp,
            HEADER_NONCE: nonce,
            HEADER_SIGNATURE: signature,
        }

        with patch("custom_components.smartly_bridge.http.verify_request") as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client", error=None)

            view = SmartlyControlView(mock_request)
            response = await view.post()

            assert response.status == 400

        await nonce_cache.stop()

    @pytest.mark.asyncio
    async def test_control_missing_entity_id(self, mock_hass, mock_config_entry):
        """Test control endpoint with missing entity_id."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.const import DOMAIN
        from custom_components.smartly_bridge.http import SmartlyControlView

        nonce_cache = NonceCache()
        await nonce_cache.start()

        mock_hass.data[DOMAIN] = {
            "config_entry": mock_config_entry,
            "nonce_cache": nonce_cache,
            "rate_limiter": RateLimiter(60, 60),
        }

        # Missing entity_id
        body = {"action": "turn_on"}

        mock_request = MagicMock()
        mock_request.app = {"hass": mock_hass}
        mock_request.method = "POST"
        mock_request.path = API_PATH_CONTROL
        mock_request.json = AsyncMock(return_value=body)
        mock_request.transport = MagicMock()
        mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)

        # Create valid auth headers
        import hashlib
        import hmac

        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())
        body_hash = hashlib.sha256(json.dumps(body).encode()).hexdigest()
        message = f"POST\n{API_PATH_CONTROL}\n{timestamp}\n{nonce}\n{body_hash}"
        signature = hmac.new(
            mock_config_entry.data["client_secret"].encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        mock_request.headers = {
            HEADER_CLIENT_ID: mock_config_entry.data["client_id"],
            HEADER_TIMESTAMP: timestamp,
            HEADER_NONCE: nonce,
            HEADER_SIGNATURE: signature,
        }

        with patch("custom_components.smartly_bridge.http.verify_request") as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client", error=None)

            view = SmartlyControlView(mock_request)
            response = await view.post()

            assert response.status == 400

        await nonce_cache.stop()

    @pytest.mark.asyncio
    async def test_control_entity_not_allowed(self, mock_hass, mock_config_entry):
        """Test control endpoint with entity not in allowed list."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.const import DOMAIN
        from custom_components.smartly_bridge.http import SmartlyControlView

        nonce_cache = NonceCache()
        await nonce_cache.start()

        mock_hass.data[DOMAIN] = {
            "config_entry": mock_config_entry,
            "nonce_cache": nonce_cache,
            "rate_limiter": RateLimiter(60, 60),
        }

        # Create entity registry mock without smartly label
        from homeassistant.helpers import entity_registry as er

        with patch.object(er, "async_get") as mock_er:
            mock_registry = MagicMock()
            mock_entry = MagicMock()
            mock_entry.labels = set()  # No smartly label
            mock_registry.async_get = MagicMock(return_value=mock_entry)
            mock_er.return_value = mock_registry

            body = {
                "entity_id": "light.forbidden",
                "action": "turn_on",
            }

            mock_request = MagicMock()
            mock_request.app = {"hass": mock_hass}
            mock_request.method = "POST"
            mock_request.path = API_PATH_CONTROL
            mock_request.json = AsyncMock(return_value=body)
            mock_request.transport = MagicMock()
            mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)

            # Create valid auth headers
            import hashlib
            import hmac

            timestamp = str(int(time.time()))
            nonce = str(uuid.uuid4())
            body_hash = hashlib.sha256(json.dumps(body).encode()).hexdigest()
            message = f"POST\n{API_PATH_CONTROL}\n{timestamp}\n{nonce}\n{body_hash}"
            signature = hmac.new(
                mock_config_entry.data["client_secret"].encode(),
                message.encode(),
                hashlib.sha256,
            ).hexdigest()

            mock_request.headers = {
                HEADER_CLIENT_ID: mock_config_entry.data["client_id"],
                HEADER_TIMESTAMP: timestamp,
                HEADER_NONCE: nonce,
                HEADER_SIGNATURE: signature,
            }

            with patch("custom_components.smartly_bridge.http.verify_request") as mock_verify:
                mock_verify.return_value = MagicMock(
                    success=True, client_id="test_client", error=None
                )

                view = SmartlyControlView(mock_request)
                response = await view.post()

                assert response.status == 403

        await nonce_cache.stop()

    @pytest.mark.asyncio
    async def test_control_service_not_allowed(self, mock_hass, mock_config_entry):
        """Test control endpoint with service not in allowed list."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.const import DOMAIN
        from custom_components.smartly_bridge.http import SmartlyControlView

        nonce_cache = NonceCache()
        await nonce_cache.start()

        mock_hass.data[DOMAIN] = {
            "config_entry": mock_config_entry,
            "nonce_cache": nonce_cache,
            "rate_limiter": RateLimiter(60, 60),
        }

        # Create entity registry mock with smartly label
        from homeassistant.helpers import entity_registry as er

        with patch.object(er, "async_get") as mock_er:
            mock_registry = MagicMock()
            mock_entry = MagicMock()
            mock_entry.labels = {"smartly"}
            mock_registry.async_get = MagicMock(return_value=mock_entry)
            mock_er.return_value = mock_registry

            body = {
                "entity_id": "light.test",
                "action": "reload",  # Not allowed
            }

            mock_request = MagicMock()
            mock_request.app = {"hass": mock_hass}
            mock_request.method = "POST"
            mock_request.path = API_PATH_CONTROL
            mock_request.json = AsyncMock(return_value=body)
            mock_request.transport = MagicMock()
            mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)

            # Create valid auth headers
            import hashlib
            import hmac

            timestamp = str(int(time.time()))
            nonce = str(uuid.uuid4())
            body_hash = hashlib.sha256(json.dumps(body).encode()).hexdigest()
            message = f"POST\n{API_PATH_CONTROL}\n{timestamp}\n{nonce}\n{body_hash}"
            signature = hmac.new(
                mock_config_entry.data["client_secret"].encode(),
                message.encode(),
                hashlib.sha256,
            ).hexdigest()

            mock_request.headers = {
                HEADER_CLIENT_ID: mock_config_entry.data["client_id"],
                HEADER_TIMESTAMP: timestamp,
                HEADER_NONCE: nonce,
                HEADER_SIGNATURE: signature,
            }

            with patch("custom_components.smartly_bridge.http.verify_request") as mock_verify:
                mock_verify.return_value = MagicMock(
                    success=True, client_id="test_client", error=None
                )

                view = SmartlyControlView(mock_request)
                response = await view.post()

                assert response.status == 403

        await nonce_cache.stop()

    @pytest.mark.asyncio
    async def test_control_service_call_failure(self, mock_hass, mock_config_entry):
        """Test control endpoint when service call fails."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.const import DOMAIN
        from custom_components.smartly_bridge.http import SmartlyControlView

        nonce_cache = NonceCache()
        await nonce_cache.start()

        mock_hass.data[DOMAIN] = {
            "config_entry": mock_config_entry,
            "nonce_cache": nonce_cache,
            "rate_limiter": RateLimiter(60, 60),
        }

        # Mock service call to raise exception
        mock_hass.services.async_call = AsyncMock(side_effect=Exception("Service error"))

        # Create entity registry mock with smartly label
        from homeassistant.helpers import entity_registry as er

        with patch.object(er, "async_get") as mock_er:
            mock_registry = MagicMock()
            mock_entry = MagicMock()
            mock_entry.labels = {"smartly"}
            mock_registry.async_get = MagicMock(return_value=mock_entry)
            mock_er.return_value = mock_registry

            body = {
                "entity_id": "light.test",
                "action": "turn_on",
            }

            mock_request = MagicMock()
            mock_request.app = {"hass": mock_hass}
            mock_request.method = "POST"
            mock_request.path = API_PATH_CONTROL
            mock_request.json = AsyncMock(return_value=body)
            mock_request.transport = MagicMock()
            mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)

            # Create valid auth headers
            import hashlib
            import hmac

            timestamp = str(int(time.time()))
            nonce = str(uuid.uuid4())
            body_hash = hashlib.sha256(json.dumps(body).encode()).hexdigest()
            message = f"POST\n{API_PATH_CONTROL}\n{timestamp}\n{nonce}\n{body_hash}"
            signature = hmac.new(
                mock_config_entry.data["client_secret"].encode(),
                message.encode(),
                hashlib.sha256,
            ).hexdigest()

            mock_request.headers = {
                HEADER_CLIENT_ID: mock_config_entry.data["client_id"],
                HEADER_TIMESTAMP: timestamp,
                HEADER_NONCE: nonce,
                HEADER_SIGNATURE: signature,
            }

            with patch("custom_components.smartly_bridge.http.verify_request") as mock_verify:
                mock_verify.return_value = MagicMock(
                    success=True, client_id="test_client", error=None
                )

                view = SmartlyControlView(mock_request)
                response = await view.post()

                assert response.status == 500

        await nonce_cache.stop()
