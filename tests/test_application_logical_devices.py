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
        attributes={"color_temp": 250, "min_mireds": 153, "max_mireds": 500},
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
            "constraints": {"min": 2000, "max": 6536, "step": 50},
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


def test_light_rgb_color_state_uses_channel_contract() -> None:
    """Home Assistant RGB lists are normalized to named channel values."""
    snapshot = EntityStateSnapshot(
        entity_id="light.desk",
        state="on",
        attributes={"rgb_color": [255, 120, 40]},
        name="Desk Light",
        domain="light",
        device_class="smart_light",
        capabilities=["rgb_color"],
        status="online",
        presentation={"card_template": "light_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["state"] == {
        "value": {"r": 255, "g": 120, "b": 40}
    }
    assert device["capabilities"][0]["commands"] == ["set_rgb_color"]


def test_lqi_signal_strength_uses_signal_quality_contract() -> None:
    """Legacy LQI signal strength is normalized to canonical signal quality."""
    snapshot = EntityStateSnapshot(
        entity_id="sensor.living_temperature",
        state="24.6",
        attributes={
            "unit_of_measurement": "°C",
            "signal_strength": 236,
            "signal_unit": "lqi",
        },
        name="Living Temperature",
        domain="sensor",
        device_class="environment_sensor",
        capabilities=["temperature", "signal_strength"],
        status="online",
        presentation={"card_template": "metric_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()
    signal_quality = next(
        capability
        for capability in device["capabilities"]
        if capability["type"] == "signal_quality"
    )

    assert signal_quality["state"] == {
        "value": 93,
        "unit": "percent",
        "raw_metric": {"kind": "lqi", "value": 236},
    }


def test_rssi_signal_strength_uses_signal_quality_contract() -> None:
    """Legacy RSSI signal strength is normalized to canonical signal quality."""
    snapshot = EntityStateSnapshot(
        entity_id="sensor.router_signal",
        state="-58",
        attributes={
            "signal_strength": -58,
            "signal_unit": "dBm",
        },
        name="Router Signal",
        domain="sensor",
        device_class="environment_sensor",
        capabilities=["signal_strength"],
        status="online",
        presentation={"card_template": "metric_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["state"] == {
        "value": 84,
        "unit": "percent",
        "raw_metric": {"kind": "rssi", "value": -58},
    }


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
            "aliases": [
                {
                    "kind": "home_assistant_entity_id",
                    "value": "light.desk",
                    "valid_from": None,
                    "valid_until": None,
                },
                {
                    "kind": "home_assistant_entity_id",
                    "value": "sensor.desk_battery",
                    "valid_from": None,
                    "valid_until": None,
                },
            ],
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
