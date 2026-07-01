"""Tests for local automation rule management endpoints."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
from custom_components.smartly_bridge.application.local_automation import (
    AutomationAction,
    AutomationTrigger,
    LocalAutomationRule,
)
from custom_components.smartly_bridge.const import API_PATH_LOCAL_AUTOMATION_RULES, DOMAIN
from custom_components.smartly_bridge.views.local_automation import (
    SmartlyLocalAutomationRulesView,
)


def _request_for_rules(
    mock_hass: MagicMock,
    body: dict | None = None,
    *,
    method: str | None = None,
) -> MagicMock:
    body = body or {}
    request = MagicMock()
    request.app = {"hass": mock_hass}
    request.headers = {
        "X-Client-Id": "test_client",
        "X-Timestamp": "0",
        "X-Nonce": "nonce",
        "X-Signature": "sig",
    }
    request.method = method or ("POST" if body else "GET")
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


class FakeLocalAutomationRuleStore:
    """Rule store used to verify setup-created runtime adapter wiring."""

    def __init__(self) -> None:
        self.list_calls = 0
        self.created_rules: list[LocalAutomationRule] = []

    def list_rules(self) -> list[LocalAutomationRule]:
        """Return configured local automation rules."""
        self.list_calls += 1
        return [
            LocalAutomationRule(
                rule_id="runtime-left-single",
                trigger=AutomationTrigger(
                    device_id="ldev_runtime_button",
                    capability="button_event",
                    event="single_press",
                    payload={"button": "left"},
                ),
                actions=[
                    AutomationAction(
                        type="device_command",
                        device_id="ldev_runtime_light",
                        capability="power",
                        command="turn_on",
                    )
                ],
            )
        ]

    def create_rule(self, rule: LocalAutomationRule) -> bool:
        """Persist a new rule."""
        self.created_rules.append(rule)
        return True

    def update_rule(self, rule: LocalAutomationRule) -> bool:
        """Replace a rule."""
        return True

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule."""
        return True


def test_list_local_automation_rules_reads_store_payload() -> None:
    """Local automation list invocation adapter reads the rule store."""
    from custom_components.smartly_bridge.views.local_automation import (
        _list_local_automation_rules,
    )

    store = FakeLocalAutomationRuleStore()

    result = _list_local_automation_rules(store)

    assert result.status == 200
    assert store.list_calls == 1
    assert result.body["count"] == 1
    assert result.body["rules"][0]["rule_id"] == "runtime-left-single"
    assert result.body["data"]["rules"][0]["trigger"]["device_id"] == (
        "ldev_runtime_button"
    )


def test_create_local_automation_rule_forwards_payload_to_store() -> None:
    """Local automation create invocation adapter forwards canonical payload."""
    from custom_components.smartly_bridge.views.local_automation import (
        _create_local_automation_rule,
    )

    store = FakeLocalAutomationRuleStore()
    payload = {
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
    }

    result = _create_local_automation_rule(store, payload)

    assert result.status == 201
    assert result.body["status"] == "created"
    assert result.body["rule_id"] == "new-left-double"
    assert len(store.created_rules) == 1
    assert store.created_rules[0].trigger.event == "double_press"
    assert store.created_rules[0].actions[0].command == "turn_off"


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
async def test_local_automation_rules_get_uses_setup_runtime_rule_store(
    mock_hass,
) -> None:
    """GET local automation rules reads through setup-created runtime adapters."""
    _configure_integration(mock_hass)
    store = FakeLocalAutomationRuleStore()
    mock_hass.data[DOMAIN]["runtime_adapters"] = {
        "local_automation_rule_store": store,
    }
    request = _request_for_rules(mock_hass)

    with patch(
        "custom_components.smartly_bridge.views.local_automation.verify_request"
    ) as mock_verify, patch(
        "custom_components.smartly_bridge.views.local_automation.HomeAssistantLocalAutomationRuleStore"
    ) as mock_store:
        mock_verify.return_value = MagicMock(
            success=True,
            client_id="test_client",
            error=None,
        )

        response = await SmartlyLocalAutomationRulesView(request).get()

    assert response.status == 200
    mock_store.assert_not_called()
    payload = json.loads(response.body)
    assert store.list_calls == 1
    assert payload["rules"][0]["rule_id"] == "runtime-left-single"
    assert payload["rules"][0]["trigger"]["device_id"] == "ldev_runtime_button"


