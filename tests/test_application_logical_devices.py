"""Tests for logical device normalization."""

from __future__ import annotations

from custom_components.smartly_bridge.application.logical_devices import (
    logical_device_from_state,
    logical_devices_from_states,
)
from custom_components.smartly_bridge.device_presentation import build_device_card_metadata
from custom_components.smartly_bridge.domain.models import EntityStateSnapshot


def _button_event_capability(
    entity_id: str,
    attributes: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    """Return metadata and the normalized button event capability."""
    metadata = build_device_card_metadata(entity_id, "unknown", attributes)
    snapshot = EntityStateSnapshot(
        entity_id=entity_id,
        state="unknown",
        attributes=attributes,
        name=str(attributes.get("friendly_name", entity_id)),
        domain=metadata["domain"],
        device_class=metadata["device_class"],
        capabilities=metadata["capabilities"],
        status=metadata["status"],
        presentation=metadata["presentation"],
    )
    device = logical_device_from_state(snapshot).to_dict()
    capability = next(item for item in device["capabilities"] if item["type"] == "button_event")
    return metadata, capability


def test_aqara_h1_profile_exposes_declared_channel_gestures() -> None:
    """Aqara H1 metadata declares each physical and combined rocker channel."""
    metadata, capability = _button_event_capability(
        "sensor.hall_remote_action",
        {
            "friendly_name": "Hall remote",
            "model": "WXKG15LM",
        },
    )

    assert metadata["device_class"] == "multi_button_device"
    assert capability["events"] == [
        "single_press",
        "double_press",
        "triple_press",
        "long_press",
    ]
    assert capability["constraints"] == {
        "event_schema_version": 1,
        "channels": [
            {
                "key": "left",
                "events": [
                    "single_press",
                    "double_press",
                    "triple_press",
                    "long_press",
                ],
            },
            {
                "key": "right",
                "events": [
                    "single_press",
                    "double_press",
                    "triple_press",
                    "long_press",
                ],
            },
            {
                "key": "both",
                "events": [
                    "single_press",
                    "double_press",
                    "triple_press",
                    "long_press",
                ],
            },
        ],
    }
    assert capability["presentation"] == {
        "channel_order": ["left", "right", "both"],
        "channel_labels": {
            "left": "Left",
            "right": "Right",
            "both": "Both",
        },
    }


def test_somrig_profile_preserves_release_gestures_per_button() -> None:
    """IKEA SOMRIG metadata exposes two independent button channels."""
    metadata, capability = _button_event_capability(
        "sensor.shortcut_remote_action",
        {
            "friendly_name": "Shortcut remote",
            "model": "E2213",
        },
    )

    assert metadata["device_class"] == "multi_button_device"
    assert capability["constraints"]["channels"] == [
        {
            "key": "button_1",
            "events": [
                "single_press",
                "double_press",
                "long_press",
                "long_release",
            ],
        },
        {
            "key": "button_2",
            "events": [
                "single_press",
                "double_press",
                "long_press",
                "long_release",
            ],
        },
    ]


def test_hue_dimmer_profile_keeps_functional_channel_names() -> None:
    """Hue dimmer metadata uses physical function names instead of numeric guesses."""
    metadata, capability = _button_event_capability(
        "sensor.living_room_dimmer_action",
        {
            "friendly_name": "Living room dimmer",
            "model": "929002398602",
        },
    )

    assert metadata["device_class"] == "multi_button_device"
    assert [channel["key"] for channel in capability["constraints"]["channels"]] == [
        "power",
        "brightness_up",
        "brightness_down",
        "scene",
    ]


def test_unknown_button_action_values_derive_declared_channels() -> None:
    """Unknown adapters can provide source action values without a model hard-code."""
    metadata, capability = _button_event_capability(
        "sensor.generic_remote_action",
        {
            "friendly_name": "Generic remote",
            "action_values": [
                "single_1",
                "double_1",
                "hold_1",
                "release_1",
                "single_2",
            ],
        },
    )

    assert metadata["device_class"] == "multi_button_device"
    assert capability["constraints"]["channels"] == [
        {
            "key": "button_1",
            "events": [
                "single_press",
                "double_press",
                "long_press",
                "long_release",
            ],
        },
        {"key": "button_2", "events": ["single_press"]},
    ]


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

    assert device["capabilities"][0]["state"] == {"value": {"r": 255, "g": 120, "b": 40}}
    assert device["capabilities"][0]["commands"] == ["set_rgb_color"]


def test_light_hs_color_state_uses_rgb_color_contract() -> None:
    """Home Assistant HS color is normalized to canonical RGB channel values."""
    snapshot = EntityStateSnapshot(
        entity_id="light.desk",
        state="on",
        attributes={"hs_color": [120, 100]},
        name="Desk Light",
        domain="light",
        device_class="smart_light",
        capabilities=["rgb_color"],
        status="online",
        presentation={"card_template": "light_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["state"] == {"value": {"r": 0, "g": 255, "b": 0}}
    assert device["capabilities"][0]["commands"] == ["set_rgb_color"]


def test_light_xy_color_state_uses_rgb_color_contract() -> None:
    """Home Assistant XY color is normalized to canonical RGB channel values."""
    snapshot = EntityStateSnapshot(
        entity_id="light.desk",
        state="on",
        attributes={"xy_color": [0.172, 0.747]},
        name="Desk Light",
        domain="light",
        device_class="smart_light",
        capabilities=["rgb_color"],
        status="online",
        presentation={"card_template": "light_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["state"] == {"value": {"r": 0, "g": 255, "b": 0}}
    assert device["capabilities"][0]["commands"] == ["set_rgb_color"]


def test_light_effect_metadata_and_state_use_effect_contract() -> None:
    """Home Assistant light effects are exposed as canonical effect controls."""
    metadata = build_device_card_metadata(
        "light.desk",
        "on",
        {
            "effect": "rainbow",
            "effect_list": ["rainbow", "pulse"],
        },
    )
    snapshot = EntityStateSnapshot(
        entity_id="light.desk",
        state="on",
        attributes={
            "effect": "rainbow",
            "effect_list": ["rainbow", "pulse"],
        },
        name="Desk Light",
        domain="light",
        device_class="smart_light",
        capabilities=metadata["capabilities"],
        status="online",
        presentation=metadata["presentation"],
    )

    device = logical_device_from_state(snapshot).to_dict()
    effect = next(
        capability for capability in device["capabilities"] if capability["type"] == "effect"
    )

    assert metadata["capabilities"] == ["on_off", "effect"]
    assert effect["role"] == "primary"
    assert effect["state"] == {"value": "rainbow"}
    assert effect["commands"] == ["set_effect"]
    assert effect["constraints"] == {"values": ["rainbow", "pulse"]}


def test_lqi_signal_strength_uses_signal_quality_contract() -> None:
    """Source LQI signal strength is normalized to canonical signal quality."""
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
    """Source RSSI signal strength is normalized to canonical signal quality."""
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


def test_air_quality_sensor_state_uses_measurement_contract() -> None:
    """Air-quality sensor device classes expose readable measurement state."""
    snapshot = EntityStateSnapshot(
        entity_id="sensor.living_co2",
        state="449.8",
        attributes={
            "device_class": "carbon_dioxide",
            "unit_of_measurement": "ppm",
        },
        name="Living CO2",
        domain="sensor",
        device_class="environment_sensor",
        capabilities=["carbon_dioxide"],
        status="online",
        presentation={"card_template": "metric_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["type"] == "carbon_dioxide"
    assert device["capabilities"][0]["role"] == "secondary"
    assert device["capabilities"][0]["readable"] is True
    assert device["capabilities"][0]["writable"] is False
    assert device["capabilities"][0]["state"] == {"value": "449.8", "unit": "ppm"}
    assert device["capabilities"][0]["commands"] == []


def test_environment_sensor_aliases_use_canonical_measurement_names() -> None:
    """Source environment aliases are normalized before logical sync."""
    devices = [
        device.to_dict()
        for device in logical_devices_from_states(
            [
                EntityStateSnapshot(
                    entity_id="sensor.living_co2",
                    state="449.8",
                    attributes={"unit_of_measurement": "ppm"},
                    name="Living CO2",
                    domain="sensor",
                    device_class="environment_sensor",
                    capabilities=["co2"],
                    status="online",
                    presentation={"card_template": "metric_card"},
                ),
                EntityStateSnapshot(
                    entity_id="sensor.outdoor_pressure",
                    state="1013.2",
                    attributes={"unit_of_measurement": "hPa"},
                    name="Outdoor Pressure",
                    domain="sensor",
                    device_class="environment_sensor",
                    capabilities=["atmospheric_pressure"],
                    status="online",
                    presentation={"card_template": "metric_card"},
                ),
            ]
        )
    ]

    assert [device["capabilities"][0]["type"] for device in devices] == [
        "carbon_dioxide",
        "pressure",
    ]
    assert [device["capabilities"][0]["state"] for device in devices] == [
        {"value": "449.8", "unit": "ppm"},
        {"value": "1013.2", "unit": "hPa"},
    ]


def test_electrical_sensor_metadata_uses_meter_capabilities() -> None:
    """Electrical sensor device classes are inferred as meter measurements."""
    metadata = build_device_card_metadata(
        "sensor.power_consumption",
        "12.3",
        {"device_class": "power", "unit_of_measurement": "W"},
    )

    assert metadata["device_class"] == "environment_sensor"
    assert metadata["capabilities"] == ["power_meter"]
    assert metadata["presentation"]["primary_metric"] == "power_meter"


def test_electrical_sensor_state_uses_meter_contract() -> None:
    """Electrical sensor capabilities expose read-only measurement state."""
    devices = [
        device.to_dict()
        for device in logical_devices_from_states(
            [
                EntityStateSnapshot(
                    entity_id="sensor.power_consumption",
                    state="12.3",
                    attributes={"unit_of_measurement": "W"},
                    name="Power Consumption",
                    domain="sensor",
                    device_class="environment_sensor",
                    capabilities=["power_meter"],
                    status="online",
                    presentation={"card_template": "metric_card"},
                ),
                EntityStateSnapshot(
                    entity_id="sensor.energy_total",
                    state="1.23",
                    attributes={"unit_of_measurement": "kWh"},
                    name="Energy Total",
                    domain="sensor",
                    device_class="environment_sensor",
                    capabilities=["energy_meter"],
                    status="online",
                    presentation={"card_template": "metric_card"},
                ),
            ]
        )
    ]

    assert [device["capabilities"][0]["type"] for device in devices] == [
        "power_meter",
        "energy_meter",
    ]
    assert [device["capabilities"][0]["role"] for device in devices] == [
        "secondary",
        "secondary",
    ]
    assert [device["capabilities"][0]["state"] for device in devices] == [
        {"value": "12.3", "unit": "W"},
        {"value": "1.23", "unit": "kWh"},
    ]


def test_motion_binary_sensor_state_uses_motion_contract() -> None:
    """Home Assistant motion binary sensors expose canonical boolean state."""
    snapshot = EntityStateSnapshot(
        entity_id="binary_sensor.hall_motion",
        state="on",
        attributes={"device_class": "motion"},
        name="Hall Motion",
        domain="binary_sensor",
        device_class="presence_sensor",
        capabilities=["motion"],
        status="online",
        presentation={"card_template": "binary_state_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["type"] == "motion"
    assert device["capabilities"][0]["role"] == "secondary"
    assert device["capabilities"][0]["state"] == {"value": True}
    assert device["capabilities"][0]["commands"] == []


def test_occupancy_binary_sensor_state_uses_presence_contract() -> None:
    """Source occupancy binary sensors are normalized to presence state."""
    snapshot = EntityStateSnapshot(
        entity_id="binary_sensor.office_presence",
        state="off",
        attributes={"device_class": "occupancy"},
        name="Office Presence",
        domain="binary_sensor",
        device_class="presence_sensor",
        capabilities=["occupancy"],
        status="online",
        presentation={"card_template": "binary_state_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["type"] == "presence"
    assert device["capabilities"][0]["role"] == "secondary"
    assert device["capabilities"][0]["state"] == {"value": False}


def test_contact_binary_sensor_state_uses_open_close_contract() -> None:
    """Home Assistant contact binary sensors map on/off to open/closed."""
    snapshot = EntityStateSnapshot(
        entity_id="binary_sensor.front_door",
        state="on",
        attributes={"device_class": "door"},
        name="Front Door",
        domain="binary_sensor",
        device_class="contact_sensor",
        capabilities=["door"],
        status="online",
        presentation={"card_template": "binary_state_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["type"] == "open_close"
    assert device["capabilities"][0]["role"] == "secondary"
    assert device["capabilities"][0]["state"] == {"value": "open"}
    assert device["capabilities"][0]["commands"] == []


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
        capability for capability in device["capabilities"] if capability["type"] == "fan_speed"
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


def test_fan_direction_uses_fan_direction_contract() -> None:
    """Home Assistant fan direction is normalized to canonical fan direction."""
    snapshot = EntityStateSnapshot(
        entity_id="fan.bedroom",
        state="on",
        attributes={"direction": "forward"},
        name="Bedroom Fan",
        domain="fan",
        device_class="fan_control",
        capabilities=["fan_direction"],
        status="online",
        presentation={"card_template": "fan_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["type"] == "fan_direction"
    assert device["capabilities"][0]["state"] == {"value": "forward"}
    assert device["capabilities"][0]["constraints"] == {"values": ["forward", "reverse"]}
    assert device["capabilities"][0]["commands"] == ["set_direction"]


def test_fan_oscillation_uses_fan_oscillation_contract() -> None:
    """Home Assistant fan oscillation is normalized to canonical fan oscillation."""
    snapshot = EntityStateSnapshot(
        entity_id="fan.bedroom",
        state="on",
        attributes={"oscillating": True},
        name="Bedroom Fan",
        domain="fan",
        device_class="fan_control",
        capabilities=["fan_oscillation"],
        status="online",
        presentation={"card_template": "fan_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["type"] == "fan_oscillation"
    assert device["capabilities"][0]["state"] == {"value": True}
    assert device["capabilities"][0]["constraints"] == {}
    assert device["capabilities"][0]["commands"] == ["set_oscillation"]


def test_climate_fan_mode_state_uses_fan_speed_contract() -> None:
    """Home Assistant climate fan mode is normalized to canonical fan speed."""
    snapshot = EntityStateSnapshot(
        entity_id="climate.living_room",
        state="cool",
        attributes={"fan_mode": "auto", "fan_modes": ["auto", "low", "high"]},
        name="Living Room AC",
        domain="climate",
        device_class="climate_control",
        capabilities=["fan_speed"],
        status="online",
        presentation={"card_template": "climate_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["state"] == {"speed": "auto"}
    assert device["capabilities"][0]["constraints"] == {"values": ["auto", "low", "high"]}
    assert device["capabilities"][0]["commands"] == ["set_fan_speed"]


def test_climate_preset_mode_uses_preset_mode_contract() -> None:
    """Home Assistant climate preset mode is normalized to canonical preset mode."""
    snapshot = EntityStateSnapshot(
        entity_id="climate.living_room",
        state="cool",
        attributes={
            "preset_mode": "eco",
            "preset_modes": ["eco", "comfort", "sleep"],
        },
        name="Living Room AC",
        domain="climate",
        device_class="climate_control",
        capabilities=["preset_mode"],
        status="online",
        presentation={"card_template": "climate_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["type"] == "preset_mode"
    assert device["capabilities"][0]["state"] == {"value": "eco"}
    assert device["capabilities"][0]["constraints"] == {"values": ["eco", "comfort", "sleep"]}
    assert device["capabilities"][0]["commands"] == ["set_preset_mode"]


def test_climate_swing_mode_uses_swing_mode_contract() -> None:
    """Home Assistant climate swing mode is normalized to canonical swing mode."""
    snapshot = EntityStateSnapshot(
        entity_id="climate.living_room",
        state="cool",
        attributes={
            "swing_mode": "vertical",
            "swing_modes": ["off", "vertical", "horizontal"],
        },
        name="Living Room AC",
        domain="climate",
        device_class="climate_control",
        capabilities=["swing_mode"],
        status="online",
        presentation={"card_template": "climate_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["type"] == "swing_mode"
    assert device["capabilities"][0]["state"] == {"value": "vertical"}
    assert device["capabilities"][0]["constraints"] == {"values": ["off", "vertical", "horizontal"]}
    assert device["capabilities"][0]["commands"] == ["set_swing_mode"]


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
        capability for capability in device["capabilities"] if capability["type"] == "position"
    )

    assert position["state"] == {"value": 55, "unit": "percent"}
    assert position["constraints"] == {"min": 0, "max": 100, "step": 1}


def test_cover_tilt_position_state_uses_tilt_position_contract() -> None:
    """Home Assistant cover tilt is normalized to canonical tilt position."""
    snapshot = EntityStateSnapshot(
        entity_id="cover.living_blind",
        state="open",
        attributes={"current_tilt_position": 35},
        name="Living Blind",
        domain="cover",
        device_class="cover_control",
        capabilities=["open_close", "tilt_position"],
        status="online",
        presentation={"card_template": "cover_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()
    tilt_position = next(
        capability for capability in device["capabilities"] if capability["type"] == "tilt_position"
    )

    assert tilt_position["state"] == {"value": 35, "unit": "percent"}
    assert tilt_position["constraints"] == {"min": 0, "max": 100, "step": 1}
    assert tilt_position["commands"] == ["set_tilt_position"]


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


def test_cover_stop_capability_merges_into_position_commands() -> None:
    """Source cover stop support is exposed through canonical position commands."""
    snapshot = EntityStateSnapshot(
        entity_id="cover.garage",
        state="open",
        attributes={},
        name="Garage Door",
        domain="cover",
        device_class="cover_control",
        capabilities=["open_close", "stop"],
        status="online",
        presentation={"card_template": "cover_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert [capability["type"] for capability in device["capabilities"]] == [
        "open_close",
        "position",
    ]
    assert device["capabilities"][0]["state"] == {"value": "open"}
    assert device["capabilities"][0]["commands"] == []
    assert device["capabilities"][1]["state"] == {}
    assert device["capabilities"][1]["commands"] == [
        "set_position",
        "open",
        "close",
        "stop",
    ]


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
    assert device["capabilities"][0]["constraints"] == {"values": ["off", "heat", "cool", "auto"]}
    assert device["capabilities"][0]["commands"] == ["set_mode"]


def test_presence_sibling_number_setting_uses_numeric_setting_contract() -> None:
    """Editable sibling number settings are exposed as canonical numeric settings."""
    snapshot = EntityStateSnapshot(
        entity_id="binary_sensor.presence",
        state="on",
        attributes={"device_class": "occupancy"},
        name="Presence Sensor",
        domain="binary_sensor",
        device_class="presence_sensor",
        capabilities=["presence"],
        status="online",
        presentation={
            "card_template": "binary_state_card",
            "setting_controls": [
                {
                    "key": "trigger_hold_seconds",
                    "entity_id": "number.presence_detection_delay",
                    "domain": "number",
                    "name": "Trigger hold seconds",
                    "action": "set_value",
                    "value": 15,
                    "min": 1,
                    "max": 120,
                    "step": 1,
                    "unit": "s",
                }
            ],
        },
        source_device_id="zigbee-presence-1",
    )

    device = logical_device_from_state(snapshot).to_dict()
    numeric_setting = next(
        capability
        for capability in device["capabilities"]
        if capability["type"] == "numeric_setting"
    )

    assert numeric_setting == {
        "type": "numeric_setting",
        "role": "setting",
        "readable": True,
        "writable": True,
        "event_only": False,
        "state": {"value": 15, "unit": "s"},
        "commands": ["set_value"],
        "events": [],
        "constraints": {"min": 1, "max": 120, "step": 1},
        "presentation": {
            "key": "trigger_hold_seconds",
            "name": "Trigger hold seconds",
        },
        "source_refs": [
            {
                "source": "home_assistant",
                "source_device_id": "zigbee-presence-1",
                "source_entity_id": "number.presence_detection_delay",
                "domain": "number",
                "role": "setting",
                "capability_types": ["numeric_setting"],
            }
        ],
    }
    assert "numeric_setting" in device["presentation"]["primary_controls"]


def test_multiple_number_settings_keep_all_numeric_setting_source_refs() -> None:
    """Repeated numeric setting controls retain every source entity reference."""
    snapshot = EntityStateSnapshot(
        entity_id="binary_sensor.presence",
        state="on",
        attributes={"device_class": "occupancy"},
        name="Presence Sensor",
        domain="binary_sensor",
        device_class="presence_sensor",
        capabilities=["presence"],
        status="online",
        presentation={
            "card_template": "binary_state_card",
            "setting_controls": [
                {
                    "key": "trigger_hold_seconds",
                    "entity_id": "number.presence_detection_delay",
                    "domain": "number",
                    "name": "Trigger hold seconds",
                    "action": "set_value",
                    "value": 15,
                    "min": 1,
                    "max": 120,
                    "step": 1,
                    "unit": "s",
                },
                {
                    "key": "cooldown_seconds",
                    "entity_id": "number.presence_cooldown",
                    "domain": "number",
                    "name": "Cooldown seconds",
                    "action": "set_value",
                    "value": 5,
                    "min": 1,
                    "max": 60,
                    "step": 1,
                    "unit": "s",
                },
            ],
        },
        source_device_id="zigbee-presence-1",
    )

    device = logical_device_from_state(snapshot).to_dict()
    numeric_setting = next(
        capability
        for capability in device["capabilities"]
        if capability["type"] == "numeric_setting"
    )

    assert [source_ref["source_entity_id"] for source_ref in numeric_setting["source_refs"]] == [
        "number.presence_detection_delay",
        "number.presence_cooldown",
    ]


def test_presence_sibling_select_setting_uses_option_setting_contract() -> None:
    """Editable sibling select settings are exposed as canonical option settings."""
    snapshot = EntityStateSnapshot(
        entity_id="binary_sensor.presence",
        state="on",
        attributes={"device_class": "occupancy"},
        name="Presence Sensor",
        domain="binary_sensor",
        device_class="presence_sensor",
        capabilities=["presence"],
        status="online",
        presentation={
            "card_template": "binary_state_card",
            "setting_controls": [
                {
                    "key": "occupancy_sensitivity",
                    "entity_id": "select.presence_occupancy_sensitivity",
                    "domain": "select",
                    "name": "Occupancy sensitivity",
                    "action": "select_option",
                    "value": "low",
                    "options": ["low", "medium", "high"],
                }
            ],
        },
        source_device_id="zigbee-presence-1",
    )

    device = logical_device_from_state(snapshot).to_dict()
    option_setting = next(
        capability
        for capability in device["capabilities"]
        if capability["type"] == "option_setting"
    )

    assert option_setting == {
        "type": "option_setting",
        "role": "setting",
        "readable": True,
        "writable": True,
        "event_only": False,
        "state": {"value": "low"},
        "commands": ["select_option"],
        "events": [],
        "constraints": {"values": ["low", "medium", "high"]},
        "presentation": {
            "key": "occupancy_sensitivity",
            "name": "Occupancy sensitivity",
        },
        "source_refs": [
            {
                "source": "home_assistant",
                "source_device_id": "zigbee-presence-1",
                "source_entity_id": "select.presence_occupancy_sensitivity",
                "domain": "select",
                "role": "setting",
                "capability_types": ["option_setting"],
            }
        ],
    }
    assert "option_setting" in device["presentation"]["primary_controls"]


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


def test_climate_temperature_range_uses_target_temperature_range_contract() -> None:
    """Home Assistant heat/cool range is normalized to target temperature range."""
    snapshot = EntityStateSnapshot(
        entity_id="climate.living_room",
        state="heat_cool",
        attributes={
            "target_temp_low": 22,
            "target_temp_high": 26,
            "min_temp": 16,
            "max_temp": 30,
            "target_temp_step": 0.5,
            "unit_of_measurement": "°C",
        },
        name="Living Room AC",
        domain="climate",
        device_class="climate_control",
        capabilities=["target_temperature_range"],
        status="online",
        presentation={"card_template": "climate_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0]["type"] == "target_temperature_range"
    assert device["capabilities"][0]["state"] == {
        "low": 22,
        "high": 26,
        "unit": "celsius",
    }
    assert device["capabilities"][0]["constraints"] == {
        "min": 16,
        "max": 30,
        "step": 0.5,
    }
    assert device["capabilities"][0]["commands"] == ["set_temperature_range"]


def test_scene_run_capability_uses_command_only_contract() -> None:
    """Home Assistant scenes expose a canonical command-only run capability."""
    snapshot = EntityStateSnapshot(
        entity_id="scene.movie_night",
        state="2026-06-29T12:00:00+00:00",
        attributes={},
        name="Movie Night",
        domain="scene",
        device_class="scene_trigger",
        capabilities=["run"],
        status="online",
        presentation={"card_template": "scene_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["capabilities"][0] == {
        "type": "run",
        "role": "primary",
        "readable": False,
        "writable": True,
        "event_only": False,
        "state": {},
        "commands": ["run"],
        "events": [],
        "constraints": {},
        "presentation": {},
        "source_refs": [
            {
                "source": "home_assistant",
                "source_device_id": None,
                "source_entity_id": "scene.movie_night",
                "domain": "scene",
                "role": "primary_control",
                "capability_types": ["run"],
            }
        ],
    }


def test_button_entity_exposes_press_command_capability() -> None:
    """Home Assistant button entities expose a canonical press command capability."""
    snapshot = EntityStateSnapshot(
        entity_id="button.desk_scene",
        state="idle",
        attributes={},
        name="Desk Scene",
        domain="button",
        device_class="button_device",
        capabilities=["event", "button_press"],
        status="online",
        presentation={"card_template": "event_card"},
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert [capability["type"] for capability in device["capabilities"]] == [
        "button_event",
        "button_press",
    ]
    button_press = device["capabilities"][1]
    assert button_press == {
        "type": "button_press",
        "role": "primary",
        "readable": False,
        "writable": True,
        "event_only": False,
        "state": {},
        "commands": ["press"],
        "events": [],
        "constraints": {},
        "presentation": {},
        "source_refs": [
            {
                "source": "home_assistant",
                "source_device_id": None,
                "source_entity_id": "button.desk_scene",
                "domain": "button",
                "role": "primary_control",
                "capability_types": ["button_press"],
            }
        ],
    }
    assert device["presentation"]["primary_controls"] == ["button_press"]


def test_input_button_helper_exposes_press_command_capability() -> None:
    """Home Assistant input_button helpers behave as Smartly button devices."""
    metadata = build_device_card_metadata(
        "input_button.an_niu",
        "2026-07-03T13:00:00+00:00",
        {"friendly_name": "按鈕"},
        {"smartly"},
    )
    snapshot = EntityStateSnapshot(
        entity_id="input_button.an_niu",
        state="2026-07-03T13:00:00+00:00",
        attributes={"friendly_name": "按鈕"},
        name="按鈕",
        domain=metadata["domain"],
        device_class=metadata["device_class"],
        capabilities=metadata["capabilities"],
        status=metadata["status"],
        presentation=metadata["presentation"],
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["primary_type"] == "button"
    assert device["device_class"] == "button_automation"
    assert [capability["type"] for capability in device["capabilities"]] == [
        "button_event",
        "button_press",
    ]
    assert device["presentation"]["template"] == "button_automation"
    assert device["presentation"]["primary_controls"] == ["button_press"]


def test_input_boolean_helper_exposes_power_capability() -> None:
    """Home Assistant input_boolean helpers behave as Smartly switch devices."""
    metadata = build_device_card_metadata(
        "input_boolean.kai_guan",
        "off",
        {"friendly_name": "開關"},
        {"smartly"},
    )
    snapshot = EntityStateSnapshot(
        entity_id="input_boolean.kai_guan",
        state="off",
        attributes={"friendly_name": "開關"},
        name="開關",
        domain=metadata["domain"],
        device_class=metadata["device_class"],
        capabilities=metadata["capabilities"],
        status=metadata["status"],
        presentation=metadata["presentation"],
    )

    device = logical_device_from_state(snapshot).to_dict()

    assert device["primary_type"] == "switch"
    assert device["device_class"] == "switch_control"
    assert [capability["type"] for capability in device["capabilities"]] == ["power"]
    assert device["capabilities"][0]["commands"] == ["turn_on", "turn_off", "toggle"]
    assert device["presentation"]["template"] == "switch_control"
    assert device["presentation"]["primary_controls"] == ["power"]


def test_input_number_helper_exposes_numeric_setting_capability() -> None:
    """Home Assistant input_number helpers expose bounded numeric controls."""
    attributes = {
        "friendly_name": "觸發維持秒數",
        "min": 1,
        "max": 120,
        "step": 1,
        "unit_of_measurement": "s",
    }
    metadata = build_device_card_metadata(
        "input_number.trigger_hold_seconds",
        "15",
        attributes,
        {"smartly"},
    )
    snapshot = EntityStateSnapshot(
        entity_id="input_number.trigger_hold_seconds",
        state="15",
        attributes=attributes,
        name="觸發維持秒數",
        domain=metadata["domain"],
        device_class=metadata["device_class"],
        capabilities=metadata["capabilities"],
        status=metadata["status"],
        presentation=metadata["presentation"],
    )

    device = logical_device_from_state(snapshot).to_dict()
    capability = device["capabilities"][0]

    assert device["primary_type"] == "setting"
    assert device["device_class"] == "setting_control"
    assert capability["type"] == "numeric_setting"
    assert capability["state"] == {"value": 15, "unit": "s"}
    assert capability["constraints"] == {"min": 1, "max": 120, "step": 1}
    assert capability["commands"] == ["set_value"]
    assert capability["source_refs"][0]["domain"] == "input_number"
    assert device["presentation"]["template"] == "setting_control"
    assert device["presentation"]["primary_controls"] == ["numeric_setting"]


def test_input_select_helper_exposes_option_setting_capability() -> None:
    """Home Assistant input_select helpers expose constrained option controls."""
    attributes = {
        "friendly_name": "感應強度",
        "options": ["low", "medium", "high"],
    }
    metadata = build_device_card_metadata(
        "input_select.occupancy_sensitivity",
        "medium",
        attributes,
        {"smartly"},
    )
    snapshot = EntityStateSnapshot(
        entity_id="input_select.occupancy_sensitivity",
        state="medium",
        attributes=attributes,
        name="感應強度",
        domain=metadata["domain"],
        device_class=metadata["device_class"],
        capabilities=metadata["capabilities"],
        status=metadata["status"],
        presentation=metadata["presentation"],
    )

    device = logical_device_from_state(snapshot).to_dict()
    capability = device["capabilities"][0]

    assert device["primary_type"] == "setting"
    assert device["device_class"] == "setting_control"
    assert capability["type"] == "option_setting"
    assert capability["state"] == {"value": "medium"}
    assert capability["constraints"] == {"values": ["low", "medium", "high"]}
    assert capability["commands"] == ["select_option"]
    assert capability["source_refs"][0]["domain"] == "input_select"
    assert device["presentation"]["template"] == "setting_control"
    assert device["presentation"]["primary_controls"] == ["option_setting"]


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
            "raw_refs": [],
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
                    "commands": [
                        "set_brightness",
                        "increase_brightness",
                        "decrease_brightness",
                    ],
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


def test_logical_device_aggregates_label_trace_diagnostics() -> None:
    """Grouped logical devices retain per-source label decisions for support diagnostics."""
    devices = [
        device.to_dict()
        for device in logical_devices_from_states(
            [
                EntityStateSnapshot(
                    entity_id="light.kitchen_main",
                    state="on",
                    attributes={"brightness": 128},
                    name="Kitchen Main",
                    domain="light",
                    device_class="smart_light",
                    capabilities=["on_off", "brightness"],
                    status="online",
                    presentation={"card_template": "light_card"},
                    source_device_id="kitchen-group",
                    diagnostics={
                        "label_trace": {
                            "source": "home_assistant",
                            "entities": [
                                {
                                    "source_entity_id": "light.kitchen_main",
                                    "exposed": True,
                                    "exposed_by": "smartly",
                                    "hidden": False,
                                    "class_override": {
                                        "label": "smartly.class.smart_light",
                                        "accepted": True,
                                        "resolved_device_class": "smart_light",
                                        "reason": "override compatible with light capability shape",
                                    },
                                    "group": {
                                        "label": "smartly.group.kitchen",
                                        "resolved_group_key": "kitchen",
                                    },
                                    "presentation_hints": ["smartly.dashboard"],
                                }
                            ],
                        }
                    },
                ),
                EntityStateSnapshot(
                    entity_id="sensor.kitchen_battery",
                    state="88",
                    attributes={"unit_of_measurement": "%"},
                    name="Kitchen Battery",
                    domain="sensor",
                    device_class="environment_sensor",
                    capabilities=["battery"],
                    status="online",
                    presentation={"card_template": "metric_card"},
                    source_device_id="kitchen-group",
                    diagnostics={
                        "label_trace": {
                            "source": "home_assistant",
                            "entities": [
                                {
                                    "source_entity_id": "sensor.kitchen_battery",
                                    "exposed": True,
                                    "exposed_by": "smartly",
                                    "hidden": False,
                                }
                            ],
                        }
                    },
                ),
            ]
        )
    ]

    assert devices[0]["diagnostics"]["label_trace"] == {
        "source": "home_assistant",
        "entities": [
            {
                "source_entity_id": "light.kitchen_main",
                "exposed": True,
                "exposed_by": "smartly",
                "hidden": False,
                "class_override": {
                    "label": "smartly.class.smart_light",
                    "accepted": True,
                    "resolved_device_class": "smart_light",
                    "reason": "override compatible with light capability shape",
                },
                "group": {
                    "label": "smartly.group.kitchen",
                    "resolved_group_key": "kitchen",
                },
                "presentation_hints": ["smartly.dashboard"],
            },
            {
                "source_entity_id": "sensor.kitchen_battery",
                "exposed": True,
                "exposed_by": "smartly",
                "hidden": False,
            },
        ],
    }
