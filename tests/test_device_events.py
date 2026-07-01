"""Tests for Smartly stateless device event ingestion."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
from custom_components.smartly_bridge.application.device_events import DeviceEventCommand
from custom_components.smartly_bridge.application.local_automation import (
    AutomationAction,
    AutomationTrigger,
    LocalAutomationRule,
)
from custom_components.smartly_bridge.adapters.home_assistant import (
    HomeAssistantDeviceEventPublisher,
    InMemoryDeviceEventDeduplicator,
    _home_assistant_device_event_publisher,
    _home_assistant_local_automation_rule_store,
    _home_assistant_smartly_command_executor,
    _in_memory_device_event_deduplicator,
)
from custom_components.smartly_bridge.const import API_PATH_DEVICE_EVENTS, DOMAIN
from custom_components.smartly_bridge.domain.models import BridgeResponse
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
    mock_hass.data[DOMAIN]["runtime_adapters"] = {
        "device_event_publisher": _home_assistant_device_event_publisher(mock_hass),
        "device_event_deduplicator": _in_memory_device_event_deduplicator(),
    }


def _configure_local_automation_runtime(mock_hass: MagicMock) -> None:
    """Add setup-created local automation adapters to the test integration."""
    mock_hass.data[DOMAIN]["runtime_adapters"].update(
        {
            "local_automation_rule_store": _home_assistant_local_automation_rule_store(
                mock_hass
            ),
            "smartly_command_executor": _home_assistant_smartly_command_executor(
                mock_hass,
                MagicMock(),
            ),
        }
    )


class FakeDeviceEventPublisher:
    """Device event publisher used to verify runtime adapter wiring."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish_device_event(self, event_data: dict) -> None:
        """Record a canonical device event."""
        self.events.append(event_data)


class FakeLocalAutomationRuleStore:
    """Rule store used to verify runtime adapter automation wiring."""

    def __init__(self, rules: list[LocalAutomationRule]) -> None:
        self._rules = rules
        self.list_calls = 0

    def list_rules(self) -> list[LocalAutomationRule]:
        """Return configured local automation rules."""
        self.list_calls += 1
        return self._rules


class FakeSmartlyCommandExecutor:
    """Smartly command executor used to verify automation dispatch."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def execute(self, client_id: str, command: object) -> BridgeResponse:
        """Record an automation command execution."""
        self.calls.append((client_id, command))
        return BridgeResponse(
            {
                "success": True,
                "status": "completed",
            },
            status=200,
        )


class FakeLocalAutomationUseCase:
    """Local automation use case used to verify assembly factory wiring."""

    def __init__(self, rule_store: object, command_executor: object) -> None:
        self.rule_store = rule_store
        self.command_executor = command_executor


class FakeDeviceEventUseCase:
    """Device event use case used to verify invocation factory wiring."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, DeviceEventCommand]] = []

    async def execute(self, client_id: str, command: DeviceEventCommand) -> BridgeResponse:
        """Record invocation and return a fixed event response."""
        self.calls.append((client_id, command))
        return BridgeResponse(
            {
                "schema_version": "2026.06",
                "data": {
                    "device_id": command.device_id,
                    "action": command.action,
                },
                "warnings": [],
                "errors": [],
            },
            status=202,
        )


def test_home_assistant_device_event_publisher_factory_builds_legacy_publisher() -> None:
    """Device event publisher factory centralizes legacy HA event bus wiring."""
    hass = MagicMock()

    publisher = _home_assistant_device_event_publisher(hass)

    assert isinstance(publisher, HomeAssistantDeviceEventPublisher)


def test_in_memory_device_event_deduplicator_factory_builds_legacy_deduplicator() -> None:
    """Device event deduplicator factory centralizes legacy in-memory dedupe wiring."""
    deduplicator = _in_memory_device_event_deduplicator()

    assert isinstance(deduplicator, InMemoryDeviceEventDeduplicator)


