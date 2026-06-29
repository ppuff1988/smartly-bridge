"""Tests for logical device normalization."""

from __future__ import annotations

from custom_components.smartly_bridge.application.logical_devices import (
    logical_device_from_state,
    logical_devices_from_states,
)
from custom_components.smartly_bridge.domain.models import EntityStateSnapshot


def test_light_color_temperature_state_uses_kelvin_contract() -> None:
    """Home Assistant mired color temperature is normalized to canonical kelvin."""
    snapshot = EntityStateSnapshot(
        entity_id="light.desk",
        state="on",
        attributes={"color_temp": 250},
        name="Desk Light",
        domain="light",
        device_class="smart_light",
        capabilities=["color_temp"],
        status="online",
        presentation={"card_template": "light_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"] == [
        {
            "type": "color_temperature",
            "role": "primary",
            "readable": True,
            "writable": True,
            "event_only": False,
            "state": {"value": 4000, "unit": "kelvin"},
            "commands": ["set_color_temperature"],
            "events": [],
            "constraints": {},
            "presentation": {},
            "source_refs": [
                {
                    "source": "home_assistant",
                    "source_device_id": None,
                    "source_entity_id": "light.desk",
                    "domain": "light",
                    "role": "primary_control",
                    "capability_types": ["color_temperature"],
                }
            ],
        }
    ]


def test_sibling_entities_with_same_source_device_group_into_one_logical_device() -> None:
    """Source device ID is the primary grouping evidence for logical devices."""
    devices = [
        device.to_dict()
        for device in logical_devices_from_states(
            [
                EntityStateSnapshot(
                    entity_id="light.desk",
                    state="on",
                    attributes={"brightness": 128},
                    name="Desk Light",
                    domain="light",
                    device_class="smart_light",
                    capabilities=["on_off", "brightness"],
                    status="online",
                    presentation={"card_template": "light_card"},
                    source_device_id="ha-device-1",
                ),
                EntityStateSnapshot(
                    entity_id="sensor.desk_battery",
                    state="87",
                    attributes={"unit_of_measurement": "%"},
                    name="Desk Battery",
                    domain="sensor",
                    device_class="environment_sensor",
                    capabilities=["battery"],
                    status="online",
                    presentation={"card_template": "metric_card"},
                    source_device_id="ha-device-1",
                ),
            ]
        )
    ]

    assert devices == [
        {
            "id": "ldev_ha_device_1",
            "name": "Desk Light",
            "primary_type": "light",
            "device_class": "light_control",
            "status": "online",
            "source_entities": ["light.desk", "sensor.desk_battery"],
            "capabilities": [
                {
                    "type": "power",
                    "role": "primary",
                    "readable": True,
                    "writable": True,
                    "event_only": False,
                    "state": {"value": True},
                    "commands": ["turn_on", "turn_off", "toggle"],
                    "events": [],
                    "constraints": {},
                    "presentation": {},
                    "source_refs": [
                        {
                            "source": "home_assistant",
                            "source_device_id": "ha-device-1",
                            "source_entity_id": "light.desk",
                            "domain": "light",
                            "role": "primary_control",
                            "capability_types": ["power"],
                        }
                    ],
                },
                {
                    "type": "brightness",
                    "role": "primary",
                    "readable": True,
                    "writable": True,
                    "event_only": False,
                    "state": {"value": 50, "unit": "percent"},
                    "commands": ["set_brightness"],
                    "events": [],
                    "constraints": {"min": 0, "max": 100, "step": 1},
                    "presentation": {},
                    "source_refs": [
                        {
                            "source": "home_assistant",
                            "source_device_id": "ha-device-1",
                            "source_entity_id": "light.desk",
                            "domain": "light",
                            "role": "primary_control",
                            "capability_types": ["brightness"],
                        }
                    ],
                },
                {
                    "type": "battery",
                    "role": "health",
                    "readable": True,
                    "writable": False,
                    "event_only": False,
                    "state": {"value": 87, "unit": "percent"},
                    "commands": [],
                    "events": [],
                    "constraints": {},
                    "presentation": {},
                    "source_refs": [
                        {
                            "source": "home_assistant",
                            "source_device_id": "ha-device-1",
                            "source_entity_id": "sensor.desk_battery",
                            "domain": "sensor",
                            "role": "health",
                            "capability_types": ["battery"],
                        }
                    ],
                },
            ],
            "presentation": {
                "template": "light_control",
                "primary_controls": ["power", "brightness"],
                "status_badges": ["battery"],
            },
            "schema_version": "2026.06",
        }
    ]
