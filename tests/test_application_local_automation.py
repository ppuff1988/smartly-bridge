"""Tests for local automation application use cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from custom_components.smartly_bridge.application.control import SmartlyCommand
from custom_components.smartly_bridge.application.local_automation import (
    AutomationAction,
    AutomationTrigger,
    LocalAutomationRule,
    LocalAutomationRuleCreateUseCase,
    LocalAutomationRuleDeleteUseCase,
    LocalAutomationRuleUpdateUseCase,
    LocalAutomationRulesListUseCase,
    LocalAutomationUseCase,
    _command_response_status,
)
from custom_components.smartly_bridge.domain.models import BridgeResponse


class FakeAutomationRuleStore:
    """Fake local automation rule store."""

    def __init__(
        self,
        rules: list[LocalAutomationRule],
        *,
        fail_create: bool = False,
        fail_update: bool = False,
        fail_delete: bool = False,
    ) -> None:
        self.rules = rules
        self.fail_create = fail_create
        self.fail_update = fail_update
        self.fail_delete = fail_delete

    def list_rules(self) -> list[LocalAutomationRule]:
        return self.rules

    def create_rule(self, rule: LocalAutomationRule) -> bool:
        if self.fail_create:
            return False
        self.rules.append(rule)
        return True

    def update_rule(self, rule: LocalAutomationRule) -> bool:
        if self.fail_update:
            return False
        for index, existing in enumerate(self.rules):
            if existing.rule_id == rule.rule_id:
                self.rules[index] = rule
                return True
        return False

    def delete_rule(self, rule_id: str) -> bool:
        if self.fail_delete:
            return False
        for index, existing in enumerate(self.rules):
            if existing.rule_id == rule_id:
                del self.rules[index]
                return True
        return False


class FakeSmartlyCommandExecutor:
    """Fake SmartlyCommand executor port."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, SmartlyCommand]] = []

    async def execute(self, client_id: str, command: SmartlyCommand) -> BridgeResponse:
        self.commands.append((client_id, command))
        return BridgeResponse(
            {
                "schema_version": "2026.06",
                "data": {
                    "command_id": command.command_id,
                    "status": "completed",
                    "device_id": command.device_id,
                    "capability": command.capability,
                    "command": command.command,
                },
                "warnings": [],
                "errors": [],
            },
            status=200,
        )


def _fixture(name: str) -> dict[str, Any]:
    """Load an API vNext fixture."""
    return json.loads(
        (Path(__file__).parent / "fixtures" / "api-vnext" / name).read_text()
    )


def test_command_response_status_ignores_removed_top_level_status() -> None:
    """Local automation command results only read SmartlyCommand vNext data.status."""
    response = BridgeResponse(
        {
            "status": "completed",
            "schema_version": "2026.06",
            "data": {},
            "warnings": [],
            "errors": [],
        },
        status=200,
    )

    assert _command_response_status(response) == "unknown"


def test_list_rules_returns_api_vnext_canonical_rule_payload() -> None:
    """Local automation rules list exposes canonical trigger/action payloads."""
    store = FakeAutomationRuleStore(
        [
            LocalAutomationRule(
                rule_id="stored-left-single",
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
                        command="turn_on",
                    )
                ],
            )
        ]
    )

    result = LocalAutomationRulesListUseCase(store).execute()

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
    assert result.status == 200
    assert result.body == {
        "schema_version": "2026.06",
        "data": {
            "rules": [expected_rule],
            "count": 1,
        },
        "warnings": [],
        "errors": [],
    }


def test_list_rules_response_matches_api_vnext_fixture() -> None:
    """Local automation list full response remains stable for Platform editor clients."""
    store = FakeAutomationRuleStore(
        [
            LocalAutomationRule(
                rule_id="stored-left-single",
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
                        command="turn_on",
                    )
                ],
            )
        ]
    )

    result = LocalAutomationRulesListUseCase(store).execute()

    assert result.body == _fixture("local-automation-list.json")


