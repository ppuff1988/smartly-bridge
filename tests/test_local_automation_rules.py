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
from custom_components.smartly_bridge.adapters.home_assistant import (
    _home_assistant_local_automation_rule_store,
)
from custom_components.smartly_bridge.const import API_PATH_LOCAL_AUTOMATION_RULES, DOMAIN
from custom_components.smartly_bridge.domain.models import BridgeResponse
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
    mock_hass.data[DOMAIN]["runtime_adapters"] = {
        "local_automation_rule_store": _home_assistant_local_automation_rule_store(
            mock_hass
        ),
    }


class FakeLocalAutomationRuleStore:
    """Rule store used to verify setup-created runtime adapter wiring."""

    def __init__(self) -> None:
        self.list_calls = 0
        self.created_rules: list[LocalAutomationRule] = []
        self.updated_rules: list[LocalAutomationRule] = []
        self.deleted_rule_ids: list[str] = []

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
        self.updated_rules.append(rule)
        return True

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule."""
        self.deleted_rule_ids.append(rule_id)
        return True


class FakeListRulesUseCase:
    """List rules use case used to verify invocation factory wiring."""

    def __init__(self) -> None:
        self.calls = 0

    def execute(self) -> BridgeResponse:
        """Record invocation and return a fixed response."""
        self.calls += 1
        return BridgeResponse(
            {
                "schema_version": "2026.06",
                "data": {
                    "rules": [{"rule_id": "factory-rule"}],
                    "count": 1,
                },
                "warnings": [],
                "errors": [],
            },
            status=200,
        )


class FakeCreateRuleUseCase:
    """Create rule use case used to verify invocation factory wiring."""

    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def execute(self, payload: dict) -> BridgeResponse:
        """Record payload and return a fixed response."""
        self.payloads.append(payload)
        return BridgeResponse(
            {
                "schema_version": "2026.06",
                "data": {
                    "status": "created",
                    "rule_id": "factory-created",
                },
                "warnings": [],
                "errors": [],
            },
            status=201,
        )


class FakeUpdateRuleUseCase:
    """Update rule use case used to verify invocation factory wiring."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, rule_id: str, payload: dict) -> BridgeResponse:
        """Record rule ID/payload and return a fixed response."""
        self.calls.append((rule_id, payload))
        return BridgeResponse(
            {
                "schema_version": "2026.06",
                "data": {
                    "status": "updated",
                    "rule_id": "factory-updated",
                },
                "warnings": [],
                "errors": [],
            },
            status=200,
        )


class FakeDeleteRuleUseCase:
    """Delete rule use case used to verify invocation factory wiring."""

    def __init__(self) -> None:
        self.rule_ids: list[str] = []

    def execute(self, rule_id: str) -> BridgeResponse:
        """Record rule ID and return a fixed response."""
        self.rule_ids.append(rule_id)
        return BridgeResponse(
            {
                "schema_version": "2026.06",
                "data": {
                    "status": "deleted",
                    "rule_id": "factory-deleted",
                },
                "warnings": [],
                "errors": [],
            },
            status=200,
        )


def test_list_local_automation_rules_reads_store_payload() -> None:
    """Local automation list invocation adapter reads the rule store."""
    from custom_components.smartly_bridge.views.local_automation import (
        _list_local_automation_rules,
    )

    store = FakeLocalAutomationRuleStore()

    result = _list_local_automation_rules(store)

    assert result.status == 200
    assert store.list_calls == 1
    assert result.body["data"]["count"] == 1
    assert result.body["data"]["rules"][0]["rule_id"] == "runtime-left-single"
    assert result.body["data"]["rules"][0]["trigger"]["device_id"] == (
        "ldev_runtime_button"
    )


def test_list_local_automation_rules_uses_injected_use_case_factory() -> None:
    """Local automation list adapter accepts an injected use-case factory."""
    from custom_components.smartly_bridge.views.local_automation import (
        _list_local_automation_rules,
    )

    store = FakeLocalAutomationRuleStore()
    use_case = FakeListRulesUseCase()
    factory_calls = []

    def use_case_factory(received_store):
        factory_calls.append(received_store)
        return use_case

    result = _list_local_automation_rules(
        store,
        use_case_factory=use_case_factory,
    )

    assert result.status == 200
    assert factory_calls == [store]
    assert use_case.calls == 1
    assert result.body["data"]["rules"] == [{"rule_id": "factory-rule"}]


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
    assert result.body["data"]["status"] == "created"
    assert result.body["data"]["rule_id"] == "new-left-double"
    assert len(store.created_rules) == 1
    assert store.created_rules[0].trigger.event == "double_press"
    assert store.created_rules[0].actions[0].command == "turn_off"


def test_create_local_automation_rule_uses_injected_use_case_factory() -> None:
    """Local automation create adapter accepts an injected use-case factory."""
    from custom_components.smartly_bridge.views.local_automation import (
        _create_local_automation_rule,
    )

    store = FakeLocalAutomationRuleStore()
    use_case = FakeCreateRuleUseCase()
    factory_calls = []
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

    def use_case_factory(received_store):
        factory_calls.append(received_store)
        return use_case

    result = _create_local_automation_rule(
        store,
        payload,
        use_case_factory=use_case_factory,
    )

    assert result.status == 201
    assert factory_calls == [store]
    assert use_case.payloads == [payload]
    assert result.body["data"]["rule_id"] == "factory-created"


