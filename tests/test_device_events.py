"""Tests for Smartly stateless device event ingestion."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
from custom_components.smartly_bridge.const import API_PATH_DEVICE_EVENTS, DOMAIN
from custom_components.smartly_bridge.views.device_events import SmartlyDeviceEventsView


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
        assert "received_at" in payload
        mock_hass.bus.async_fire.assert_called_once()
        event_type, event_data = mock_hass.bus.async_fire.call_args.args
        assert event_type == "smartly_bridge_device_event"
        assert event_data["device_id"] == "device_abc123"
        assert event_data["action"] == "single_left"
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