@pytest.mark.asyncio
async def test_ingest_device_event_forwards_command_to_application_use_case() -> None:
    """Device event invocation adapter forwards client and command."""
    from custom_components.smartly_bridge.views.device_events import _ingest_device_event

    publisher = FakeDeviceEventPublisher()
    deduplicator = InMemoryDeviceEventDeduplicator()
    command = DeviceEventCommand(
        device_id="device_abc123",
        type="button_action",
        action="single_left",
        timestamp="2026-06-27T10:20:00.000Z",
        meta={"source": "zigbee2mqtt"},
    )

    result = await _ingest_device_event(
        publisher,
        deduplicator,
        None,
        "client-1",
        command,
    )

    assert result.status == 202
    assert result.body["data"]["device_id"] == "device_abc123"
    assert result.body["data"]["action"] == "single_left"
    assert publisher.events[0]["device_id"] == "device_abc123"
    assert publisher.events[0]["event"] == "single_press"


@pytest.mark.asyncio
async def test_ingest_device_event_uses_injected_use_case_factory() -> None:
    """Device event invocation adapter accepts an injected use-case factory."""
    from custom_components.smartly_bridge.views.device_events import _ingest_device_event

    publisher = FakeDeviceEventPublisher()
    deduplicator = InMemoryDeviceEventDeduplicator()
    automation = object()
    use_case = FakeDeviceEventUseCase()
    factory_calls: list[tuple[object, object, object]] = []

    def use_case_factory(received_publisher, received_deduplicator, received_automation):
        factory_calls.append(
            (received_publisher, received_deduplicator, received_automation)
        )
        return use_case

    command = DeviceEventCommand(
        device_id="device_abc123",
        type="button_action",
        action="single_left",
        timestamp="2026-06-27T10:20:00.000Z",
        meta={"source": "zigbee2mqtt"},
    )

    result = await _ingest_device_event(
        publisher,
        deduplicator,
        automation,
        "client-1",
        command,
        use_case_factory=use_case_factory,
    )

    assert result.status == 202
    assert factory_calls == [(publisher, deduplicator, automation)]
    assert use_case.calls == [("client-1", command)]
    assert result.body["data"]["device_id"] == "device_abc123"


def test_build_local_automation_reuses_setup_runtime_adapters() -> None:
    """Local automation assembly uses setup-created rule and command ports."""
    from custom_components.smartly_bridge.views.device_events import _build_local_automation

    rule_store = FakeLocalAutomationRuleStore(
        [
            LocalAutomationRule(
                rule_id="rule-left-single",
                trigger=AutomationTrigger(
                    device_id="device_abc123",
                    capability="button_event",
                    event="single_press",
                    payload={"button": "left"},
                ),
                actions=[
                    AutomationAction(
                        type="device_command",
                        device_id="ldev_light",
                        capability="power",
                        command="turn_on",
                    )
                ],
            )
        ]
    )
    command_executor = FakeSmartlyCommandExecutor()
    integration_data = {
        "runtime_adapters": {
            "local_automation_rule_store": rule_store,
            "smartly_command_executor": command_executor,
        }
    }

    automation = _build_local_automation(integration_data, MagicMock())

    assert automation is not None
    assert integration_data["runtime_adapters"]["local_automation_rule_store"] is rule_store
    assert integration_data["runtime_adapters"]["smartly_command_executor"] is command_executor
    assert rule_store.list_calls == 1


def test_build_local_automation_does_not_mutate_runtime_adapters() -> None:
    """Local automation assembly uses only setup-created runtime adapters."""
    from custom_components.smartly_bridge.views.device_events import _build_local_automation

    rule_store = FakeLocalAutomationRuleStore(
        [
            LocalAutomationRule(
                rule_id="rule-left-single",
                trigger=AutomationTrigger(
                    device_id="device_abc123",
                    capability="button_event",
                    event="single_press",
                    payload={"button": "left"},
                ),
                actions=[
                    AutomationAction(
                        type="device_command",
                        device_id="ldev_light",
                        capability="power",
                        command="turn_on",
                    )
                ],
            )
        ]
    )
    command_executor = FakeSmartlyCommandExecutor()
    integration_data = {
        "runtime_adapters": {
            "local_automation_rule_store": rule_store,
            "smartly_command_executor": command_executor,
        }
    }

    automation = _build_local_automation(integration_data, MagicMock())

    assert automation is not None
    assert integration_data["runtime_adapters"] == {
        "local_automation_rule_store": rule_store,
        "smartly_command_executor": command_executor,
    }