def test_update_local_automation_rule_forwards_payload_to_store() -> None:
    """Local automation update invocation adapter forwards canonical payload."""
    from custom_components.smartly_bridge.views.local_automation import (
        _update_local_automation_rule,
    )

    store = FakeLocalAutomationRuleStore()
    payload = {
        "rule_id": "runtime-left-single",
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
    }

    result = _update_local_automation_rule(store, "runtime-left-single", payload)

    assert result.status == 200
    assert result.body["data"]["status"] == "updated"
    assert result.body["data"]["rule_id"] == "runtime-left-single"
    assert len(store.updated_rules) == 1
    assert store.updated_rules[0].enabled is False
    assert store.updated_rules[0].trigger.event == "double_press"
    assert store.updated_rules[0].actions[0].command == "turn_off"


def test_update_local_automation_rule_uses_injected_use_case_factory() -> None:
    """Local automation update adapter accepts an injected use-case factory."""
    from custom_components.smartly_bridge.views.local_automation import (
        _update_local_automation_rule,
    )

    store = FakeLocalAutomationRuleStore()
    use_case = FakeUpdateRuleUseCase()
    factory_calls = []
    payload = {
        "rule_id": "runtime-left-single",
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
    }

    def use_case_factory(received_store):
        factory_calls.append(received_store)
        return use_case

    result = _update_local_automation_rule(
        store,
        "runtime-left-single",
        payload,
        use_case_factory=use_case_factory,
    )

    assert result.status == 200
    assert factory_calls == [store]
    assert use_case.calls == [("runtime-left-single", payload)]
    assert result.body["data"]["rule_id"] == "factory-updated"


def test_delete_local_automation_rule_forwards_rule_id_to_store() -> None:
    """Local automation delete invocation adapter forwards canonical rule ID."""
    from custom_components.smartly_bridge.views.local_automation import (
        _delete_local_automation_rule,
    )

    store = FakeLocalAutomationRuleStore()

    result = _delete_local_automation_rule(store, "runtime-left-single")

    assert result.status == 200
    assert result.body["data"]["status"] == "deleted"
    assert result.body["data"]["rule_id"] == "runtime-left-single"
    assert store.deleted_rule_ids == ["runtime-left-single"]


def test_delete_local_automation_rule_uses_injected_use_case_factory() -> None:
    """Local automation delete adapter accepts an injected use-case factory."""
    from custom_components.smartly_bridge.views.local_automation import (
        _delete_local_automation_rule,
    )

    store = FakeLocalAutomationRuleStore()
    use_case = FakeDeleteRuleUseCase()
    factory_calls = []

    def use_case_factory(received_store):
        factory_calls.append(received_store)
        return use_case

    result = _delete_local_automation_rule(
        store,
        "runtime-left-single",
        use_case_factory=use_case_factory,
    )

    assert result.status == 200
    assert factory_calls == [store]
    assert use_case.rule_ids == ["runtime-left-single"]
    assert result.body["data"]["rule_id"] == "factory-deleted"


def test_local_automation_rule_store_resolver_uses_runtime_store(mock_hass) -> None:
    """Local automation rule store resolver returns the setup-created runtime port."""
    from custom_components.smartly_bridge.views.local_automation import (
        _local_automation_rule_store,
    )

    _configure_integration(mock_hass)
    store = FakeLocalAutomationRuleStore()
    mock_hass.data[DOMAIN]["runtime_adapters"] = {
        "local_automation_rule_store": store,
    }

    result = _local_automation_rule_store(mock_hass)

    assert result is store


def test_local_automation_rule_store_resolver_requires_runtime_store(
    mock_hass,
) -> None:
    """Local automation rule store resolver does not create a fallback."""
    from custom_components.smartly_bridge.views.local_automation import (
        _local_automation_rule_store,
    )

    _configure_integration(mock_hass)
    mock_hass.data[DOMAIN]["runtime_adapters"] = {}

    result = _local_automation_rule_store(mock_hass)

    assert (
        "local_automation_rule_store"
        not in mock_hass.data[DOMAIN]["runtime_adapters"]
    )
    assert result is None


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
        "schema_version": "2026.06",
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
    ) as mock_verify:
        mock_verify.return_value = MagicMock(
            success=True,
            client_id="test_client",
            error=None,
        )

        response = await SmartlyLocalAutomationRulesView(request).get()

    assert response.status == 200
    payload = json.loads(response.body)
    assert store.list_calls == 1
    assert payload["data"]["rules"][0]["rule_id"] == "runtime-left-single"
    assert payload["data"]["rules"][0]["trigger"]["device_id"] == (
        "ldev_runtime_button"
    )


@pytest.mark.asyncio
async def test_local_automation_rules_get_requires_setup_runtime_rule_store(
    mock_hass,
) -> None:
    """GET local automation rules fails when setup did not create the rule store."""
    _configure_integration(mock_hass)
    mock_hass.data[DOMAIN]["runtime_adapters"] = {}
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

    assert response.status == 500
    assert json.loads(response.body) == {
        "schema_version": "2026.06",
        "data": {
            "status": "rejected",
        },
        "warnings": [],
        "errors": [
            {
                "code": "local_automation_rule_store_unavailable",
                "message": "Local automation rule store not initialized",
                "target": "local_automation.rule_store",
            }
        ],
    }
    assert (
        "local_automation_rule_store"
        not in mock_hass.data[DOMAIN]["runtime_adapters"]
    )


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
    assert set(payload) == {"schema_version", "data", "warnings", "errors"}
    assert payload["data"]["status"] == "created"
    assert payload["data"]["rule_id"] == "new-left-double"
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
    assert set(payload) == {"schema_version", "data", "warnings", "errors"}
    assert payload["data"]["status"] == "updated"
    assert payload["data"]["rule_id"] == "stored-left-single"
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
        "schema_version": "2026.06",
        "data": {
            "status": "deleted",
            "rule_id": "stored-left-single",
        },
        "warnings": [],
        "errors": [],
    }
    mock_hass.config_entries.async_update_entry.assert_called_once()
