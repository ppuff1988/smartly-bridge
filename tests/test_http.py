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
        from custom_components.smartly_bridge.views.control import SmartlyControlView

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
        from custom_components.smartly_bridge.views.control import SmartlyControlView

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
        from custom_components.smartly_bridge.views.control import SmartlyControlView

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
        with patch("custom_components.smartly_bridge.views.control.verify_request") as mock_verify:
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
        from custom_components.smartly_bridge.views.sync import SmartlySyncView

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
            patch("custom_components.smartly_bridge.views.sync.verify_request") as mock_verify,
            patch("custom_components.smartly_bridge.acl.get_structure") as mock_structure,
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

        # Control, Sync Structure, Sync States + 5 Camera views
        # (Snapshot, Stream, List, Config, HLS)
        assert mock_hass.http.register_view.call_count == 8


class TestStatesEndpoint:
    """Tests for /api/smartly/sync/states endpoint."""

    @pytest.mark.asyncio
    async def test_states_returns_all_states(self, mock_hass, mock_config_entry):
        """Test states endpoint returns all entity states."""
        from unittest.mock import AsyncMock, MagicMock

        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.const import DOMAIN
        from custom_components.smartly_bridge.views.sync import SmartlySyncStatesView

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
        with patch("custom_components.smartly_bridge.views.sync.verify_request") as mock_verify:
            mock_verify.return_value = MagicMock(
                success=True, client_id=mock_config_entry.data["client_id"], error=None
            )

            with patch("homeassistant.helpers.entity_registry.async_get"):
                with patch(
                    "custom_components.smartly_bridge.views.sync.get_allowed_entities"
                ) as mock_get:
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
        from custom_components.smartly_bridge.views.sync import SmartlySyncStatesView

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
        from custom_components.smartly_bridge.views.control import SmartlyControlView

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

        with patch("custom_components.smartly_bridge.views.control.verify_request") as mock_verify:
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
        from custom_components.smartly_bridge.views.control import SmartlyControlView

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

        with patch("custom_components.smartly_bridge.views.control.verify_request") as mock_verify:
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
        from custom_components.smartly_bridge.views.control import SmartlyControlView

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

            with patch(
                "custom_components.smartly_bridge.views.control.verify_request"
            ) as mock_verify:
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
        from custom_components.smartly_bridge.views.control import SmartlyControlView

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

            with patch(
                "custom_components.smartly_bridge.views.control.verify_request"
            ) as mock_verify:
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
        from custom_components.smartly_bridge.views.control import SmartlyControlView

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

            with patch(
                "custom_components.smartly_bridge.views.control.verify_request"
            ) as mock_verify:
                mock_verify.return_value = MagicMock(
                    success=True, client_id="test_client", error=None
                )

                view = SmartlyControlView(mock_request)
                response = await view.post()

                assert response.status == 500

        await nonce_cache.stop()