@pytest.mark.asyncio
async def test_local_automation_rules_get_echoes_request_correlation_headers(
    mock_hass,
) -> None:
    """GET local automation rules exposes request/correlation IDs."""
    _configure_integration(mock_hass)
    store = FakeLocalAutomationRuleStore()
    mock_hass.data[DOMAIN]["runtime_adapters"] = {
        "local_automation_rule_store": store,
    }
    request = _request_for_rules(mock_hass)
    request.headers.update(
        {
            "X-Request-Id": "req-local-rules-1",
            "X-Correlation-Id": "corr-local-rules-1",
        }
    )

    with patch(
        "custom_components.smartly_bridge.views.local_automation.verify_request"
    ) as mock_verify:
        mock_verify.return_value = MagicMock(
            success=True,
            client_id="test_client",
            error=None,
        )

        response = await SmartlyLocalAutomationRulesView(request).get()

    assert response.status == 200
    payload = json.loads(response.body)
    assert payload["request_id"] == "req-local-rules-1"
    assert payload["correlation_id"] == "corr-local-rules-1"


@pytest.mark.asyncio
async def test_local_automation_rules_get_not_configured_uses_vnext_error(
    mock_hass,
) -> None:
    """GET local automation rules returns API vNext error when unconfigured."""
    mock_hass.data = {}
    request = _request_for_rules(mock_hass)

    response = await SmartlyLocalAutomationRulesView(request).get()

    assert response.status == 500
    assert json.loads(response.body) == {
        "error": "integration_not_configured",
        "message": "Smartly Bridge integration is not configured",
        "schema_version": "2026.06",
        "data": {
            "status": "rejected",
        },
        "warnings": [],
        "errors": [
            {
                "code": "integration_not_configured",
                "message": "Smartly Bridge integration is not configured",
                "target": "integration",
            }
        ],
    }


@pytest.mark.asyncio
async def test_local_automation_rules_get_auth_failure_uses_vnext_error(
    mock_hass,
) -> None:
    """GET local automation rules auth failure returns API vNext error."""
    _configure_integration(mock_hass)
    request = _request_for_rules(mock_hass)

    with patch(
        "custom_components.smartly_bridge.views.local_automation.verify_request"
    ) as mock_verify:
        mock_verify.return_value = MagicMock(
            success=False,
            client_id=None,
            error="invalid_signature",
        )

        response = await SmartlyLocalAutomationRulesView(request).get()

    assert response.status == 401
    assert json.loads(response.body) == {
        "error": "invalid_signature",
        "message": "Local automation rule request authentication failed",
        "schema_version": "2026.06",
        "data": {
            "status": "rejected",
        },
        "warnings": [],
        "errors": [
            {
                "code": "invalid_signature",
                "message": "Local automation rule request authentication failed",
                "target": "request.auth",
            }
        ],
    }


