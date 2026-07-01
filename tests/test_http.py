"""Tests for HTTP API endpoints."""

from __future__ import annotations

import json
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.application.control import ControlCommand, SmartlyCommand
from custom_components.smartly_bridge.const import (
    API_PATH_CONTROL,
    API_PATH_DEVICE_EVENTS,
    API_PATH_LOCAL_AUTOMATION_RULES,
    API_PATH_RAW_DIAGNOSTIC,
    API_PATH_STATES,
    API_PATH_SYNC,
    DOMAIN,
    HEADER_CLIENT_ID,
    HEADER_NONCE,
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
)
from custom_components.smartly_bridge.domain.models import BridgeResponse
from custom_components.smartly_bridge.views.control import (
    _entity_id_from_body,
    _normalize_control_body,
    _service_data_from_body,
    _smartly_command_from_body,
)


class FakeSmartlyCommandExecutor:
    """SmartlyCommand executor used to verify setup-created runtime wiring."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, SmartlyCommand]] = []

    async def execute(self, client_id: str, command: SmartlyCommand) -> BridgeResponse:
        """Record and accept a canonical command."""
        self.calls.append((client_id, command))
        return BridgeResponse(
            {
                "success": True,
                "schema_version": "2026.06",
                "command_id": command.command_id,
                "status": "completed",
                "device_id": command.device_id,
                "capability": command.capability,
                "command": command.command,
                "data": {
                    "command_id": command.command_id,
                    "status": "completed",
                },
                "warnings": [],
                "errors": [],
            }
        )


class FakeControlUseCase:
    """Legacy ControlCommand use case used to verify runtime wiring."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ControlCommand]] = []

    async def execute(self, client_id: str, command: ControlCommand) -> BridgeResponse:
        """Record and accept a legacy control command."""
        self.calls.append((client_id, command))
        return BridgeResponse(
            {
                "success": True,
                "schema_version": "2026.06",
                "entity_id": command.entity_id,
                "action": command.action,
                "service_data": command.service_data,
                "data": {
                    "entity_id": command.entity_id,
                    "action": command.action,
                },
                "warnings": [],
                "errors": [],
            }
        )


class FakeRawDiagnosticStore:
    """Raw diagnostic store used to verify runtime wiring."""

    def __init__(self) -> None:
        self.refs: list[str] = []

    def get_raw_diagnostic(self, raw_ref: str) -> dict:
        """Return raw diagnostic data for the requested ref."""
        self.refs.append(raw_ref)
        return {
            "entity_id": "light.kitchen",
            "access_token": "secret-token",
            "attributes": {
                "host": "192.168.1.25",
                "brightness": 128,
            },
        }


def test_control_request_accepts_data_alias_for_service_data() -> None:
    """Control requests accept frontend data payloads as service data."""
    body = {
        "action": "set_brightness",
        "data": {"brightness": 150},
    }

    assert _service_data_from_body(body) == {"brightness": 150}


def test_control_request_prefers_service_data_over_data_alias() -> None:
    """Explicit service_data wins when both payload keys are present."""
    body = {
        "service_data": {"brightness": 120},
        "data": {"brightness": 150},
    }

    assert _service_data_from_body(body) == {"brightness": 120}


def test_control_request_accepts_device_id_alias_for_entity_id() -> None:
    """Control requests accept frontend device_id as the target entity identifier."""
    body = {
        "device_id": "select.presence_occupancy_sensitivity",
        "action": "select_option",
        "data": {"option": "low"},
    }

    assert _entity_id_from_body(body) == "select.presence_occupancy_sensitivity"


def test_control_request_prefers_entity_id_over_device_id_alias() -> None:
    """Canonical entity_id wins when both target identifier keys are present."""
    body = {
        "entity_id": "number.presence_detection_delay",
        "device_id": "binary_sensor.presence",
    }

    assert _entity_id_from_body(body) == "number.presence_detection_delay"


def test_control_request_normalizes_platform_button_command() -> None:
    """Platform device commands normalize to canonical Home Assistant control fields."""
    body = {
        "device_id": "usb-fan",
        "capability": "button",
        "command": "press",
        "target": "fan_short",
    }

    normalized = _normalize_control_body(body)

    assert normalized == {
        "entity_id": "button.usb_fan_fan_short",
        "action": "press",
        "service_data": {},
        "actor": {},
    }


def test_control_request_normalizes_platform_command_with_entity_target() -> None:
    """Entity targets can be supplied directly in the normalized command format."""
    body = {
        "device_id": "usb-fan",
        "capability": "button",
        "command": "press",
        "target": "button.usb_fan_short_press",
    }

    normalized = _normalize_control_body(body)

    assert normalized["entity_id"] == "button.usb_fan_short_press"
    assert normalized["action"] == "press"


def test_control_request_builds_vnext_smartly_command() -> None:
    """API vNext command payloads remain logical-device commands."""
    body = {
        "command_id": "cmd-1",
        "device_id": "ldev_light_kitchen",
        "capability": "brightness",
        "command": "set_brightness",
        "params": {"value": 80},
        "source": {"user_id": "user-1"},
    }

    command = _smartly_command_from_body(body)

    assert command is not None
    assert command.command_id == "cmd-1"
    assert command.device_id == "ldev_light_kitchen"
    assert command.capability == "brightness"
    assert command.command == "set_brightness"
    assert command.params == {"value": 80}
    assert command.source == {"user_id": "user-1"}