class TestFormatNumericAttributes:
    """Tests for format_numeric_attributes function."""

    def test_current_with_ma_unit(self):
        """Test current formatting with mA unit."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "device_class": "current",
            "friendly_name": "小燈電流",
            "state_class": "measurement",
            "unit_of_measurement": "mA",
            "current": 456.789123,
        }

        result = format_numeric_attributes(attrs)

        assert result["current"] == 456.8  # 1 decimal place for mA
        assert result["unit_of_measurement"] == "mA"

    def test_current_with_a_unit(self):
        """Test current formatting with A unit."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "device_class": "current",
            "friendly_name": "主電流",
            "state_class": "measurement",
            "unit_of_measurement": "A",
            "current": 0.456789123,
        }

        result = format_numeric_attributes(attrs)

        assert result["current"] == 0.457  # 3 decimal places for A
        assert result["unit_of_measurement"] == "A"

    def test_voltage_power_energy(self):
        """Test voltage, power, and energy formatting."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "voltage": 220.123456,
            "power": 100.987654,
            "energy": 1.23456789,
            "temperature": 25.56789,
            "humidity": 65.789,
            "unit_of_measurement": "W",
        }

        result = format_numeric_attributes(attrs)

        assert result["voltage"] == 220.12  # 2 decimal places
        assert result["power"] == 100.99  # 2 decimal places
        assert result["energy"] == 1.23  # 2 decimal places
        assert result["temperature"] == 25.6  # 1 decimal place
        assert result["humidity"] == 65.8  # 1 decimal place

    def test_power_with_kw_unit(self):
        """Test power formatting with kW unit."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "device_class": "power",
            "friendly_name": "總功率",
            "state_class": "measurement",
            "unit_of_measurement": "kW",
            "power": 1.23456789,
        }

        result = format_numeric_attributes(attrs)

        assert result["power"] == 1.235  # 3 decimal places for kW
        assert result["unit_of_measurement"] == "kW"

    def test_power_with_mw_unit(self):
        """Test power formatting with mW unit."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "unit_of_measurement": "mW",
            "power": 1234.56789,
        }

        result = format_numeric_attributes(attrs)

        assert result["power"] == 1235  # 0 decimal places for mW (integer)

    def test_power_factor_and_related(self):
        """Test power factor and related power measurements."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "power_factor": 0.905678123,
            "active_power": 100.987654,
            "reactive_power": 50.123456,
            "apparent_power": 111.789123,
        }

        result = format_numeric_attributes(attrs)

        assert result["power_factor"] == 0.906  # 3 decimal places
        assert result["active_power"] == 100.99  # 2 decimal places
        assert result["reactive_power"] == 50.12  # 2 decimal places
        assert result["apparent_power"] == 111.79  # 2 decimal places

    def test_frequency(self):
        """Test frequency formatting."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "frequency": 50.123456,
        }

        result = format_numeric_attributes(attrs)

        assert result["frequency"] == 50.12  # 2 decimal places

    def test_voltage_with_mv_unit(self):
        """Test voltage formatting with mV unit."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "unit_of_measurement": "mV",
            "voltage": 1234.56789,
        }

        result = format_numeric_attributes(attrs)

        assert result["voltage"] == 1235  # 0 decimal places for mV (integer)

    def test_energy_with_wh_unit(self):
        """Test energy formatting with Wh unit."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "unit_of_measurement": "Wh",
            "energy": 123.456789,
        }

        result = format_numeric_attributes(attrs)

        assert result["energy"] == 123.5  # 1 decimal place for Wh

    def test_energy_with_kwh_unit(self):
        """Test energy formatting with kWh unit."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "unit_of_measurement": "kWh",
            "energy": 1.23456789,
        }

        result = format_numeric_attributes(attrs)

        assert result["energy"] == 1.235  # 3 decimal places for kWh

    def test_battery_and_illuminance(self):
        """Test battery and illuminance formatting (no decimals)."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "battery": 85.6789,
            "illuminance": 499.789,
        }

        result = format_numeric_attributes(attrs)

        assert result["battery"] == 86  # 0 decimal places (integer)
        assert result["illuminance"] == 500  # 0 decimal places (integer)

    def test_air_quality_sensors(self):
        """Test air quality sensor formatting."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "co2": 449.789,
            "pm25": 12.456,
            "pm10": 25.678,
            "pressure": 1013.25678,
        }

        result = format_numeric_attributes(attrs)

        assert result["co2"] == 450  # 0 decimal places (integer)
        assert result["pm25"] == 12.5  # 1 decimal place
        assert result["pm10"] == 25.7  # 1 decimal place
        assert result["pressure"] == 1013.3  # 1 decimal place

    def test_non_numeric_values_preserved(self):
        """Test that non-numeric values are preserved."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "device_class": "current",
            "friendly_name": "Test Sensor",
            "state_class": "measurement",
            "current": 1.234567,
            "some_string": "text",
            "some_none": None,
            "some_bool": True,
        }

        result = format_numeric_attributes(attrs)

        assert result["current"] == 1.235  # Formatted
        assert result["some_string"] == "text"  # Preserved
        assert result["some_none"] is None  # Preserved
        assert result["some_bool"] is True  # Preserved

    def test_missing_attributes(self):
        """Test that missing numeric attributes don't cause errors."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "device_class": "current",
            "friendly_name": "Test",
        }

        result = format_numeric_attributes(attrs)

        assert "current" not in result  # Not added if not present
        assert result["device_class"] == "current"

    def test_invalid_numeric_values(self):
        """Test handling of invalid numeric values."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "current": "not_a_number",
            "voltage": float("inf"),
        }

        result = format_numeric_attributes(attrs)

        # Invalid values should be preserved
        assert result["current"] == "not_a_number"
        # Inf should still be handled by round() but kept as inf
        assert result["voltage"] == float("inf")

    def test_original_attributes_not_modified(self):
        """Test that original attributes dict is not modified."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        original = {
            "current": 1.23456789,
            "voltage": 220.123456,
        }

        result = format_numeric_attributes(original)

        # Original should not be modified
        assert original["current"] == 1.23456789
        assert original["voltage"] == 220.123456
        # Result should be formatted
        assert result["current"] == 1.235
        assert result["voltage"] == 220.12
