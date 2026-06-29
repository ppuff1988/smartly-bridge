"""Tests for Smartly stateless device event ingestion."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
from custom_components.smartly_bridge.const import API_PATH_DEVICE_EVENTS, DOMAIN
from custom_components.smartly_bridge.views.device_events import (
    SmartlyDeviceEventsView,
    SmartlyDeviceEventsViewWrapper,
)


def _request_for_device_event(
    mock_hass: MagicMock,
    body: dict,
    device_id: str = "device_abc123",
) -> MagicMock:
    request = MagicMock()
    request.app = {"hass": mock_hass}
    request.headers = {
        "X-Client-Id": "test_client",
        "X-Timestamp": "0",
        "X-Nonce": "nonce",
        "X-Signature": "sig",
    }
    request.method = "POST"
    request.path = API_PATH_DEVICE_EVENTS.format(device_id=device_id)
    request.match_info = {"device_id": device_id}
    request.json = AsyncMock(return_value=body)
    request.read = AsyncMock(return_value=json.dumps(body).encode())
    request.transport = MagicMock()
    request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
    return request


def _configure_integration(mock_hass: MagicMock) -> None:
    mock_hass.data[DOMAIN] = {
        "config_entry": MagicMock(
            data={
                "client_secret": "test_secret",
                "allowed_cidrs": "",
            }
        ),
        "nonce_cache": NonceCache(),
        "rate_limiter": RateLimiter(60, 60),
    }


class TestDeviceEventsEndpoint:
    """Tests for /api/smartly/devices/{device_id}/events endpoint."""

    @pytest.mark.asyncio
    async def test_device_event_accepts_button_action_and_fires_ha_event(self, mock_hass):
        """Valid button actions are accepted and emitted on the HA event bus."""
        _configure_integration(mock_hass)
        body = {
            "type": "button_action",
            "action": "single_left",
            "timestamp": "2026-06-27T10:20:00.000Z",
            "meta": {
                "source": "zigbee2mqtt",
                "model": "aqara_d1_double",
                "endpoint": "left",
                "linkquality": 128,
            },
        }
        request = _request_for_device_event(mock_hass, body)

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client", error=None)

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 202
        payload = json.loads(response.body)
        assert payload["success"] is True
        assert payload["device_id"] == "device_abc123"
        assert payload["action"] == "single_left"
        assert payload["event_id"].startswith("evt_")
        assert payload["capability"] == "button_event"
        assert payload["event"] == "single_press"
        assert payload["payload"] == {"button": "left"}
        assert payload["events"] == [
            {
                "event_id": payload["event_id"],
                "device_id": "device_abc123",
                "capability": "button_event",
                "event": "single_press",
                "payload": {"button": "left"},
                "occurred_at": "2026-06-27T10:20:00.000Z",
            }
        ]
        assert "received_at" in payload
        mock_hass.bus.async_fire.assert_called_once()
        event_type, event_data = mock_hass.bus.async_fire.call_args.args
        assert event_type == "smartly_bridge_device_event"
        assert event_data["device_id"] == "device_abc123"
        assert event_data["action"] == "single_left"
        assert event_data["capability"] == "button_event"
        assert event_data["event"] == "single_press"
        assert event_data["payload"] == {"button": "left"}
        assert event_data["meta"]["endpoint"] == "left"

    @pytest.mark.asyncio
    async def test_device_event_rejects_unsupported_action(self, mock_hass):
        """Unsupported button actions are rejected before automation dispatch."""
        _configure_integration(mock_hass)
        request = _request_for_device_event(
            mock_hass,
            {
                "type": "button_action",
                "action": "triple_left",
                "timestamp": "2026-06-27T10:20:00.000Z",
            },
        )

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client", error=None)

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 400
        assert json.loads(response.body)["error"] == "invalid_action"
        mock_hass.bus.async_fire.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_event_invalid_action_response_includes_vnext_error_envelope(
        self,
        mock_hass,
    ):
        """HTTP invalid action responses expose API vNext error envelope fields."""
        _configure_integration(mock_hass)
        request = _request_for_device_event(
            mock_hass,
            {
                "type": "button_action",
                "action": "triple_left",
                "timestamp": "2026-06-27T10:20:00.000Z",
            },
        )

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client", error=None)

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 400
        assert json.loads(response.body) == {
            "error": "invalid_action",
            "message": "Unsupported button action",
            "schema_version": "2026.06",
            "data": {
                "device_id": "device_abc123",
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": "INVALID_ACTION",
                    "message": "Unsupported button action",
                    "target": "event.action",
                    "retryable": False,
                }
            ],
        }
        mock_hass.bus.async_fire.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_event_invalid_timestamp_response_includes_vnext_error_envelope(
        self,
        mock_hass,
    ):
        """HTTP invalid timestamp responses expose API vNext error envelope fields."""
        _configure_integration(mock_hass)
        request = _request_for_device_event(
            mock_hass,
            {
                "type": "button_action",
                "action": "single_left",
                "timestamp": "not-a-timestamp",
            },
        )

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client", error=None)

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 400
        assert json.loads(response.body) == {
            "error": "invalid_timestamp",
            "message": "Invalid event timestamp",
            "schema_version": "2026.06",
            "data": {
                "device_id": "device_abc123",
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": "INVALID_TIMESTAMP",
                    "message": "Invalid event timestamp",
                    "target": "event.timestamp",
                    "retryable": False,
                }
            ],
        }
        mock_hass.bus.async_fire.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_event_invalid_meta_response_includes_vnext_error_envelope(
        self,
        mock_hass,
    ):
        """HTTP invalid meta responses expose API vNext error envelope fields."""
        _configure_integration(mock_hass)
        request = _request_for_device_event(
            mock_hass,
            {
                "type": "button_action",
                "action": "single_left",
                "timestamp": "2026-06-27T10:20:00.000Z",
                "meta": ["not", "an", "object"],
            },
        )

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client", error=None)

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 400
        assert json.loads(response.body) == {
            "error": "invalid_meta",
            "message": "Invalid event metadata",
            "schema_version": "2026.06",
            "data": {
                "device_id": "device_abc123",
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": "INVALID_META",
                    "message": "Invalid event metadata",
                    "target": "event.meta",
                    "retryable": False,
                }
            ],
        }
        mock_hass.bus.async_fire.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_event_accepts_button_action_alias_format(self, mock_hass):
        """Button-action aliases are accepted by the HTTP ingestion path."""
        _configure_integration(mock_hass)
        request = _request_for_device_event(
            mock_hass,
            {
                "type": "button_action",
                "action": "left_single",
                "timestamp": "2026-06-27T10:20:00.000Z",
            },
        )

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client", error=None)

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 202
        payload = json.loads(response.body)
        assert payload["event"] == "single_press"
        assert payload["payload"] == {"button": "left"}
        mock_hass.bus.async_fire.assert_called_once()

    @pytest.mark.asyncio
    async def test_device_event_duplicate_reuses_event_id_without_refiring(self, mock_hass):
        """Repeated canonical events are idempotent within the integration runtime."""
        _configure_integration(mock_hass)
        body = {
            "type": "button_action",
            "action": "single_left",
            "timestamp": "2026-06-27T10:20:00.000Z",
        }

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client", error=None)

            first = await SmartlyDeviceEventsView(
                _request_for_device_event(mock_hass, body)
            ).post()
            second = await SmartlyDeviceEventsView(
                _request_for_device_event(mock_hass, body)
            ).post()

        assert first.status == 202
        first_payload = json.loads(first.body)
        assert second.status == 200
        second_payload = json.loads(second.body)
        assert second_payload["duplicate"] is True
        assert second_payload["event_id"] == first_payload["event_id"]
        assert second_payload["events"][0]["event_id"] == first_payload["event_id"]
        mock_hass.bus.async_fire.assert_called_once()

    @pytest.mark.asyncio
    async def test_device_event_returns_json_error_when_dispatch_fails(self, mock_hass):
        """Unexpected dispatch failures return a structured JSON error."""
        _configure_integration(mock_hass)
        mock_hass.bus.async_fire.side_effect = RuntimeError("event bus unavailable")
        request = _request_for_device_event(
            mock_hass,
            {
                "type": "button_action",
                "action": "single_left",
                "timestamp": "2026-06-27T10:20:00.000Z",
            },
        )

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client", error=None)

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 500
        assert json.loads(response.body)["error"] == "device_event_failed"

    @pytest.mark.asyncio
    async def test_device_event_wrapper_accepts_route_device_id(self, mock_hass):
        """Home Assistant passes route variables as keyword arguments to view wrappers."""
        _configure_integration(mock_hass)
        request = _request_for_device_event(
            mock_hass,
            {
                "type": "button_action",
                "action": "single_left",
                "timestamp": "2026-06-27T10:20:00.000Z",
            },
        )

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client", error=None)

            response = await SmartlyDeviceEventsViewWrapper().post(
                request,
                device_id="device_abc123",
            )

        assert response.status == 202
