"""Tests for local automation application use cases."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.smartly_bridge.application.control import SmartlyCommand
from custom_components.smartly_bridge.application.local_automation import (
    AutomationAction,
    AutomationTrigger,
    LocalAutomationRule,
    LocalAutomationUseCase,
)
from custom_components.smartly_bridge.domain.models import BridgeResponse


class FakeAutomationRuleStore:
    """Fake local automation rule store."""

    def __init__(self, rules: list[LocalAutomationRule]) -> None:
        self.rules = rules

    def list_rules(self) -> list[LocalAutomationRule]:
        return self.rules


class FakeSmartlyCommandExecutor:
    """Fake SmartlyCommand executor port."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, SmartlyCommand]] = []

    async def execute(self, client_id: str, command: SmartlyCommand) -> BridgeResponse:
        self.commands.append((client_id, command))
        return BridgeResponse(
            {
                "success": True,
                "command_id": command.command_id,
                "status": "completed",
            },
            status=200,
        )


@pytest.mark.asyncio
async def test_button_event_rule_executes_device_command_action() -> None:
    """Canonical button events trigger matching local device_command actions."""
    store = FakeAutomationRuleStore(
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
                        device_id="ldev_light",
                        capability="power",
                        command="toggle",
                        params={},
                    )
                ],
            )
        ]
    )
    executor = FakeSmartlyCommandExecutor()
    use_case = LocalAutomationUseCase(
        store,
        executor,
        command_id_factory=lambda event, rule, index: f"cmd-{event['event_id']}-{rule.rule_id}-{index}",
    )

    results = await use_case.handle_device_event(
        "client-1",
        {
            "event_id": "evt-1",
            "device_id": "ldev_button",
            "capability": "button_event",
            "event": "single_press",
            "payload": {"button": "left"},
            "occurred_at": "2026-06-29T00:00:00Z",
        },
    )

    assert executor.commands == [
        (
            "client-1",
            SmartlyCommand(
                command_id="cmd-evt-1-rule-left-single-0",
                device_id="ldev_light",
                capability="power",
                command="toggle",
                params={},
                source={
                    "automation_rule_id": "rule-left-single",
                    "event_id": "evt-1",
                },
            ),
        )
    ]
    assert results == [
        {
            "rule_id": "rule-left-single",
            "action_index": 0,
            "type": "device_command",
            "command_id": "cmd-evt-1-rule-left-single-0",
            "status": "completed",
            "response_status": 200,
        }
    ]


@pytest.mark.asyncio
async def test_button_event_rule_requires_payload_match() -> None:
    """Button event rules only trigger when canonical payload constraints match."""
    store = FakeAutomationRuleStore(
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
                        device_id="ldev_light",
                        capability="power",
                        command="toggle",
                    )
                ],
            )
        ]
    )
    executor = FakeSmartlyCommandExecutor()
    use_case = LocalAutomationUseCase(store, executor)

    results = await use_case.handle_device_event(
        "client-1",
        {
            "event_id": "evt-1",
            "device_id": "ldev_button",
            "capability": "button_event",
            "event": "single_press",
            "payload": {"button": "right"},
            "occurred_at": "2026-06-29T00:00:00Z",
        },
    )

    assert executor.commands == []
    assert results == []
