"""Tests for local automation rule management endpoints."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
from custom_components.smartly_bridge.const import API_PATH_LOCAL_AUTOMATION_RULES, DOMAIN
from custom_components.smartly_bridge.views.local_automation import (
    SmartlyLocalAutomationRulesView,
)


def _request_for_rules(mock_hass: MagicMock, body: dict | None = None) -> MagicMock:
    body = body or {}
    request = MagicMock()
    request.app = {"hass": mock_hass}
    request.headers = {
        "X-Client-Id": "test_client",
        "X-Timestamp": "0",
        "X-Nonce": "nonce",
        "X-Signature": "sig",
    }
    request.method = "POST" if body else "GET"
    request.path = API_PATH_LOCAL_AUTOMATION_RULES
    request.match_info = {}
    request.json = AsyncMock(return_value=body)
    request.read = AsyncMock(return_value=json.dumps(body).encode() if body else b"")
    request.transport = MagicMock()
    request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
    return request


def _configure_integration(mock_hass: MagicMock) -> None:
    mock_hass.data[DOMAIN] = {
        "config_entry": MagicMock(
            data={
                "client_secret": "test_secret",
                "allowed_cidrs": "",
                "local_automation_rules": [
                    {
                        "rule_id": "stored-left-single",
                        "trigger": {
                            "device_id": "ldev_button",
                            "capability": "button_event",
                            "event": "single_press",
                            "payload": {"button": "left"},
                        },
                        "actions": [
                            {
                                "type": "device_command",
                                "device_id": "ldev_light",
                                "capability": "power",
                                "command": "turn_on",
                            }
                        ],
                    }
                ],
            }
        ),
        "nonce_cache": NonceCache(),
        "rate_limiter": RateLimiter(60, 60),
    }


@pytest.mark.asyncio
async def test_local_automation_rules_get_lists_stored_rules(mock_hass) -> None:
    """GET local automation rules returns stored canonical rules."""
    _configure_integration(mock_hass)
    request = _request_for_rules(mock_hass)

    with patch(
        "custom_components.smartly_bridge.views.local_automation.verify_request"
    ) as mock_verify:
        mock_verify.return_value = MagicMock(
            success=True,
            client_id="test_client",
            error=None,
        )

        response = await SmartlyLocalAutomationRulesView(request).get()

    expected_rule = {
        "rule_id": "stored-left-single",
        "enabled": True,
        "trigger": {
            "device_id": "ldev_button",
            "capability": "button_event",
            "event": "single_press",
            "payload": {"button": "left"},
        },
        "actions": [
            {
                "type": "device_command",
                "device_id": "ldev_light",
                "capability": "power",
                "command": "turn_on",
                "params": {},
            }
        ],
    }
    assert response.status == 200
    payload = json.loads(response.body)
    assert payload == {
        "success": True,
        "schema_version": "2026.06",
        "rules": [expected_rule],
        "count": 1,
        "data": {
            "rules": [expected_rule],
            "count": 1,
        },
        "warnings": [],
        "errors": [],
    }


@pytest.mark.asyncio
async def test_local_automation_rules_post_creates_stored_rule(mock_hass) -> None:
    """POST local automation rules persists a canonical rule."""
    _configure_integration(mock_hass)
    request = _request_for_rules(
        mock_hass,
        {
            "rule_id": "new-left-double",
            "trigger": {
                "device_id": "ldev_button",
                "capability": "button_event",
                "event": "double_press",
                "payload": {"button": "left"},
            },
            "actions": [
                {
                    "type": "device_command",
                    "device_id": "ldev_light",
                    "capability": "power",
                    "command": "turn_off",
                }
            ],
        },
    )

    with patch(
        "custom_components.smartly_bridge.views.local_automation.verify_request"
    ) as mock_verify:
        mock_verify.return_value = MagicMock(
            success=True,
            client_id="test_client",
            error=None,
        )

        response = await SmartlyLocalAutomationRulesView(request).post()

    assert response.status == 201
    payload = json.loads(response.body)
    assert payload["success"] is True
    assert payload["status"] == "created"
    assert payload["rule_id"] == "new-left-double"
    assert payload["data"]["rule"]["trigger"] == {
        "device_id": "ldev_button",
        "capability": "button_event",
        "event": "double_press",
        "payload": {"button": "left"},
    }
    mock_hass.config_entries.async_update_entry.assert_called_once()