def test_create_rule_persists_canonical_rule_payload() -> None:
    """Creating a local automation rule persists canonical trigger/action config."""
    store = FakeAutomationRuleStore([])

    result = LocalAutomationRuleCreateUseCase(store).execute(
        {
            "rule_id": "rule-left-single",
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
    )

    expected_rule = LocalAutomationRule(
        rule_id="rule-left-single",
        enabled=True,
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
                command="turn_on",
                params={},
            )
        ],
    )
    assert store.rules == [expected_rule]
    assert result.status == 201
    assert set(result.body) == {"schema_version", "data", "warnings", "errors"}
    assert result.body["data"]["status"] == "created"
    assert result.body["data"]["rule_id"] == "rule-left-single"
    assert result.body["data"]["rule"]["rule_id"] == "rule-left-single"
    assert result.body["errors"] == []


def test_create_rule_response_matches_api_vnext_fixture() -> None:
    """Local automation create response remains stable for Platform editor clients."""
    store = FakeAutomationRuleStore([])

    result = LocalAutomationRuleCreateUseCase(store).execute(
        {
            "rule_id": "rule-left-single",
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
    )

    assert result.status == 201
    assert result.body == _fixture("local-automation-create.json")


def test_create_rule_rejects_when_store_cannot_persist() -> None:
    """Creating a local automation rule reports persistence failures."""
    store = FakeAutomationRuleStore([], fail_create=True)

    result = LocalAutomationRuleCreateUseCase(store).execute(
        {
            "rule_id": "rule-left-single",
            "trigger": {
                "device_id": "ldev_button",
                "capability": "button_event",
                "event": "single_press",
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
    )

    assert store.rules == []
    assert result.status == 500
    assert result.body == {
        "schema_version": "2026.06",
        "data": {
            "status": "rejected",
        },
        "warnings": [],
        "errors": [
            {
                "code": "rule_persistence_failed",
                "message": "Local automation rule could not be persisted",
                "target": "rule",
            }
        ],
    }


def test_create_rule_persistence_error_matches_api_vnext_fixture() -> None:
    """Local automation create error response remains stable for Platform clients."""
    store = FakeAutomationRuleStore([], fail_create=True)

    result = LocalAutomationRuleCreateUseCase(store).execute(
        {
            "rule_id": "rule-left-single",
            "trigger": {
                "device_id": "ldev_button",
                "capability": "button_event",
                "event": "single_press",
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
    )

    assert result.body == _fixture("local-automation-create-error.json")


def test_update_rule_replaces_existing_canonical_rule() -> None:
    """Updating a local automation rule replaces the existing stored rule."""
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
                        command="turn_on",
                    )
                ],
            )
        ]
    )

    result = LocalAutomationRuleUpdateUseCase(store).execute(
        "rule-left-single",
        {
            "rule_id": "ignored-client-rule-id",
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
    )

    expected_rule = LocalAutomationRule(
        rule_id="rule-left-single",
        enabled=False,
        trigger=AutomationTrigger(
            device_id="ldev_button",
            capability="button_event",
            event="double_press",
            payload={"button": "right"},
        ),
        actions=[
            AutomationAction(
                type="device_command",
                device_id="ldev_light",
                capability="power",
                command="turn_off",
                params={},
            )
        ],
    )
    assert store.rules == [expected_rule]
    assert result.status == 200
    assert set(result.body) == {"schema_version", "data", "warnings", "errors"}
    assert result.body["data"]["status"] == "updated"
    assert result.body["data"]["rule_id"] == "rule-left-single"
    assert result.body["data"]["rule"]["enabled"] is False
    assert result.body["errors"] == []


def test_update_rule_response_matches_api_vnext_fixture() -> None:
    """Local automation update response remains stable for Platform editor clients."""
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
                        command="turn_on",
                    )
                ],
            )
        ]
    )

    result = LocalAutomationRuleUpdateUseCase(store).execute(
        "rule-left-single",
        {
            "rule_id": "ignored-client-rule-id",
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
    )

    assert result.status == 200
    assert result.body == _fixture("local-automation-update.json")


def test_update_rule_rejects_when_store_cannot_persist_existing_rule() -> None:
    """Updating an existing local automation rule reports persistence failures."""
    existing_rule = LocalAutomationRule(
        rule_id="rule-left-single",
        trigger=AutomationTrigger(
            device_id="ldev_button",
            capability="button_event",
            event="single_press",
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
    store = FakeAutomationRuleStore([existing_rule], fail_update=True)

    result = LocalAutomationRuleUpdateUseCase(store).execute(
        "rule-left-single",
        {
            "trigger": {
                "device_id": "ldev_button",
                "capability": "button_event",
                "event": "double_press",
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

    assert store.rules == [existing_rule]
    assert result.status == 500
    assert result.body == {
        "schema_version": "2026.06",
        "data": {
            "status": "rejected",
        },
        "warnings": [],
        "errors": [
            {
                "code": "rule_persistence_failed",
                "message": "Local automation rule could not be persisted",
                "target": "rule",
            }
        ],
    }


def test_update_rule_persistence_error_matches_api_vnext_fixture() -> None:
    """Local automation update persistence error remains stable for Platform clients."""
    existing_rule = LocalAutomationRule(
        rule_id="rule-left-single",
        trigger=AutomationTrigger(
            device_id="ldev_button",
            capability="button_event",
            event="single_press",
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
    store = FakeAutomationRuleStore([existing_rule], fail_update=True)

    result = LocalAutomationRuleUpdateUseCase(store).execute(
        "rule-left-single",
        {
            "trigger": {
                "device_id": "ldev_button",
                "capability": "button_event",
                "event": "double_press",
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

    assert result.status == 500
    assert result.body == _fixture("local-automation-update-error.json")


def test_delete_rule_removes_existing_rule() -> None:
    """Deleting a local automation rule removes the stored rule."""
    store = FakeAutomationRuleStore(
        [
            LocalAutomationRule(
                rule_id="rule-left-single",
                trigger=AutomationTrigger(
                    device_id="ldev_button",
                    capability="button_event",
                    event="single_press",
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

    result = LocalAutomationRuleDeleteUseCase(store).execute("rule-left-single")

    assert store.rules == []
    assert result.status == 200
    assert result.body == {
        "schema_version": "2026.06",
        "data": {
            "status": "deleted",
            "rule_id": "rule-left-single",
        },
        "warnings": [],
        "errors": [],
    }


def test_delete_rule_response_matches_api_vnext_fixture() -> None:
    """Local automation delete response remains stable for Platform editor clients."""
    store = FakeAutomationRuleStore(
        [
            LocalAutomationRule(
                rule_id="rule-left-single",
                trigger=AutomationTrigger(
                    device_id="ldev_button",
                    capability="button_event",
                    event="single_press",
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

    result = LocalAutomationRuleDeleteUseCase(store).execute("rule-left-single")

    assert result.status == 200
    assert result.body == _fixture("local-automation-delete.json")


def test_delete_rule_rejects_when_store_cannot_persist_existing_rule() -> None:
    """Deleting an existing local automation rule reports persistence failures."""
    existing_rule = LocalAutomationRule(
        rule_id="rule-left-single",
        trigger=AutomationTrigger(
            device_id="ldev_button",
            capability="button_event",
            event="single_press",
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
    store = FakeAutomationRuleStore([existing_rule], fail_delete=True)

    result = LocalAutomationRuleDeleteUseCase(store).execute("rule-left-single")

    assert store.rules == [existing_rule]
    assert result.status == 500
    assert result.body == {
        "schema_version": "2026.06",
        "data": {
            "status": "rejected",
        },
        "warnings": [],
        "errors": [
            {
                "code": "rule_persistence_failed",
                "message": "Local automation rule could not be persisted",
                "target": "rule",
            }
        ],
    }


def test_delete_rule_persistence_error_matches_api_vnext_fixture() -> None:
    """Local automation delete persistence error remains stable for Platform clients."""
    existing_rule = LocalAutomationRule(
        rule_id="rule-left-single",
        trigger=AutomationTrigger(
            device_id="ldev_button",
            capability="button_event",
            event="single_press",
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
    store = FakeAutomationRuleStore([existing_rule], fail_delete=True)

    result = LocalAutomationRuleDeleteUseCase(store).execute("rule-left-single")

    assert result.status == 500
    assert result.body == _fixture("local-automation-delete-error.json")


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