@pytest.mark.asyncio
async def test_local_automation_rules_get_rate_limit_uses_vnext_error(
    mock_hass,
) -> None:
    """GET local automation rules rate limit returns API vNext error."""
    _configure_integration(mock_hass)
    request = _request_for_rules(mock_hass)
    mock_hass.data[DOMAIN]["rate_limiter"] = MagicMock()
    mock_hass.data[DOMAIN]["rate_limiter"].check = AsyncMock(return_value=False)

    with patch(
        "custom_components.smartly_bridge.views.local_automation.verify_request"
    ) as mock_verify:
        mock_verify.return_value = MagicMock(
            success=True,
            client_id="test_client",
            error=None,
        )

        response = await SmartlyLocalAutomationRulesView(request).get()

    assert response.status == 429
    assert response.headers["Retry-After"] == "60"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert json.loads(response.body) == {
        "error": "rate_limited",
        "message": "Local automation rule request was rate limited",
        "schema_version": "2026.06",
        "data": {
            "status": "rejected",
        },
        "warnings": [],
        "errors": [
            {
                "code": "rate_limited",
                "message": "Local automation rule request was rate limited",
                "target": "request.rate_limit",
            }
        ],
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


@pytest.mark.parametrize(
    ("method_name", "http_method"),
    [
        ("post", "POST"),
        ("put", "PUT"),
        ("delete", "DELETE"),
    ],
)
@pytest.mark.asyncio
async def test_local_automation_rules_invalid_json_uses_vnext_error(
    mock_hass,
    method_name: str,
    http_method: str,
) -> None:
    """Mutating local automation rules invalid JSON returns API vNext error."""
    _configure_integration(mock_hass)
    request = _request_for_rules(mock_hass, method=http_method)
    request.json = AsyncMock(side_effect=json.JSONDecodeError("bad json", "{", 0))

    with patch(
        "custom_components.smartly_bridge.views.local_automation.verify_request"
    ) as mock_verify:
        mock_verify.return_value = MagicMock(
            success=True,
            client_id="test_client",
            error=None,
        )

        view = SmartlyLocalAutomationRulesView(request)
        response = await getattr(view, method_name)()

    assert response.status == 400
    assert json.loads(response.body) == {
        "error": "invalid_json",
        "message": "Request body must be valid JSON",
        "schema_version": "2026.06",
        "data": {
            "status": "rejected",
        },
        "warnings": [],
        "errors": [
            {
                "code": "invalid_json",
                "message": "Request body must be valid JSON",
                "target": "request.body",
            }
        ],
    }


@pytest.mark.asyncio
async def test_local_automation_rules_put_updates_stored_rule(mock_hass) -> None:
    """PUT local automation rules updates an existing canonical rule."""
    _configure_integration(mock_hass)
    request = _request_for_rules(
        mock_hass,
        {
            "rule_id": "stored-left-single",
            "enabled": False,
            "trigger": {
                "device_id": "ldev_button",
                "capability": "button_event",
                "event": "double_press",
                "payload": {"button": "right"},
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
        method="PUT",
    )

    with patch(
        "custom_components.smartly_bridge.views.local_automation.verify_request"
    ) as mock_verify:
        mock_verify.return_value = MagicMock(
            success=True,
            client_id="test_client",
            error=None,
        )

        response = await SmartlyLocalAutomationRulesView(request).put()

    assert response.status == 200
    payload = json.loads(response.body)
    assert payload["success"] is True
    assert payload["status"] == "updated"
    assert payload["rule_id"] == "stored-left-single"
    assert payload["data"]["rule"]["enabled"] is False
    assert payload["data"]["rule"]["trigger"] == {
        "device_id": "ldev_button",
        "capability": "button_event",
        "event": "double_press",
        "payload": {"button": "right"},
    }
    mock_hass.config_entries.async_update_entry.assert_called_once()


@pytest.mark.asyncio
async def test_local_automation_rules_delete_removes_stored_rule(mock_hass) -> None:
    """DELETE local automation rules removes an existing canonical rule."""
    _configure_integration(mock_hass)
    request = _request_for_rules(
        mock_hass,
        {"rule_id": "stored-left-single"},
        method="DELETE",
    )

    with patch(
        "custom_components.smartly_bridge.views.local_automation.verify_request"
    ) as mock_verify:
        mock_verify.return_value = MagicMock(
            success=True,
            client_id="test_client",
            error=None,
        )

        response = await SmartlyLocalAutomationRulesView(request).delete()

    assert response.status == 200
    payload = json.loads(response.body)
    assert payload == {
        "success": True,
        "schema_version": "2026.06",
        "status": "deleted",
        "rule_id": "stored-left-single",
        "data": {
            "status": "deleted",
            "rule_id": "stored-left-single",
        },
        "warnings": [],
        "errors": [],
    }
    mock_hass.config_entries.async_update_entry.assert_called_once()