def test_build_local_automation_requires_runtime_rule_store() -> None:
    """Local automation assembly does not create a request-time rule-store fallback."""
    from custom_components.smartly_bridge.views.device_events import _build_local_automation

    command_executor = FakeSmartlyCommandExecutor()
    integration_data = {
        "local_automation_rules": [
            LocalAutomationRule(
                rule_id="rule-left-single",
                trigger=AutomationTrigger(
                    device_id="device_abc123",
                    capability="button_event",
                    event="single_press",
                    payload={"button": "left"},
                ),
                actions=[
                    AutomationAction(
                        type="device_command",
                        device_id="ldev_light",
                        capability="power",
                        command="turn_on",
                    )
                ],
            )
        ],
        "runtime_adapters": {
            "smartly_command_executor": command_executor,
        },
    }

    automation = _build_local_automation(integration_data, MagicMock())

    assert automation is None
    assert "local_automation_rule_store" not in integration_data["runtime_adapters"]
    assert integration_data["runtime_adapters"]["smartly_command_executor"] is command_executor


def test_build_local_automation_requires_runtime_command_executor() -> None:
    """Local automation assembly does not create a request-time command executor fallback."""
    from custom_components.smartly_bridge.views.device_events import _build_local_automation

    rule_store = FakeLocalAutomationRuleStore(
        [
            LocalAutomationRule(
                rule_id="rule-left-single",
                trigger=AutomationTrigger(
                    device_id="device_abc123",
                    capability="button_event",
                    event="single_press",
                    payload={"button": "left"},
                ),
                actions=[
                    AutomationAction(
                        type="device_command",
                        device_id="ldev_light",
                        capability="power",
                        command="turn_on",
                    )
                ],
            )
        ]
    )
    integration_data = {
        "runtime_adapters": {
            "local_automation_rule_store": rule_store,
        },
    }

    automation = _build_local_automation(integration_data, MagicMock())

    assert automation is None
    assert integration_data["runtime_adapters"]["local_automation_rule_store"] is rule_store
    assert "smartly_command_executor" not in integration_data["runtime_adapters"]


def test_build_local_automation_uses_injected_use_case_factory() -> None:
    """Local automation assembly accepts an injected use-case factory."""
    from custom_components.smartly_bridge.views.device_events import _build_local_automation

    rule_store = FakeLocalAutomationRuleStore(
        [
            LocalAutomationRule(
                rule_id="rule-left-single",
                trigger=AutomationTrigger(
                    device_id="device_abc123",
                    capability="button_event",
                    event="single_press",
                    payload={"button": "left"},
                ),
                actions=[
                    AutomationAction(
                        type="device_command",
                        device_id="ldev_light",
                        capability="power",
                        command="turn_on",
                    )
                ],
            )
        ]
    )
    command_executor = FakeSmartlyCommandExecutor()
    integration_data = {
        "runtime_adapters": {
            "local_automation_rule_store": rule_store,
            "smartly_command_executor": command_executor,
        }
    }
    factory_calls: list[tuple[object, object]] = []

    def use_case_factory(received_rule_store, received_command_executor):
        factory_calls.append((received_rule_store, received_command_executor))
        return FakeLocalAutomationUseCase(
            received_rule_store,
            received_command_executor,
        )

    automation = _build_local_automation(
        integration_data,
        MagicMock(),
        use_case_factory=use_case_factory,
    )

    assert isinstance(automation, FakeLocalAutomationUseCase)
    assert factory_calls == [(rule_store, command_executor)]
    assert automation.rule_store is rule_store
    assert automation.command_executor is command_executor