def test_control_request_ignores_legacy_body_as_vnext_command() -> None:
    """Legacy control requests continue through entity/action normalization."""
    assert (
        _smartly_command_from_body(
            {"entity_id": "light.kitchen", "action": "turn_on", "service_data": {}}
        )
        is None
    )


def test_control_request_does_not_forward_routing_target_as_service_data() -> None:
    """Frontend routing targets are not forwarded to Home Assistant services."""
    body = {
        "entity_id": "button.6e0e87b473817f383acf3e41b5fecbd2_fan_short",
        "action": "press",
        "data": {"target": "fan_short"},
    }

    normalized = _normalize_control_body(body)

    assert normalized == {
        "entity_id": "button.6e0e87b473817f383acf3e41b5fecbd2_fan_short",
        "action": "press",
        "service_data": {},
        "actor": {},
    }


class TestControlEndpoint:
    """Tests for /api/smartly/control endpoint."""

    @pytest.mark.asyncio
    async def test_control_not_configured_response_includes_vnext_error_envelope(self):
        """Control setup failures expose API vNext error envelope fields."""
        from custom_components.smartly_bridge.views.control import SmartlyControlView

        request = MagicMock()
        request.headers = {}
        request.method = "POST"
        request.path = API_PATH_CONTROL
        request.app = {"hass": MagicMock()}
        request.app["hass"].data = {}

        response = await SmartlyControlView(request).post()

        assert response.status == 500
        assert json.loads(response.body) == {
            "error": "integration_not_configured",
            "schema_version": "2026.06",
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": "INTEGRATION_NOT_CONFIGURED",
                    "message": "integration not configured",
                    "target": "control",
                    "retryable": False,
                }
            ],
        }

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
    async def test_control_auth_failure_response_includes_vnext_error_envelope(self):
        """Control auth failures expose API vNext error envelope fields."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.views.control import SmartlyControlView

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
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)

        request.app["hass"].data = {
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

        with patch("custom_components.smartly_bridge.views.control.verify_request") as mock_verify:
            mock_verify.return_value = MagicMock(
                success=False,
                client_id=None,
                error="invalid_signature",
            )

            response = await SmartlyControlView(request).post()

        assert response.status == 401
        assert json.loads(response.body) == {
            "error": "invalid_signature",
            "schema_version": "2026.06",
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": "INVALID_SIGNATURE",
                    "message": "invalid signature",
                    "target": "control",
                    "retryable": False,
                }
            ],
        }

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
        assert response.headers["Retry-After"] == "60"
        assert response.headers["X-RateLimit-Remaining"] == "0"
        assert json.loads(response.body) == {
            "error": "rate_limited",
            "schema_version": "2026.06",
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": "RATE_LIMITED",
                    "message": "rate limited",
                    "target": "control",
                    "retryable": False,
                }
            ],
        }


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

    def test_legacy_states_path(self):
        """Test legacy states API path."""
        assert API_PATH_STATES == "/api/smartly/states"

    def test_device_events_path(self):
        """Test device events API path."""
        assert API_PATH_DEVICE_EVENTS == "/api/smartly/devices/{device_id}/events"

    def test_local_automation_rules_path(self):
        """Test local automation rules API path."""
        assert API_PATH_LOCAL_AUTOMATION_RULES == "/api/smartly/automations/local/rules"

    def test_raw_diagnostic_path(self):
        """Test raw diagnostic API path."""
        assert API_PATH_RAW_DIAGNOSTIC == "/api/smartly/diagnostics/raw/{raw_ref}"


class TestViewRegistration:
    """Tests for HTTP view registration."""

    def test_register_views(self, mock_hass):
        """Test views are registered correctly."""
        from custom_components.smartly_bridge.http import register_views

        register_views(mock_hass)

        # Control, Device Events, Local Automation Rules, Raw Diagnostics,
        # Sync Structure, Sync States, Legacy States alias
        # + 5 Camera views
        # (Snapshot, Stream, List, Config, HLS) + 4 WebRTC views
        # (Token, Offer, ICE, Hangup) + 3 History views
        # (History, History Batch, Statistics)
        assert mock_hass.http.register_view.call_count == 19

        registered_views = [call.args[0] for call in mock_hass.http.register_view.call_args_list]
        registered_urls = {view.url for view in registered_views}
        assert API_PATH_STATES in registered_urls


class TestRawDiagnosticEndpoint:
    """Tests for /api/smartly/diagnostics/raw/{raw_ref} endpoint."""

    def test_fetch_raw_diagnostic_reads_and_masks_store_payload(self):
        """Raw diagnostic invocation adapter reads and masks store payload."""
        from custom_components.smartly_bridge.views.diagnostics import _fetch_raw_diagnostic

        store = FakeRawDiagnosticStore()

        result = _fetch_raw_diagnostic(store, raw_ref="raw_light_001")

        assert result.status == 200
        assert store.refs == ["raw_light_001"]
        assert result.body["data"]["payload"]["access_token"] == "<redacted>"
        assert result.body["data"]["payload"]["attributes"]["host"] == "<redacted>"

    @pytest.mark.asyncio
    async def test_raw_diagnostic_uses_runtime_store(self, mock_hass, mock_config_entry):
        """Raw diagnostic requests read through the setup-created storage port."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.views.diagnostics import SmartlyRawDiagnosticView

        nonce_cache = NonceCache()
        await nonce_cache.start()

        store = FakeRawDiagnosticStore()
        mock_hass.data[DOMAIN] = {
            "config_entry": mock_config_entry,
            "nonce_cache": nonce_cache,
            "rate_limiter": RateLimiter(60, 60),
            "runtime_adapters": {"raw_diagnostic_store": store},
        }

        mock_request = MagicMock()
        mock_request.app = {"hass": mock_hass}
        mock_request.method = "GET"
        mock_request.path = "/api/smartly/diagnostics/raw/raw_light_001"
        mock_request.match_info = {"raw_ref": "raw_light_001"}
        mock_request.transport = MagicMock()
        mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        mock_request.headers = {}

        with patch(
            "custom_components.smartly_bridge.views.diagnostics.verify_request"
        ) as mock_verify, patch(
            "custom_components.smartly_bridge.views.diagnostics.HomeAssistantRawDiagnosticStore"
        ) as mock_store:
            mock_verify.return_value = MagicMock(
                success=True, client_id="test_client", error=None
            )

            response = await SmartlyRawDiagnosticView(mock_request).get()

        assert response.status == 200
        mock_store.assert_not_called()
        assert store.refs == ["raw_light_001"]
        assert json.loads(response.body) == {
            "success": True,
            "schema_version": "2026.06",
            "raw_ref": "raw_light_001",
            "data": {
                "raw_ref": "raw_light_001",
                "payload": {
                    "entity_id": "light.kitchen",
                    "access_token": "<redacted>",
                    "attributes": {
                        "host": "<redacted>",
                        "brightness": 128,
                    },
                },
            },
            "warnings": [],
            "errors": [],
        }

        await nonce_cache.stop()

    @pytest.mark.asyncio
    async def test_raw_diagnostic_echoes_request_correlation_headers(
        self, mock_hass, mock_config_entry
    ):
        """Raw diagnostic vNext envelope exposes request/correlation IDs."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.views.diagnostics import SmartlyRawDiagnosticView

        nonce_cache = NonceCache()
        await nonce_cache.start()

        store = FakeRawDiagnosticStore()
        mock_hass.data[DOMAIN] = {
            "config_entry": mock_config_entry,
            "nonce_cache": nonce_cache,
            "rate_limiter": RateLimiter(60, 60),
            "runtime_adapters": {"raw_diagnostic_store": store},
        }

        mock_request = MagicMock()
        mock_request.app = {"hass": mock_hass}
        mock_request.method = "GET"
        mock_request.path = "/api/smartly/diagnostics/raw/raw_light_001"
        mock_request.match_info = {"raw_ref": "raw_light_001"}
        mock_request.transport = MagicMock()
        mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        mock_request.headers = {
            "X-Request-Id": "req-raw-1",
            "X-Correlation-Id": "corr-raw-1",
        }

        with patch(
            "custom_components.smartly_bridge.views.diagnostics.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(
                success=True, client_id="test_client", error=None
            )

            response = await SmartlyRawDiagnosticView(mock_request).get()

        assert response.status == 200
        body = json.loads(response.body)
        assert body["request_id"] == "req-raw-1"
        assert body["correlation_id"] == "corr-raw-1"

        await nonce_cache.stop()

    @pytest.mark.asyncio
    async def test_raw_diagnostic_auth_failure_uses_diagnostic_error_envelope(
        self, mock_hass, mock_config_entry
    ):
        """Raw diagnostic auth failures use diagnostics-specific error targets."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.views.diagnostics import SmartlyRawDiagnosticView

        nonce_cache = NonceCache()
        await nonce_cache.start()

        mock_hass.data[DOMAIN] = {
            "config_entry": mock_config_entry,
            "nonce_cache": nonce_cache,
            "rate_limiter": RateLimiter(60, 60),
            "runtime_adapters": {"raw_diagnostic_store": FakeRawDiagnosticStore()},
        }

        mock_request = MagicMock()
        mock_request.app = {"hass": mock_hass}
        mock_request.method = "GET"
        mock_request.path = "/api/smartly/diagnostics/raw/raw_light_001"
        mock_request.match_info = {"raw_ref": "raw_light_001"}
        mock_request.transport = MagicMock()
        mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        mock_request.headers = {}

        with patch(
            "custom_components.smartly_bridge.views.diagnostics.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(
                success=False, client_id=None, error="auth_failed"
            )

            response = await SmartlyRawDiagnosticView(mock_request).get()

        assert response.status == 401
        assert json.loads(response.body) == {
            "error": "auth_failed",
            "message": "Raw diagnostic request authentication failed",
            "schema_version": "2026.06",
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": "AUTH_FAILED",
                    "message": "Raw diagnostic request authentication failed",
                    "target": "diagnostics.raw.auth",
                    "retryable": False,
                }
            ],
        }

        await nonce_cache.stop()

    @pytest.mark.asyncio
    async def test_raw_diagnostic_lazily_creates_runtime_store(
        self, mock_hass, mock_config_entry
    ):
        """Raw diagnostic requests fall back to the HA runtime store adapter."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.views.diagnostics import SmartlyRawDiagnosticView

        nonce_cache = NonceCache()
        await nonce_cache.start()

        mock_hass.data[DOMAIN] = {
            "config_entry": mock_config_entry,
            "nonce_cache": nonce_cache,
            "rate_limiter": RateLimiter(60, 60),
            "raw_diagnostics": {
                "raw_light_001": {
                    "entity_id": "light.kitchen",
                    "access_token": "secret-token",
                }
            },
            "runtime_adapters": {},
        }

        mock_request = MagicMock()
        mock_request.app = {"hass": mock_hass}
        mock_request.method = "GET"
        mock_request.path = "/api/smartly/diagnostics/raw/raw_light_001"
        mock_request.match_info = {"raw_ref": "raw_light_001"}
        mock_request.transport = MagicMock()
        mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        mock_request.headers = {}

        with patch(
            "custom_components.smartly_bridge.views.diagnostics.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(
                success=True, client_id="test_client", error=None
            )

            response = await SmartlyRawDiagnosticView(mock_request).get()

        assert response.status == 200
        assert json.loads(response.body)["data"]["payload"] == {
            "entity_id": "light.kitchen",
            "access_token": "<redacted>",
        }
        assert "raw_diagnostic_store" in mock_hass.data[DOMAIN]["runtime_adapters"]

        await nonce_cache.stop()


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

        # Mock entity registry entry
        mock_entry = MagicMock()
        mock_entry.icon = "mdi:lightbulb"
        mock_entry.original_icon = None

        mock_entity_reg = MagicMock()
        mock_entity_reg.async_get_entity_id = MagicMock(return_value="light.test")

        # Mock auth verification
        with patch("custom_components.smartly_bridge.views.sync.verify_request") as mock_verify:
            mock_verify.return_value = MagicMock(
                success=True, client_id=mock_config_entry.data["client_id"], error=None
            )

            with patch("homeassistant.helpers.entity_registry.async_get") as mock_reg_get:
                mock_reg_get.return_value = mock_entity_reg
                mock_entity_reg.async_get = MagicMock(return_value=mock_entry)

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
            body = json.loads(response.text)
            assert body == {
                "error": "invalid_json",
                "schema_version": "2026.06",
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "INVALID_JSON",
                        "message": "invalid json",
                        "target": "control",
                        "retryable": False,
                    }
                ],
            }

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
            body = json.loads(response.text)
            assert body == {
                "error": "missing_required_fields",
                "schema_version": "2026.06",
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "MISSING_REQUIRED_FIELDS",
                        "message": "missing required fields",
                        "target": "control",
                        "retryable": False,
                    }
                ],
            }

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

    @pytest.mark.asyncio
    async def test_control_platform_button_command_calls_button_press(
        self, mock_hass, mock_config_entry
    ):
        """Normalized Platform button commands call Home Assistant button.press."""
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
        mock_hass.states.get.return_value = None

        from homeassistant.helpers import entity_registry as er

        with patch.object(er, "async_get") as mock_er:
            mock_registry = MagicMock()
            mock_entry = MagicMock()
            mock_entry.labels = {"smartly"}
            mock_registry.async_get = MagicMock(return_value=mock_entry)
            mock_er.return_value = mock_registry

            body = {
                "device_id": "usb-fan",
                "capability": "button",
                "command": "press",
                "target": "fan_short",
            }

            mock_request = MagicMock()
            mock_request.app = {"hass": mock_hass}
            mock_request.method = "POST"
            mock_request.path = API_PATH_CONTROL
            mock_request.json = AsyncMock(return_value=body)
            mock_request.transport = MagicMock()
            mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
            mock_request.headers = {}

            with patch(
                "custom_components.smartly_bridge.views.control.verify_request"
            ) as mock_verify:
                mock_verify.return_value = MagicMock(
                    success=True, client_id="test_client", error=None
                )

                view = SmartlyControlView(mock_request)
                response = await view.post()

        assert response.status == 200
        mock_hass.services.async_call.assert_awaited_once_with(
            "button",
            "press",
            {"entity_id": "button.usb_fan_fan_short"},
            blocking=True,
        )

        await nonce_cache.stop()

    @pytest.mark.asyncio
    async def test_control_legacy_command_uses_setup_runtime_use_case(
        self, mock_hass, mock_config_entry
    ):
        """Legacy entity/action control path executes through setup-created use case."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.const import DOMAIN
        from custom_components.smartly_bridge.views.control import SmartlyControlView

        use_case = FakeControlUseCase()
        mock_hass.data[DOMAIN] = {
            "config_entry": mock_config_entry,
            "nonce_cache": NonceCache(),
            "rate_limiter": RateLimiter(60, 60),
            "runtime_adapters": {
                "control_use_case": use_case,
            },
        }
        body = {
            "entity_id": "light.kitchen",
            "action": "turn_on",
            "service_data": {"brightness_pct": 50},
            "actor": {"source": "legacy-test"},
        }
        mock_request = MagicMock()
        mock_request.app = {"hass": mock_hass}
        mock_request.method = "POST"
        mock_request.path = API_PATH_CONTROL
        mock_request.json = AsyncMock(return_value=body)
        mock_request.transport = MagicMock()
        mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        mock_request.headers = {}

        with patch(
            "custom_components.smartly_bridge.views.control.verify_request"
        ) as mock_verify, patch(
            "custom_components.smartly_bridge.views.control.HomeAssistantControlGateway"
        ) as mock_gateway:
            mock_verify.return_value = MagicMock(
                success=True, client_id="test_client", error=None
            )

            response = await SmartlyControlView(mock_request).post()

        assert response.status == 200
        mock_gateway.assert_not_called()
        assert use_case.calls == [
            (
                "test_client",
                ControlCommand(
                    entity_id="light.kitchen",
                    action="turn_on",
                    service_data={"brightness_pct": 50},
                    actor={"source": "legacy-test"},
                ),
            )
        ]

    @pytest.mark.asyncio
    async def test_control_response_includes_request_context_headers(
        self, mock_hass, mock_config_entry
    ):
        """Control responses echo optional request correlation headers."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.const import DOMAIN
        from custom_components.smartly_bridge.views.control import SmartlyControlView

        use_case = FakeControlUseCase()
        mock_hass.data[DOMAIN] = {
            "config_entry": mock_config_entry,
            "nonce_cache": NonceCache(),
            "rate_limiter": RateLimiter(60, 60),
            "runtime_adapters": {
                "control_use_case": use_case,
            },
        }
        body = {
            "entity_id": "light.kitchen",
            "action": "turn_on",
            "service_data": {"brightness_pct": 50},
        }
        mock_request = MagicMock()
        mock_request.app = {"hass": mock_hass}
        mock_request.method = "POST"
        mock_request.path = API_PATH_CONTROL
        mock_request.json = AsyncMock(return_value=body)
        mock_request.transport = MagicMock()
        mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        mock_request.headers = {
            "X-Request-Id": "req-control-001",
            "X-Correlation-Id": "corr-control-001",
        }

        with patch(
            "custom_components.smartly_bridge.views.control.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(
                success=True, client_id="test_client", error=None
            )

            response = await SmartlyControlView(mock_request).post()

        assert response.status == 200
        payload = json.loads(response.body)
        assert payload["request_id"] == "req-control-001"
        assert payload["correlation_id"] == "corr-control-001"
        assert payload["success"] is True
        assert payload["entity_id"] == "light.kitchen"

    @pytest.mark.asyncio
    async def test_control_vnext_command_uses_setup_runtime_executor(
        self, mock_hass, mock_config_entry
    ):
        """API vNext command path executes through setup-created runtime adapters."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.const import DOMAIN
        from custom_components.smartly_bridge.views.control import SmartlyControlView

        executor = FakeSmartlyCommandExecutor()
        mock_hass.data[DOMAIN] = {
            "config_entry": mock_config_entry,
            "nonce_cache": NonceCache(),
            "rate_limiter": RateLimiter(60, 60),
            "runtime_adapters": {
                "smartly_command_executor": executor,
            },
        }
        body = {
            "command_id": "cmd-runtime",
            "device_id": "ldev_light_kitchen",
            "capability": "brightness",
            "command": "set_brightness",
            "params": {"value": 35},
        }
        mock_request = MagicMock()
        mock_request.app = {"hass": mock_hass}
        mock_request.method = "POST"
        mock_request.path = API_PATH_CONTROL
        mock_request.json = AsyncMock(return_value=body)
        mock_request.transport = MagicMock()
        mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        mock_request.headers = {}

        with patch(
            "custom_components.smartly_bridge.views.control.verify_request"
        ) as mock_verify, patch(
            "custom_components.smartly_bridge.views.control.HomeAssistantSmartlyCommandExecutor"
        ) as mock_executor:
            mock_verify.return_value = MagicMock(
                success=True, client_id="test_client", error=None
            )

            response = await SmartlyControlView(mock_request).post()

        assert response.status == 200
        mock_executor.assert_not_called()
        payload = json.loads(response.body)
        assert payload["command_id"] == "cmd-runtime"
        assert executor.calls == [
            (
                "test_client",
                SmartlyCommand(
                    command_id="cmd-runtime",
                    device_id="ldev_light_kitchen",
                    capability="brightness",
                    command="set_brightness",
                    params={"value": 35},
                ),
            )
        ]

    @pytest.mark.asyncio
    async def test_control_vnext_smartly_command_dispatches_resolved_source_entity(
        self, mock_hass, mock_config_entry
    ):
        """API vNext commands resolve logical devices before calling Home Assistant."""
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
        updated_state = MagicMock()
        updated_state.state = "on"
        updated_state.attributes = {"brightness": 204}
        mock_hass.states.get.return_value = updated_state

        from homeassistant.helpers import entity_registry as er

        with (
            patch.object(er, "async_get") as mock_er,
            patch(
                "custom_components.smartly_bridge.adapters.home_assistant.get_allowed_entities",
                return_value=["light.kitchen"],
            ),
        ):
            mock_registry = MagicMock()
            mock_entry = MagicMock()
            mock_entry.labels = {"smartly"}
            mock_entry.device_id = "ha-device-1"
            mock_registry.async_get = MagicMock(return_value=mock_entry)
            mock_er.return_value = mock_registry

            body = {
                "command_id": "cmd-1",
                "device_id": "ldev_ha_device_1",
                "capability": "brightness",
                "command": "set_brightness",
                "params": {"value": 80},
                "source": {"user_id": "user-1"},
            }

            mock_request = MagicMock()
            mock_request.app = {"hass": mock_hass}
            mock_request.method = "POST"
            mock_request.path = API_PATH_CONTROL
            mock_request.json = AsyncMock(return_value=body)
            mock_request.transport = MagicMock()
            mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
            mock_request.headers = {}

            with patch(
                "custom_components.smartly_bridge.views.control.verify_request"
            ) as mock_verify:
                mock_verify.return_value = MagicMock(
                    success=True, client_id="test_client", error=None
                )

                response = await SmartlyControlView(mock_request).post()

        assert response.status == 200
        assert json.loads(response.body) == {
            "success": True,
            "schema_version": "2026.06",
            "command_id": "cmd-1",
            "status": "completed",
            "adapter_id": "home_assistant",
            "correlation_id": "cmd-1",
            "device_id": "ldev_ha_device_1",
            "capability": "brightness",
            "command": "set_brightness",
            "entity_id": "light.kitchen",
            "expected_state": {"brightness": {"value": 80, "unit": "percent"}},
            "new_state": "on",
            "new_attributes": {"brightness": 204},
            "data": {
                "command_id": "cmd-1",
                "status": "completed",
                "device_id": "ldev_ha_device_1",
                "capability": "brightness",
                "command": "set_brightness",
                "adapter_id": "home_assistant",
                "correlation_id": "cmd-1",
                "source_entity_id": "light.kitchen",
                "expected_state": {"brightness": {"value": 80, "unit": "percent"}},
            },
            "warnings": [],
            "errors": [],
        }
        mock_hass.services.async_call.assert_awaited_once_with(
            "light",
            "turn_on",
            {"entity_id": "light.kitchen", "brightness_pct": 80},
            blocking=True,
        )

        await nonce_cache.stop()

    @pytest.mark.asyncio
    async def test_control_vnext_smartly_command_dispatches_button_press(
        self, mock_hass, mock_config_entry
    ):
        """Canonical button press commands resolve and call Home Assistant button.press."""
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

        mock_button_state = MagicMock()
        mock_button_state.state = "idle"
        mock_button_state.attributes = {"friendly_name": "Desk Scene"}
        mock_hass.states.get.return_value = mock_button_state

        from homeassistant.helpers import entity_registry as er

        with (
            patch.object(er, "async_get") as mock_er,
            patch(
                "custom_components.smartly_bridge.adapters.home_assistant.get_allowed_entities",
                return_value=["button.desk_scene"],
            ),
        ):
            mock_registry = MagicMock()
            mock_entry = MagicMock()
            mock_entry.labels = {"smartly"}
            mock_entry.device_id = "ha-button-1"
            mock_registry.async_get = MagicMock(return_value=mock_entry)
            mock_er.return_value = mock_registry

            body = {
                "command_id": "cmd-button",
                "device_id": "ldev_ha_button_1",
                "capability": "button_press",
                "command": "press",
                "params": {},
            }

            mock_request = MagicMock()
            mock_request.app = {"hass": mock_hass}
            mock_request.method = "POST"
            mock_request.path = API_PATH_CONTROL
            mock_request.json = AsyncMock(return_value=body)
            mock_request.transport = MagicMock()
            mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
            mock_request.headers = {}

            with patch(
                "custom_components.smartly_bridge.views.control.verify_request"
            ) as mock_verify:
                mock_verify.return_value = MagicMock(
                    success=True, client_id="test_client", error=None
                )

                response = await SmartlyControlView(mock_request).post()

        assert response.status == 200
        assert json.loads(response.body) == {
            "success": True,
            "schema_version": "2026.06",
            "command_id": "cmd-button",
            "status": "completed",
            "adapter_id": "home_assistant",
            "correlation_id": "cmd-button",
            "device_id": "ldev_ha_button_1",
            "capability": "button_press",
            "command": "press",
            "entity_id": "button.desk_scene",
            "expected_state": {},
            "new_state": "idle",
            "new_attributes": {"friendly_name": "Desk Scene"},
            "data": {
                "command_id": "cmd-button",
                "status": "completed",
                "device_id": "ldev_ha_button_1",
                "capability": "button_press",
                "command": "press",
                "adapter_id": "home_assistant",
                "correlation_id": "cmd-button",
                "source_entity_id": "button.desk_scene",
                "expected_state": {},
            },
            "warnings": [],
            "errors": [],
        }
        mock_hass.services.async_call.assert_awaited_once_with(
            "button",
            "press",
            {"entity_id": "button.desk_scene"},
            blocking=True,
        )

        await nonce_cache.stop()

    @pytest.mark.asyncio
    async def test_control_vnext_numeric_setting_resolves_sibling_number_entity(
        self, mock_hass, mock_config_entry
    ):
        """API vNext numeric settings resolve editable sibling number entities."""
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

        presence_state = MagicMock()
        presence_state.state = "on"
        presence_state.attributes = {
            "friendly_name": "Presence Sensor",
            "device_class": "occupancy",
        }
        number_state = MagicMock()
        number_state.state = "20"
        number_state.attributes = {
            "friendly_name": "Trigger hold seconds",
            "min": 1,
            "max": 120,
            "step": 1,
            "unit_of_measurement": "s",
        }
        mock_hass.states.get.side_effect = lambda entity_id: {
            "binary_sensor.presence": presence_state,
            "number.presence_detection_delay": number_state,
        }.get(entity_id)

        from homeassistant.helpers import entity_registry as er

        with (
            patch.object(er, "async_get") as mock_er,
            patch(
                "custom_components.smartly_bridge.adapters.home_assistant.get_allowed_entities",
                return_value=["binary_sensor.presence"],
            ),
        ):
            primary_entry = MagicMock()
            primary_entry.labels = {"smartly"}
            primary_entry.device_id = "zigbee-presence-1"
            setting_entry = MagicMock()
            setting_entry.labels = set()
            setting_entry.device_id = "zigbee-presence-1"
            setting_entry.entity_id = "number.presence_detection_delay"

            mock_registry = MagicMock()
            mock_registry.entities = {
                "binary_sensor.presence": primary_entry,
                "number.presence_detection_delay": setting_entry,
            }
            mock_registry.async_get.side_effect = lambda entity_id: {
                "binary_sensor.presence": primary_entry,
                "number.presence_detection_delay": setting_entry,
            }.get(entity_id)
            mock_er.return_value = mock_registry

            body = {
                "command_id": "cmd-setting-delay",
                "device_id": "ldev_zigbee_presence_1",
                "capability": "numeric_setting",
                "command": "set_value",
                "params": {"value": 20},
                "source": {"user_id": "user-1"},
            }

            mock_request = MagicMock()
            mock_request.app = {"hass": mock_hass}
            mock_request.method = "POST"
            mock_request.path = API_PATH_CONTROL
            mock_request.json = AsyncMock(return_value=body)
            mock_request.transport = MagicMock()
            mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
            mock_request.headers = {}

            with patch(
                "custom_components.smartly_bridge.views.control.verify_request"
            ) as mock_verify:
                mock_verify.return_value = MagicMock(
                    success=True, client_id="test_client", error=None
                )

                response = await SmartlyControlView(mock_request).post()

        assert response.status == 200
        assert json.loads(response.body)["entity_id"] == "number.presence_detection_delay"
        assert json.loads(response.body)["expected_state"] == {
            "numeric_setting": {"value": 20}
        }
        mock_hass.services.async_call.assert_awaited_once_with(
            "number",
            "set_value",
            {"entity_id": "number.presence_detection_delay", "value": 20},
            blocking=True,
        )

        await nonce_cache.stop()

    @pytest.mark.asyncio
    async def test_control_vnext_numeric_setting_uses_keyed_sibling_number_entity(
        self, mock_hass, mock_config_entry
    ):
        """API vNext numeric setting keys select the matching sibling number."""
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

        presence_state = MagicMock()
        presence_state.state = "on"
        presence_state.attributes = {
            "friendly_name": "Presence Sensor",
            "device_class": "occupancy",
        }
        trigger_state = MagicMock()
        trigger_state.state = "20"
        trigger_state.attributes = {
            "friendly_name": "Trigger hold seconds",
            "min": 1,
            "max": 120,
            "step": 1,
            "unit_of_measurement": "s",
        }
        cooldown_state = MagicMock()
        cooldown_state.state = "5"
        cooldown_state.attributes = {
            "friendly_name": "Cooldown seconds",
            "min": 1,
            "max": 120,
            "step": 1,
            "unit_of_measurement": "s",
        }
        mock_hass.states.get.side_effect = lambda entity_id: {
            "binary_sensor.presence": presence_state,
            "number.presence_detection_delay": trigger_state,
            "number.presence_cooldown": cooldown_state,
        }.get(entity_id)

        from homeassistant.helpers import entity_registry as er

        with (
            patch.object(er, "async_get") as mock_er,
            patch(
                "custom_components.smartly_bridge.adapters.home_assistant.get_allowed_entities",
                return_value=["binary_sensor.presence"],
            ),
        ):
            primary_entry = MagicMock()
            primary_entry.labels = {"smartly"}
            primary_entry.device_id = "zigbee-presence-1"
            trigger_entry = MagicMock()
            trigger_entry.labels = set()
            trigger_entry.device_id = "zigbee-presence-1"
            trigger_entry.entity_id = "number.presence_detection_delay"
            cooldown_entry = MagicMock()
            cooldown_entry.labels = set()
            cooldown_entry.device_id = "zigbee-presence-1"
            cooldown_entry.entity_id = "number.presence_cooldown"

            mock_registry = MagicMock()
            mock_registry.entities = {
                "binary_sensor.presence": primary_entry,
                "number.presence_detection_delay": trigger_entry,
                "number.presence_cooldown": cooldown_entry,
            }
            mock_registry.async_get.side_effect = lambda entity_id: {
                "binary_sensor.presence": primary_entry,
                "number.presence_detection_delay": trigger_entry,
                "number.presence_cooldown": cooldown_entry,
            }.get(entity_id)
            mock_er.return_value = mock_registry

            body = {
                "command_id": "cmd-setting-cooldown",
                "device_id": "ldev_zigbee_presence_1",
                "capability": "numeric_setting",
                "command": "set_value",
                "params": {"key": "cooldown_seconds", "value": 5},
                "source": {"user_id": "user-1"},
            }

            mock_request = MagicMock()
            mock_request.app = {"hass": mock_hass}
            mock_request.method = "POST"
            mock_request.path = API_PATH_CONTROL
            mock_request.json = AsyncMock(return_value=body)
            mock_request.transport = MagicMock()
            mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
            mock_request.headers = {}

            with patch(
                "custom_components.smartly_bridge.views.control.verify_request"
            ) as mock_verify:
                mock_verify.return_value = MagicMock(
                    success=True, client_id="test_client", error=None
                )

                response = await SmartlyControlView(mock_request).post()

        assert response.status == 200
        assert json.loads(response.body)["entity_id"] == "number.presence_cooldown"
        assert json.loads(response.body)["expected_state"] == {
            "numeric_setting": {"value": 5}
        }
        mock_hass.services.async_call.assert_awaited_once_with(
            "number",
            "set_value",
            {"entity_id": "number.presence_cooldown", "value": 5},
            blocking=True,
        )

        await nonce_cache.stop()

    @pytest.mark.asyncio
    async def test_control_vnext_option_setting_resolves_sibling_select_entity(
        self, mock_hass, mock_config_entry
    ):
        """API vNext option settings resolve editable sibling select entities."""
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

        presence_state = MagicMock()
        presence_state.state = "on"
        presence_state.attributes = {
            "friendly_name": "Presence Sensor",
            "device_class": "occupancy",
        }
        select_state = MagicMock()
        select_state.state = "low"
        select_state.attributes = {
            "friendly_name": "Occupancy sensitivity",
            "options": ["low", "medium", "high"],
        }
        mock_hass.states.get.side_effect = lambda entity_id: {
            "binary_sensor.presence": presence_state,
            "select.presence_occupancy_sensitivity": select_state,
        }.get(entity_id)

        from homeassistant.helpers import entity_registry as er

        with (
            patch.object(er, "async_get") as mock_er,
            patch(
                "custom_components.smartly_bridge.adapters.home_assistant.get_allowed_entities",
                return_value=["binary_sensor.presence"],
            ),
        ):
            primary_entry = MagicMock()
            primary_entry.labels = {"smartly"}
            primary_entry.device_id = "zigbee-presence-1"
            setting_entry = MagicMock()
            setting_entry.labels = set()
            setting_entry.device_id = "zigbee-presence-1"
            setting_entry.entity_id = "select.presence_occupancy_sensitivity"

            mock_registry = MagicMock()
            mock_registry.entities = {
                "binary_sensor.presence": primary_entry,
                "select.presence_occupancy_sensitivity": setting_entry,
            }
            mock_registry.async_get.side_effect = lambda entity_id: {
                "binary_sensor.presence": primary_entry,
                "select.presence_occupancy_sensitivity": setting_entry,
            }.get(entity_id)
            mock_er.return_value = mock_registry

            body = {
                "command_id": "cmd-setting-sensitivity",
                "device_id": "ldev_zigbee_presence_1",
                "capability": "option_setting",
                "command": "select_option",
                "params": {"option": "medium"},
                "source": {"user_id": "user-1"},
            }

            mock_request = MagicMock()
            mock_request.app = {"hass": mock_hass}
            mock_request.method = "POST"
            mock_request.path = API_PATH_CONTROL
            mock_request.json = AsyncMock(return_value=body)
            mock_request.transport = MagicMock()
            mock_request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
            mock_request.headers = {}

            with patch(
                "custom_components.smartly_bridge.views.control.verify_request"
            ) as mock_verify:
                mock_verify.return_value = MagicMock(
                    success=True, client_id="test_client", error=None
                )

                response = await SmartlyControlView(mock_request).post()

        assert response.status == 200
        assert json.loads(response.body)["entity_id"] == (
            "select.presence_occupancy_sensitivity"
        )
        assert json.loads(response.body)["expected_state"] == {
            "option_setting": {"value": "medium"}
        }
        mock_hass.services.async_call.assert_awaited_once_with(
            "select",
            "select_option",
            {"entity_id": "select.presence_occupancy_sensitivity", "option": "medium"},
            blocking=True,
        )

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

    def test_signal_quality_aliases(self):
        """Test signal quality attributes are normalized for Platform."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "linkquality": 236,
            "friendly_name": "Temperature Sensor",
        }

        result = format_numeric_attributes(attrs)

        assert result["linkquality"] == 236
        assert result["signal_strength"] == 236
        assert result["signal_unit"] == "lqi"

    def test_rssi_signal_alias(self):
        """Test RSSI is exposed through the normalized signal attribute."""
        from custom_components.smartly_bridge.utils import format_numeric_attributes

        attrs = {
            "rssi": -58,
            "friendly_name": "Wi-Fi Sensor",
        }

        result = format_numeric_attributes(attrs)

        assert result["rssi"] == -58
        assert result["signal_strength"] == -58
        assert result["signal_unit"] == "dBm"

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
