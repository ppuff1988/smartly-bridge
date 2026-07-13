"""Tests for Home Assistant Smartly command executor wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.smartly_bridge.adapters.home_assistant import (
    HomeAssistantCommandTargetResolver,
    HomeAssistantSmartlyCommandExecutor,
    _home_assistant_smartly_command_executor,
)
from custom_components.smartly_bridge.application.control import SmartlyCommand
from custom_components.smartly_bridge.domain.models import BridgeResponse


class FakeSmartlyCommandUseCase:
    """Smartly command use case used to verify executor wiring."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, SmartlyCommand]] = []

    async def execute(self, client_id: str, command: SmartlyCommand) -> BridgeResponse:
        """Record the command and return an accepted response."""
        self.calls.append((client_id, command))
        return BridgeResponse(
            {
                "schema_version": "2026.06",
                "data": {
                    "command_id": command.command_id,
                    "status": "completed",
                },
                "warnings": [],
                "errors": [],
            }
        )


def test_home_assistant_smartly_command_executor_factory_builds_runtime_executor() -> None:
    """Smartly command executor factory centralizes runtime executor wiring."""
    hass = MagicMock()
    logger = MagicMock()

    executor = _home_assistant_smartly_command_executor(hass, logger)

    assert isinstance(executor, HomeAssistantSmartlyCommandExecutor)


@pytest.mark.asyncio
async def test_smartly_command_executor_uses_injected_use_case_factory() -> None:
    """Command executor delegates through the injected application use case seam."""
    hass = MagicMock()
    logger = MagicMock()
    use_case = FakeSmartlyCommandUseCase()
    factory_calls: list[tuple[object, object]] = []

    def use_case_factory(hass_arg: object, logger_arg: object) -> FakeSmartlyCommandUseCase:
        factory_calls.append((hass_arg, logger_arg))
        return use_case

    executor = HomeAssistantSmartlyCommandExecutor(
        hass,
        logger,
        use_case_factory=use_case_factory,
    )
    command = SmartlyCommand(
        command_id="cmd-1",
        device_id="ldev-light",
        capability="power",
        command="turn_on",
    )

    result = await executor.execute("client-1", command)

    assert result.body["data"]["status"] == "completed"
    assert factory_calls == [(hass, logger)]
    assert use_case.calls == [("client-1", command)]


def test_setting_target_resolver_rejects_ambiguous_unkeyed_settings() -> None:
    """Multiple sibling settings require the stable instance key."""
    hass = MagicMock()
    trigger_state = MagicMock()
    trigger_state.state = "15"
    trigger_state.attributes = {"friendly_name": "Trigger hold seconds"}
    cooldown_state = MagicMock()
    cooldown_state.state = "5"
    cooldown_state.attributes = {"friendly_name": "Cooldown seconds"}
    hass.states.get.side_effect = lambda entity_id: {
        "number.presence_detection_delay": trigger_state,
        "number.presence_cooldown": cooldown_state,
    }.get(entity_id)
    registry = MagicMock()
    trigger = MagicMock(
        entity_id="number.presence_detection_delay",
        device_id="zigbee-presence-1",
    )
    cooldown = MagicMock(
        entity_id="number.presence_cooldown",
        device_id="zigbee-presence-1",
    )
    registry.entities = {
        trigger.entity_id: trigger,
        cooldown.entity_id: cooldown,
    }
    resolver = HomeAssistantCommandTargetResolver(hass)

    assert (
        resolver._resolve_setting_target(
            registry,
            {"zigbee-presence-1"},
            domains={"number", "input_number"},
        )
        is None
    )
    assert (
        resolver._resolve_setting_target(
            registry,
            {"zigbee-presence-1"},
            domains={"number", "input_number"},
            setting_key="cooldown_seconds",
        )
        == "number.presence_cooldown"
    )


def test_setting_target_resolver_supports_standalone_helper() -> None:
    """A setting helper without an HA device ID can still resolve itself."""
    hass = MagicMock()
    state = MagicMock(
        state="15",
        attributes={"friendly_name": "Hall delay"},
    )
    hass.states.get.return_value = state
    helper = MagicMock(
        entity_id="input_number.hall_delay",
        device_id=None,
    )
    registry = MagicMock()
    registry.entities = {helper.entity_id: helper}
    resolver = HomeAssistantCommandTargetResolver(hass)

    target = resolver._resolve_setting_target(
        registry,
        {"input_number.hall_delay"},
        domains={"number", "input_number"},
    )

    assert target == "input_number.hall_delay"


@pytest.mark.parametrize(
    ("domain", "capability", "keyed"),
    [
        ("input_number", "numeric_setting", True),
        ("input_number", "numeric_setting", False),
        ("input_select", "option_setting", True),
        ("input_select", "option_setting", False),
    ],
)
def test_labeled_setting_helpers_use_keyed_resolver(
    domain: str,
    capability: str,
    keyed: bool,
) -> None:
    """Directly labeled settings still enforce key selection and ambiguity."""
    hass = MagicMock()
    if domain == "input_number":
        trigger_object_id = "presence_detection_delay"
        cooldown_object_id = "presence_cooldown"
        trigger_name = "Trigger hold seconds"
        cooldown_name = "Cooldown seconds"
        setting_key = "cooldown_seconds"
    else:
        trigger_object_id = "presence_sensitivity"
        cooldown_object_id = "presence_mode"
        trigger_name = "Presence sensitivity"
        cooldown_name = "Presence mode"
        setting_key = "presence_mode"
    trigger_state = MagicMock(
        state="15",
        attributes={
            "friendly_name": trigger_name,
            "min": 1,
            "max": 120,
            "step": 1,
            "options": ["15", "5"],
        },
    )
    cooldown_state = MagicMock(
        state="5",
        attributes={
            "friendly_name": cooldown_name,
            "min": 1,
            "max": 60,
            "step": 1,
            "options": ["15", "5"],
        },
    )
    trigger_entity_id = f"{domain}.{trigger_object_id}"
    cooldown_entity_id = f"{domain}.{cooldown_object_id}"
    hass.states.get.side_effect = lambda entity_id: {
        trigger_entity_id: trigger_state,
        cooldown_entity_id: cooldown_state,
    }.get(entity_id)
    trigger = MagicMock(
        entity_id=trigger_entity_id,
        device_id="zigbee-presence-1",
        labels={"smartly"},
    )
    cooldown = MagicMock(
        entity_id=cooldown_entity_id,
        device_id="zigbee-presence-1",
        labels={"smartly"},
    )
    registry = MagicMock()
    registry.entities = {
        trigger.entity_id: trigger,
        cooldown.entity_id: cooldown,
    }
    registry.async_get.side_effect = lambda entity_id: registry.entities.get(entity_id)
    resolver = HomeAssistantCommandTargetResolver(
        hass,
        allowed_entities_fn=lambda _hass, _registry: list(registry.entities),
    )

    from homeassistant.helpers import entity_registry as er

    with patch.object(er, "async_get", return_value=registry):
        target = resolver.resolve_command_target(
            "ldev_zigbee_presence_1",
            capability,
            {"key": setting_key} if keyed else {},
        )

    expected = cooldown_entity_id if keyed else None
    assert target == expected
