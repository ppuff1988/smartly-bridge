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


def test_fan_percentage_state_uses_fan_speed_contract() -> None:
    """Home Assistant fan percentage is normalized to canonical fan speed."""
    snapshot = EntityStateSnapshot(
        entity_id="fan.bedroom",
        state="on",
        attributes={"percentage": 75},
        name="Bedroom Fan",
        domain="fan",
        device_class="fan_control",
        capabilities=["on_off", "fan_speed"],
        status="online",
        presentation={"card_template": "fan_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()
    fan_speed = next(
        capability
        for capability in device["capabilities"]
        if capability["type"] == "fan_speed"
    )

    assert fan_speed["state"] == {
        "percentage": 75,
        "unit": "percent",
    }
    assert fan_speed["constraints"] == {"min": 0, "max": 100, "step": 1}
    assert fan_speed["commands"] == ["set_fan_speed"]


def test_fan_preset_state_uses_fan_speed_contract() -> None:
    """Home Assistant fan preset mode is retained as canonical fan speed state."""
    snapshot = EntityStateSnapshot(
        entity_id="fan.bedroom",
        state="on",
        attributes={"preset_mode": "sleep"},
        name="Bedroom Fan",
        domain="fan",
        device_class="fan_control",
        capabilities=["fan_speed"],
        status="online",
        presentation={"card_template": "fan_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["state"] == {"speed": "sleep"}


def test_cover_position_state_uses_position_contract() -> None:
    """Home Assistant cover current position is normalized to canonical position."""
    snapshot = EntityStateSnapshot(
        entity_id="cover.living_curtain",
        state="open",
        attributes={"current_position": 55},
        name="Living Curtain",
        domain="cover",
        device_class="cover_control",
        capabilities=["open_close", "position"],
        status="online",
        presentation={"card_template": "cover_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()
    position = next(
        capability
        for capability in device["capabilities"]
        if capability["type"] == "position"
    )

    assert position["state"] == {"value": 55, "unit": "percent"}
    assert position["constraints"] == {"min": 0, "max": 100, "step": 1}


def test_cover_open_close_state_uses_open_close_contract() -> None:
    """Home Assistant cover state is normalized to canonical open/closed state."""
    snapshot = EntityStateSnapshot(
        entity_id="cover.living_curtain",
        state="closed",
        attributes={},
        name="Living Curtain",
        domain="cover",
        device_class="cover_control",
        capabilities=["open_close"],
        status="online",
        presentation={"card_template": "cover_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["state"] == {"value": "closed"}


def test_lock_state_uses_lock_contract() -> None:
    """Home Assistant lock state is normalized to canonical lock state."""
    snapshot = EntityStateSnapshot(
        entity_id="lock.front_door",
        state="locked",
        attributes={},
        name="Front Door",
        domain="lock",
        device_class="lock_control",
        capabilities=["lock"],
        status="online",
        presentation={"card_template": "lock_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["state"] == {"value": "locked"}
    assert device["capabilities"][0]["commands"] == ["lock", "unlock"]


def test_climate_hvac_mode_uses_mode_select_contract() -> None:
    """Home Assistant climate HVAC mode is normalized to canonical mode select."""
    snapshot = EntityStateSnapshot(
        entity_id="climate.living_room",
        state="cool",
        attributes={"hvac_mode": "cool", "hvac_modes": ["off", "heat", "cool", "auto"]},
        name="Living Room AC",
        domain="climate",
        device_class="climate_control",
        capabilities=["hvac_mode"],
        status="online",
        presentation={"card_template": "climate_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["type"] == "mode_select"
    assert device["capabilities"][0]["state"] == {"value": "cool"}
    assert device["capabilities"][0]["constraints"] == {
        "values": ["off", "heat", "cool", "auto"]
    }
    assert device["capabilities"][0]["commands"] == ["set_mode"]


def test_climate_target_temperature_uses_target_temperature_contract() -> None:
    """Home Assistant climate temperature is normalized to target temperature."""
    snapshot = EntityStateSnapshot(
        entity_id="climate.living_room",
        state="cool",
        attributes={
            "temperature": 24,
            "min_temp": 16,
            "max_temp": 30,
            "target_temp_step": 0.5,
            "unit_of_measurement": "°C",
        },
        name="Living Room AC",
        domain="climate",
        device_class="climate_control",
        capabilities=["target_temperature"],
        status="online",
        presentation={"card_template": "climate_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["type"] == "target_temperature"
    assert device["capabilities"][0]["state"] == {"value": 24, "unit": "celsius"}
    assert device["capabilities"][0]["constraints"] == {
        "min": 16,
        "max": 30,
        "step": 0.5,
    }
    assert device["capabilities"][0]["commands"] == ["set_temperature"]


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