def test_device_event_publisher_resolver_uses_runtime_publisher() -> None:
    """Device event publisher resolver returns the setup-created runtime port."""
    from custom_components.smartly_bridge.views.device_events import _device_event_publisher

    publisher = FakeDeviceEventPublisher()
    integration_data = {
        "runtime_adapters": {
            "device_event_publisher": publisher,
        }
    }

    result = _device_event_publisher(integration_data, MagicMock())

    assert result is publisher


def test_device_event_publisher_resolver_requires_runtime_publisher() -> None:
    """Device event publisher resolver does not create a fallback."""
    from custom_components.smartly_bridge.views.device_events import _device_event_publisher

    integration_data = {"runtime_adapters": {}}
    hass = MagicMock()

    result = _device_event_publisher(integration_data, hass)

    assert result is None
    assert "device_event_publisher" not in integration_data["runtime_adapters"]


def test_device_event_deduplicator_resolver_uses_runtime_deduplicator() -> None:
    """Device event deduplicator resolver returns the setup-created runtime port."""
    from custom_components.smartly_bridge.views.device_events import _device_event_deduplicator

    deduplicator = InMemoryDeviceEventDeduplicator()
    integration_data = {
        "runtime_adapters": {
            "device_event_deduplicator": deduplicator,
        }
    }

    result = _device_event_deduplicator(integration_data)

    assert result is deduplicator


