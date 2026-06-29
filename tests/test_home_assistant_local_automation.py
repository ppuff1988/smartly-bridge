"""Tests for Home Assistant local automation adapters."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.smartly_bridge.adapters.home_assistant import (
    HomeAssistantLocalAutomationRuleStore,
)
from custom_components.smartly_bridge.application.local_automation import (
    AutomationAction,
    AutomationTrigger,
    LocalAutomationRule,
)
from custom_components.smartly_bridge.const import DOMAIN


def test_local_automation_rule_store_loads_serialized_config_entry_rules() -> None:
    """Serialized config entry rules are adapted into local automation rules."""
    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            "config_entry": MagicMock(
                data={
                    "local_automation_rules": [
                        {
                            "rule_id": "rule-left-single",
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
                                    "command": "toggle",
                                    "params": {},
                                }
                            ],
                        }
                    ]
                }
            )
        }
    }

    rules = HomeAssistantLocalAutomationRuleStore(hass).list_rules()

    assert rules == [
        LocalAutomationRule(
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
                    command="toggle",
                    params={},
                )
            ],
        )
    ]


def test_local_automation_rule_store_runtime_rules_override_config_entry() -> None:
    """Runtime rules override config entry rules during live updates."""
    runtime_rule = LocalAutomationRule(
        rule_id="runtime-rule",
        trigger=AutomationTrigger(
            device_id="ldev_runtime_button",
            capability="button_event",
            event="single_press",
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
    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            "config_entry": MagicMock(
                data={
                    "local_automation_rules": [
                        {
                            "rule_id": "stored-rule",
                            "trigger": {
                                "device_id": "ldev_stored_button",
                                "capability": "button_event",
                                "event": "single_press",
                            },
                            "actions": [
                                {
                                    "type": "device_command",
                                    "device_id": "ldev_stored_light",
                                    "capability": "power",
                                    "command": "turn_on",
                                }
                            ],
                        }
                    ]
                }
            ),
            "local_automation_rules": [runtime_rule],
        }
    }

    rules = HomeAssistantLocalAutomationRuleStore(hass).list_rules()

    assert rules == [runtime_rule]


def test_local_automation_rule_store_creates_config_entry_rule() -> None:
    """Creating a rule persists serialized config entry data."""
    config_entry = MagicMock(
        data={
            "client_secret": "secret",
            "local_automation_rules": [
                {
                    "rule_id": "existing-rule",
                    "trigger": {
                        "device_id": "ldev_existing_button",
                        "capability": "button_event",
                        "event": "single_press",
                    },
                    "actions": [
                        {
                            "type": "device_command",
                            "device_id": "ldev_existing_light",
                            "capability": "power",
                            "command": "turn_on",
                        }
                    ],
                }
            ],
        }
    )
    hass = MagicMock()
    hass.data = {DOMAIN: {"config_entry": config_entry}}

    HomeAssistantLocalAutomationRuleStore(hass).create_rule(
        LocalAutomationRule(
            rule_id="new-rule",
            enabled=True,
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
    )

    hass.config_entries.async_update_entry.assert_called_once_with(
        config_entry,
        data={
            "client_secret": "secret",
            "local_automation_rules": [
                config_entry.data["local_automation_rules"][0],
                {
                    "rule_id": "new-rule",
                    "enabled": True,
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
                            "params": {},
                        }
                    ],
                },
            ],
        },
    )


def test_local_automation_rule_store_updates_config_entry_rule() -> None:
    """Updating a rule replaces serialized config entry data by rule ID."""
    config_entry = MagicMock(
        data={
            "client_secret": "secret",
            "local_automation_rules": [
                {
                    "rule_id": "target-rule",
                    "trigger": {
                        "device_id": "ldev_old_button",
                        "capability": "button_event",
                        "event": "single_press",
                    },
                    "actions": [
                        {
                            "type": "device_command",
                            "device_id": "ldev_old_light",
                            "capability": "power",
                            "command": "turn_on",
                        }
                    ],
                },
                {
                    "rule_id": "other-rule",
                    "trigger": {
                        "device_id": "ldev_other_button",
                        "capability": "button_event",
                        "event": "single_press",
                    },
                    "actions": [
                        {
                            "type": "device_command",
                            "device_id": "ldev_other_light",
                            "capability": "power",
                            "command": "turn_on",
                        }
                    ],
                },
            ],
        }
    )
    hass = MagicMock()
    hass.data = {DOMAIN: {"config_entry": config_entry}}

    updated = HomeAssistantLocalAutomationRuleStore(hass).update_rule(
        LocalAutomationRule(
            rule_id="target-rule",
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
    )

    assert updated is True
    hass.config_entries.async_update_entry.assert_called_once_with(
        config_entry,
        data={
            "client_secret": "secret",
            "local_automation_rules": [
                {
                    "rule_id": "target-rule",
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
                            "params": {},
                        }
                    ],
                },
                config_entry.data["local_automation_rules"][1],
            ],
        },
    )


def test_local_automation_rule_store_deletes_config_entry_rule() -> None:
    """Deleting a rule removes serialized config entry data by rule ID."""
    config_entry = MagicMock(
        data={
            "client_secret": "secret",
            "local_automation_rules": [
                {
                    "rule_id": "target-rule",
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
                },
                {
                    "rule_id": "other-rule",
                    "trigger": {
                        "device_id": "ldev_other_button",
                        "capability": "button_event",
                        "event": "single_press",
                    },
                    "actions": [
                        {
                            "type": "device_command",
                            "device_id": "ldev_other_light",
                            "capability": "power",
                            "command": "turn_on",
                        }
                    ],
                },
            ],
        }
    )
    hass = MagicMock()
    hass.data = {DOMAIN: {"config_entry": config_entry}}

    deleted = HomeAssistantLocalAutomationRuleStore(hass).delete_rule("target-rule")

    assert deleted is True
    hass.config_entries.async_update_entry.assert_called_once_with(
        config_entry,
        data={
            "client_secret": "secret",
            "local_automation_rules": [
                config_entry.data["local_automation_rules"][1],
            ],
        },
    )