def test_device_event_deduplicator_resolver_requires_runtime_deduplicator() -> None:
    """Device event deduplicator resolver does not create a fallback."""
    from custom_components.smartly_bridge.views.device_events import _device_event_deduplicator

    integration_data = {"runtime_adapters": {}}

    result = _device_event_deduplicator(integration_data)

    assert result is None
    assert "device_event_deduplicator" not in integration_data["runtime_adapters"]
    assert "device_event_deduplicator" not in integration_data


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
        assert set(payload) == {"schema_version", "data", "warnings", "errors"}
        assert payload["data"]["device_id"] == "device_abc123"
        assert payload["data"]["action"] == "single_left"
        assert payload["data"]["event_id"].startswith("evt_")
        assert payload["data"]["capability"] == "button_event"
        assert payload["data"]["event"] == "single_press"
        assert payload["data"]["payload"] == {"button": "left"}
        assert payload["data"]["events"] == [
            {
                "event_id": payload["data"]["event_id"],
                "device_id": "device_abc123",
                "capability": "button_event",
                "event": "single_press",
                "payload": {"button": "left"},
                "occurred_at": "2026-06-27T10:20:00.000Z",
            }
        ]
        assert "received_at" in payload["data"]
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
    async def test_device_event_response_includes_request_context_headers(self, mock_hass):
        """Accepted event responses echo optional request correlation headers."""
        _configure_integration(mock_hass)
        request = _request_for_device_event(
            mock_hass,
            {
                "type": "button_action",
                "action": "single_left",
                "timestamp": "2026-06-27T10:20:00.000Z",
            },
        )
        request.headers["X-Request-Id"] = "req-device-001"
        request.headers["X-Correlation-Id"] = "corr-device-001"

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client", error=None)

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 202
        payload = json.loads(response.body)
        assert payload["request_id"] == "req-device-001"
        assert payload["correlation_id"] == "corr-device-001"
        assert payload["data"]["device_id"] == "device_abc123"

    @pytest.mark.asyncio
    async def test_device_event_requires_setup_runtime_publisher(self, mock_hass):
        """Device events fail when setup did not create the event publisher."""
        _configure_integration(mock_hass)
        mock_hass.data[DOMAIN]["runtime_adapters"].pop("device_event_publisher")
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
        assert json.loads(response.body) == {
            "schema_version": "2026.06",
            "data": {
                "device_id": "device_abc123",
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": "DEVICE_EVENT_PUBLISHER_UNAVAILABLE",
                    "message": "Device event publisher not initialized",
                    "target": "device_event.publisher",
                    "retryable": False,
                }
            ],
        }
        assert (
            "device_event_publisher"
            not in mock_hass.data[DOMAIN]["runtime_adapters"]
        )

    @pytest.mark.asyncio
    async def test_device_event_requires_setup_runtime_deduplicator(self, mock_hass):
        """Device events fail when setup did not create the event deduplicator."""
        _configure_integration(mock_hass)
        mock_hass.data[DOMAIN]["runtime_adapters"].pop("device_event_deduplicator")
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
        assert json.loads(response.body) == {
            "schema_version": "2026.06",
            "data": {
                "device_id": "device_abc123",
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": "DEVICE_EVENT_DEDUPLICATOR_UNAVAILABLE",
                    "message": "Device event deduplicator not initialized",
                    "target": "device_event.deduplicator",
                    "retryable": False,
                }
            ],
        }
        assert (
            "device_event_deduplicator"
            not in mock_hass.data[DOMAIN]["runtime_adapters"]
        )

    @pytest.mark.asyncio
    async def test_device_event_requires_setup_runtime_local_automation_rule_store(
        self,
        mock_hass,
    ):
        """Configured local automation fails without the setup-created rule store."""
        _configure_integration(mock_hass)
        mock_hass.data[DOMAIN]["local_automation_rules"] = [
            LocalAutomationRule(
                rule_id="rule-left-single",
                trigger=AutomationTrigger(
                    device_id="ldev_button",
                    capability="button_event",
                    event="single_press",
                    payload={"button": "left"},
                ),
                actions=[
                    AutomationAction(
                        type="device_command",
                        device_id="ldev_light_kitchen",
                        capability="power",
                        command="turn_on",
                    )
                ],
            )
        ]
        mock_hass.data[DOMAIN]["runtime_adapters"]["smartly_command_executor"] = (
            FakeSmartlyCommandExecutor()
        )
        request = _request_for_device_event(
            mock_hass,
            {
                "type": "button_action",
                "action": "single_left",
                "timestamp": "2026-06-27T10:20:00.000Z",
            },
            device_id="ldev_button",
        )

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(
                success=True,
                client_id="test_client",
                error=None,
            )

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 500
        assert json.loads(response.body) == {
            "schema_version": "2026.06",
            "data": {
                "device_id": "ldev_button",
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": "LOCAL_AUTOMATION_RULE_STORE_UNAVAILABLE",
                    "message": "Local automation rule store not initialized",
                    "target": "local_automation.rule_store",
                    "retryable": False,
                }
            ],
        }
        assert (
            "local_automation_rule_store"
            not in mock_hass.data[DOMAIN]["runtime_adapters"]
        )
        mock_hass.bus.async_fire.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_event_requires_setup_runtime_smartly_command_executor(
        self,
        mock_hass,
    ):
        """Configured local automation fails without the setup-created command executor."""
        _configure_integration(mock_hass)
        mock_hass.data[DOMAIN]["runtime_adapters"]["local_automation_rule_store"] = (
            FakeLocalAutomationRuleStore(
                [
                    LocalAutomationRule(
                        rule_id="rule-left-single",
                        trigger=AutomationTrigger(
                            device_id="ldev_button",
                            capability="button_event",
                            event="single_press",
                            payload={"button": "left"},
                        ),
                        actions=[
                            AutomationAction(
                                type="device_command",
                                device_id="ldev_light_kitchen",
                                capability="power",
                                command="turn_on",
                            )
                        ],
                    )
                ]
            )
        )
        request = _request_for_device_event(
            mock_hass,
            {
                "type": "button_action",
                "action": "single_left",
                "timestamp": "2026-06-27T10:20:00.000Z",
            },
            device_id="ldev_button",
        )

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(
                success=True,
                client_id="test_client",
                error=None,
            )

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 500
        assert json.loads(response.body) == {
            "schema_version": "2026.06",
            "data": {
                "device_id": "ldev_button",
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": "SMARTLY_COMMAND_EXECUTOR_UNAVAILABLE",
                    "message": "Smartly command executor not initialized",
                    "target": "local_automation.command_executor",
                    "retryable": False,
                }
            ],
        }
        assert (
            "smartly_command_executor"
            not in mock_hass.data[DOMAIN]["runtime_adapters"]
        )
        mock_hass.bus.async_fire.assert_not_called()

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
        assert json.loads(response.body)["errors"][0]["code"] == "INVALID_ACTION"
        mock_hass.bus.async_fire.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_event_invalid_json_response_includes_vnext_error_envelope(
        self,
        mock_hass,
    ):
        """HTTP invalid JSON responses expose API vNext error envelope fields."""
        _configure_integration(mock_hass)
        request = _request_for_device_event(mock_hass, {})
        request.json = AsyncMock(side_effect=json.JSONDecodeError("invalid", "", 0))

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client", error=None)

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 400
        assert json.loads(response.body) == {
            "schema_version": "2026.06",
            "data": {
                "device_id": "device_abc123",
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": "INVALID_JSON",
                    "message": "Invalid JSON body",
                    "target": "request.body",
                    "retryable": False,
                }
            ],
        }
        mock_hass.bus.async_fire.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_event_auth_failure_response_includes_vnext_error_envelope(
        self,
        mock_hass,
    ):
        """HTTP auth failure responses expose API vNext error envelope fields."""
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
            mock_verify.return_value = MagicMock(
                success=False,
                client_id=None,
                error="invalid_signature",
            )

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 401
        assert json.loads(response.body) == {
            "schema_version": "2026.06",
            "data": {
                "device_id": "device_abc123",
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": "INVALID_SIGNATURE",
                    "message": "Device event request authentication failed",
                    "target": "request.auth",
                    "retryable": False,
                }
            ],
        }
        mock_hass.bus.async_fire.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_event_rate_limit_response_includes_vnext_error_envelope(
        self,
        mock_hass,
    ):
        """HTTP rate-limit responses expose API vNext error envelope fields."""
        _configure_integration(mock_hass)
        mock_hass.data[DOMAIN]["rate_limiter"] = MagicMock()
        mock_hass.data[DOMAIN]["rate_limiter"].check = AsyncMock(return_value=False)
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
            mock_verify.return_value = MagicMock(
                success=True,
                client_id="test_client",
                error=None,
            )

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 429
        assert response.headers["Retry-After"] == "60"
        assert response.headers["X-RateLimit-Remaining"] == "0"
        assert json.loads(response.body) == {
            "schema_version": "2026.06",
            "data": {
                "device_id": "device_abc123",
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": "RATE_LIMITED",
                    "message": "Device event request was rate limited",
                    "target": "request.rate_limit",
                    "retryable": False,
                }
            ],
        }
        mock_hass.bus.async_fire.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_event_not_configured_response_includes_vnext_error_envelope(
        self,
        mock_hass,
    ):
        """HTTP integration setup failures expose API vNext error envelope fields."""
        mock_hass.data = {}
        request = _request_for_device_event(
            mock_hass,
            {
                "type": "button_action",
                "action": "single_left",
                "timestamp": "2026-06-27T10:20:00.000Z",
            },
        )

        response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 500
        assert json.loads(response.body) == {
            "schema_version": "2026.06",
            "data": {
                "device_id": "device_abc123",
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": "INTEGRATION_NOT_CONFIGURED",
                    "message": "Smartly Bridge integration is not configured",
                    "target": "integration",
                    "retryable": False,
                }
            ],
        }
        mock_hass.bus.async_fire.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_event_missing_required_fields_response_includes_vnext_error_envelope(
        self,
        mock_hass,
    ):
        """HTTP missing required field responses expose API vNext error envelope fields."""
        _configure_integration(mock_hass)
        request = _request_for_device_event(
            mock_hass,
            {
                "type": "button_action",
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
            "schema_version": "2026.06",
            "data": {
                "device_id": "device_abc123",
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": "MISSING_REQUIRED_FIELDS",
                    "message": "Missing required event fields",
                    "target": "event.action",
                    "retryable": False,
                }
            ],
        }
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
        assert payload["data"]["event"] == "single_press"
        assert payload["data"]["payload"] == {"button": "left"}
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
        assert second_payload["data"]["duplicate"] is True
        assert second_payload["data"]["event_id"] == first_payload["data"]["event_id"]
        assert (
            second_payload["data"]["events"][0]["event_id"]
            == first_payload["data"]["event_id"]
        )
        mock_hass.bus.async_fire.assert_called_once()

    @pytest.mark.asyncio
    async def test_device_event_uses_setup_runtime_event_publisher(self, mock_hass):
        """Legacy event endpoint dispatches through setup-created hexagonal adapters."""
        _configure_integration(mock_hass)
        publisher = FakeDeviceEventPublisher()
        mock_hass.data[DOMAIN]["runtime_adapters"] = {
            "device_event_publisher": publisher,
            "device_event_deduplicator": InMemoryDeviceEventDeduplicator(),
        }
        body = {
            "type": "button_action",
            "action": "single_left",
            "timestamp": "2026-06-27T10:20:00.000Z",
        }
        request = _request_for_device_event(mock_hass, body)

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(success=True, client_id="test_client", error=None)

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 202
        assert len(publisher.events) == 1
        assert publisher.events[0]["device_id"] == "device_abc123"
        mock_hass.bus.async_fire.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_event_triggers_local_automation_device_command(self, mock_hass):
        """Accepted device events execute matching local automation device commands."""
        _configure_integration(mock_hass)
        mock_hass.data[DOMAIN]["local_automation_rules"] = [
            LocalAutomationRule(
                rule_id="rule-left-single",
                trigger=AutomationTrigger(
                    device_id="ldev_button",
                    capability="button_event",
                    event="single_press",
                    payload={"button": "left"},
                ),
                actions=[
                    AutomationAction(
                        type="device_command",
                        device_id="ldev_light_kitchen",
                        capability="power",
                        command="turn_on",
                    )
                ],
            )
        ]
        _configure_local_automation_runtime(mock_hass)

        mock_light_state = MagicMock()
        mock_light_state.state = "on"
        mock_light_state.attributes = {"friendly_name": "Kitchen Light"}
        mock_hass.states.get.return_value = mock_light_state

        body = {
            "type": "button_action",
            "action": "single_left",
            "timestamp": "2026-06-27T10:20:00.000Z",
        }
        request = _request_for_device_event(mock_hass, body, device_id="ldev_button")

        with (
            patch(
                "custom_components.smartly_bridge.views.device_events.verify_request"
            ) as mock_verify,
            patch(
                "custom_components.smartly_bridge.adapters.home_assistant.get_allowed_entities",
                return_value=["light.kitchen"],
            ),
            patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get,
        ):
            mock_verify.return_value = MagicMock(
                success=True,
                client_id="test_client",
                error=None,
            )
            mock_entry = MagicMock(labels={"smartly"}, device_id="light-kitchen")
            mock_registry = MagicMock()
            mock_registry.async_get = MagicMock(return_value=mock_entry)
            mock_registry.entities = {"light.kitchen": mock_entry}
            mock_er_get.return_value = mock_registry

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 202
        payload = json.loads(response.body)
        assert payload["data"]["automations"] == [
            {
                "rule_id": "rule-left-single",
                "action_index": 0,
                "type": "device_command",
                "command_id": (
                    f"auto_{payload['data']['event_id']}_rule-left-single_0"
                ),
                "status": "completed",
                "response_status": 200,
            }
        ]
        mock_hass.services.async_call.assert_awaited_once_with(
            "light",
            "turn_on",
            {"entity_id": "light.kitchen"},
            blocking=True,
        )

    @pytest.mark.asyncio
    async def test_device_event_uses_stored_local_automation_rules(self, mock_hass):
        """Stored local automation rules trigger without runtime rule overrides."""
        _configure_integration(mock_hass)
        mock_hass.data[DOMAIN]["config_entry"].data["local_automation_rules"] = [
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
                        "device_id": "ldev_light_kitchen",
                        "capability": "power",
                        "command": "turn_on",
                    }
                ],
            }
        ]
        _configure_local_automation_runtime(mock_hass)

        mock_light_state = MagicMock()
        mock_light_state.state = "on"
        mock_light_state.attributes = {"friendly_name": "Kitchen Light"}
        mock_hass.states.get.return_value = mock_light_state

        request = _request_for_device_event(
            mock_hass,
            {
                "type": "button_action",
                "action": "single_left",
                "timestamp": "2026-06-27T10:20:00.000Z",
            },
            device_id="ldev_button",
        )

        with (
            patch(
                "custom_components.smartly_bridge.views.device_events.verify_request"
            ) as mock_verify,
            patch(
                "custom_components.smartly_bridge.adapters.home_assistant.get_allowed_entities",
                return_value=["light.kitchen"],
            ),
            patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get,
        ):
            mock_verify.return_value = MagicMock(
                success=True,
                client_id="test_client",
                error=None,
            )
            mock_entry = MagicMock(labels={"smartly"}, device_id="light-kitchen")
            mock_registry = MagicMock()
            mock_registry.async_get = MagicMock(return_value=mock_entry)
            mock_registry.entities = {"light.kitchen": mock_entry}
            mock_er_get.return_value = mock_registry

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 202
        payload = json.loads(response.body)
        assert payload["data"]["automations"] == [
            {
                "rule_id": "stored-left-single",
                "action_index": 0,
                "type": "device_command",
                "command_id": (
                    f"auto_{payload['data']['event_id']}_stored-left-single_0"
                ),
                "status": "completed",
                "response_status": 200,
            }
        ]
        mock_hass.services.async_call.assert_awaited_once_with(
            "light",
            "turn_on",
            {"entity_id": "light.kitchen"},
            blocking=True,
        )

    @pytest.mark.asyncio
    async def test_device_event_uses_runtime_rule_store_even_without_legacy_rules(
        self,
        mock_hass,
    ):
        """Runtime rule store rules enable automation without legacy rule data."""
        _configure_integration(mock_hass)
        rule_store = FakeLocalAutomationRuleStore(
            [
                LocalAutomationRule(
                    rule_id="runtime-left-single",
                    trigger=AutomationTrigger(
                        device_id="ldev_button",
                        capability="button_event",
                        event="single_press",
                        payload={"button": "left"},
                    ),
                    actions=[
                        AutomationAction(
                            type="device_command",
                            device_id="ldev_light_kitchen",
                            capability="power",
                            command="turn_on",
                        )
                    ],
                )
            ]
        )
        command_executor = FakeSmartlyCommandExecutor()
        mock_hass.data[DOMAIN]["runtime_adapters"] = {
            "device_event_publisher": FakeDeviceEventPublisher(),
            "device_event_deduplicator": InMemoryDeviceEventDeduplicator(),
            "local_automation_rule_store": rule_store,
            "smartly_command_executor": command_executor,
        }
        request = _request_for_device_event(
            mock_hass,
            {
                "type": "button_action",
                "action": "single_left",
                "timestamp": "2026-06-27T10:20:00.000Z",
            },
            device_id="ldev_button",
        )

        with patch(
            "custom_components.smartly_bridge.views.device_events.verify_request"
        ) as mock_verify:
            mock_verify.return_value = MagicMock(
                success=True,
                client_id="test_client",
                error=None,
            )

            response = await SmartlyDeviceEventsView(request).post()

        assert response.status == 202
        payload = json.loads(response.body)
        assert payload["data"]["automations"] == [
            {
                "rule_id": "runtime-left-single",
                "action_index": 0,
                "type": "device_command",
                "command_id": (
                    f"auto_{payload['data']['event_id']}_runtime-left-single_0"
                ),
                "status": "completed",
                "response_status": 200,
            }
        ]
        assert rule_store.list_calls >= 1
        assert len(command_executor.calls) == 1

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
        assert json.loads(response.body) == {
            "schema_version": "2026.06",
            "data": {
                "device_id": "device_abc123",
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": "DEVICE_EVENT_FAILED",
                    "message": "RuntimeError: event bus unavailable",
                    "target": "device_event.dispatch",
                    "retryable": False,
                }
            ],
        }

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
