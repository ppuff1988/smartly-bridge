"""Logical device normalization for migration toward capability contracts."""

from __future__ import annotations

import colorsys
import re
from collections import OrderedDict
from typing import Any

from ..domain.models import EntityStateSnapshot, SmartlyCapability, SmartlyLogicalDevice

_WRITABLE_CAPABILITIES = {
    "power",
    "brightness",
    "color_temperature",
    "rgb_color",
    "effect",
    "target_temperature",
    "target_temperature_range",
    "position",
    "tilt_position",
    "fan_speed",
    "fan_direction",
    "fan_oscillation",
    "mode_select",
    "preset_mode",
    "swing_mode",
    "numeric_setting",
    "option_setting",
    "lock",
    "run",
    "button_press",
}

_MEASUREMENT_CAPABILITIES = {
    "temperature",
    "humidity",
    "air_quality",
    "aqi",
    "carbon_dioxide",
    "carbon_monoxide",
    "pm25",
    "pm10",
    "current",
    "energy_meter",
    "power_meter",
    "pressure",
    "atmospheric_pressure",
    "voltage",
    "illuminance",
}


def logical_device_from_state(snapshot: EntityStateSnapshot) -> SmartlyLogicalDevice:
    """Build a shadow logical device from normalized entity metadata."""
    return _logical_device_from_group([snapshot])


def logical_devices_from_states(
    snapshots: list[EntityStateSnapshot],
) -> list[SmartlyLogicalDevice]:
    """Build grouped logical devices from normalized entity state snapshots."""
    parents: dict[str, str] = {}

    def find(key: str) -> str:
        parents.setdefault(key, key)
        if parents[key] != key:
            parents[key] = find(parents[key])
        return parents[key]

    def union(left: str, right: str) -> None:
        parents[find(right)] = find(left)

    for snapshot in snapshots:
        keys = _group_membership_keys(snapshot)
        for key in keys:
            parents.setdefault(key, key)
        for key in keys[1:]:
            union(keys[0], key)

    grouped: OrderedDict[str, list[EntityStateSnapshot]] = OrderedDict()
    for snapshot in snapshots:
        grouped.setdefault(find(_group_membership_keys(snapshot)[0]), []).append(snapshot)

    return [_logical_device_from_group(group) for group in grouped.values()]


def logical_device_id_for_source_id(source_id: str) -> str:
    """Return the deterministic logical device ID for a source identifier."""
    return _logical_device_id(source_id)


def canonical_capability_name(capability: str) -> str:
    """Return the canonical capability name for a source capability."""
    return _canonical_capability(capability)


def _logical_device_from_group(snapshots: list[EntityStateSnapshot]) -> SmartlyLogicalDevice:
    """Build a logical device from one source-device group."""
    primary = _primary_snapshot(snapshots)
    canonical_capabilities = _capabilities_from_group(snapshots)
    return SmartlyLogicalDevice(
        id=_logical_device_id(_logical_device_source_id(primary)),
        name=primary.name or primary.entity_id,
        primary_type=_primary_type_for_snapshot(primary),
        device_class=_logical_device_class(primary),
        status=_group_status(snapshots),
        source_entities=[snapshot.entity_id for snapshot in snapshots],
        capabilities=canonical_capabilities,
        aliases=_aliases_for_group(snapshots),
        presentation=_logical_device_presentation(
            primary.presentation,
            canonical_capabilities,
        ),
        diagnostics=_diagnostics_for_group(snapshots),
    )


def _group_membership_keys(snapshot: EntityStateSnapshot) -> list[str]:
    """Return grouping memberships for source-device and label-derived grouping."""
    keys = [snapshot.source_device_id or snapshot.entity_id]
    label_group_key = _label_trace_group_key(snapshot)
    if label_group_key is not None:
        keys.append(f"smartly.group.{label_group_key}")
    return keys


def _logical_device_source_id(snapshot: EntityStateSnapshot) -> str:
    """Return the logical-device source identifier used for stable IDs."""
    label_group_key = _label_trace_group_key(snapshot)
    if label_group_key is not None:
        return f"smartly_group_{label_group_key}"
    return snapshot.source_device_id or snapshot.entity_id


def _label_trace_group_key(snapshot: EntityStateSnapshot) -> str | None:
    """Return the resolved smartly.group key from snapshot diagnostics."""
    for entity_trace in _label_trace_entities(snapshot):
        group = entity_trace.get("group")
        if not isinstance(group, dict):
            continue
        resolved_group_key = group.get("resolved_group_key")
        if isinstance(resolved_group_key, str) and resolved_group_key:
            return resolved_group_key
    return None


def _diagnostics_for_group(snapshots: list[EntityStateSnapshot]) -> dict[str, Any]:
    """Aggregate support-only diagnostics for a logical device group."""
    label_trace_entities: list[dict[str, Any]] = []
    for snapshot in snapshots:
        label_trace_entities.extend(_label_trace_entities(snapshot))
    if not label_trace_entities:
        return {}
    return {
        "label_trace": {
            "source": "home_assistant",
            "entities": label_trace_entities,
        }
    }


def _label_trace_entities(snapshot: EntityStateSnapshot) -> list[dict[str, Any]]:
    """Return per-entity label trace entries from a snapshot."""
    label_trace = snapshot.diagnostics.get("label_trace")
    if not isinstance(label_trace, dict):
        return []
    entities = label_trace.get("entities")
    if not isinstance(entities, list):
        return []
    return [entity for entity in entities if isinstance(entity, dict)]


def _primary_snapshot(snapshots: list[EntityStateSnapshot]) -> EntityStateSnapshot:
    """Select the primary source entity for grouped presentation metadata."""
    for snapshot in snapshots:
        has_writable_capability = any(
            _canonical_capability(capability) in _WRITABLE_CAPABILITIES
            for capability in snapshot.capabilities
        )
        if has_writable_capability:
            return snapshot
    return snapshots[0]


def _group_status(snapshots: list[EntityStateSnapshot]) -> str | None:
    """Return the best aggregate status for a logical-device group."""
    statuses = [snapshot.status for snapshot in snapshots if snapshot.status]
    if "online" in statuses:
        return "online"
    return statuses[0] if statuses else None


def _capabilities_from_group(snapshots: list[EntityStateSnapshot]) -> list[SmartlyCapability]:
    """Return de-duplicated capabilities while retaining all source references."""
    capabilities: OrderedDict[str, SmartlyCapability] = OrderedDict()
    for snapshot in snapshots:
        for source_capability in snapshot.capabilities:
            capability = _capability_from_snapshot(snapshot, source_capability)
            existing = capabilities.get(capability.type)
            if existing is None:
                capabilities[capability.type] = capability
                continue
            capabilities[capability.type] = _merge_capability_source_refs(
                existing,
                capability,
            )
    for capability in _setting_capabilities_from_presentation(_primary_snapshot(snapshots)):
        existing = capabilities.get(capability.type)
        if existing is None:
            capabilities[capability.type] = capability
            continue
        capabilities[capability.type] = _merge_capability_source_refs(
            existing,
            capability,
        )
    return list(capabilities.values())


def _merge_capability_source_refs(
    existing: SmartlyCapability,
    incoming: SmartlyCapability,
) -> SmartlyCapability:
    """Return an existing capability with the incoming source refs appended."""
    return SmartlyCapability(
        type=existing.type,
        role=existing.role,
        readable=existing.readable,
        writable=existing.writable,
        event_only=existing.event_only,
        state=existing.state,
        commands=existing.commands,
        events=existing.events,
        constraints=existing.constraints,
        presentation=existing.presentation,
        source_refs=[*existing.source_refs, *incoming.source_refs],
    )


def _aliases_for_group(snapshots: list[EntityStateSnapshot]) -> list[dict[str, Any]]:
    """Return migration aliases for a logical device group."""
    return [
        {
            "kind": "home_assistant_entity_id",
            "value": snapshot.entity_id,
            "valid_from": None,
            "valid_until": None,
        }
        for snapshot in snapshots
    ]


def _logical_device_id(entity_id: str) -> str:
    """Return a deterministic logical device ID for migration aliases."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", entity_id).strip("_").lower()
    return f"ldev_{normalized}"


def _primary_type_for_snapshot(snapshot: EntityStateSnapshot) -> str:
    """Map existing entity metadata to a Smartly primary type."""
    domain = snapshot.domain or snapshot.entity_id.split(".", 1)[0]
    if snapshot.device_class == "presence_sensor":
        return "presence_sensor"
    if snapshot.device_class == "contact_sensor":
        return "contact_sensor"
    if snapshot.device_class == "environment_sensor":
        return "environment_sensor"
    if domain == "binary_sensor":
        return "sensor"
    return domain or "unknown"


def _logical_device_class(snapshot: EntityStateSnapshot) -> str:
    """Map existing presentation classes to API vNext device classes."""
    mapping = {
        "smart_light": "light_control",
        "simple_light_switch": "light_control",
        "simple_switch": "switch_control",
        "fan_control": "fan_control",
        "environment_sensor": "sensor_summary",
        "presence_sensor": "sensor_summary",
        "contact_sensor": "sensor_summary",
        "button_device": "button_automation",
        "multi_button_device": "button_automation",
        "cover_control": "cover_control",
        "climate_control": "climate_control",
        "scene_trigger": "scene_trigger",
    }
    return mapping.get(snapshot.device_class or "", "diagnostic_device")


def _capability_from_snapshot(snapshot: EntityStateSnapshot, capability: str) -> SmartlyCapability:
    """Map source presentation capabilities to canonical capability contracts."""
    canonical = _canonical_capability(capability)
    state = _capability_state(snapshot, canonical)
    return SmartlyCapability(
        type=canonical,
        role=_capability_role(canonical),
        readable=canonical not in {"button_event", "run", "button_press"},
        writable=canonical in _WRITABLE_CAPABILITIES,
        event_only=canonical == "button_event",
        state=state,
        commands=_commands_for_capability(canonical),
        constraints=_constraints_for_capability(snapshot, canonical),
        source_refs=[_source_ref(snapshot, canonical)],
    )


def _canonical_capability(capability: str) -> str:
    """Return the canonical capability name for a source capability."""
    return {
        "on_off": "power",
        "color_temp": "color_temperature",
        "hvac_mode": "mode_select",
        "signal_strength": "signal_quality",
        "co2": "carbon_dioxide",
        "energy": "energy_meter",
        "atmospheric_pressure": "pressure",
        "event": "button_event",
        "occupancy": "presence",
        "contact": "open_close",
        "opening": "open_close",
        "door": "open_close",
        "window": "open_close",
        "stop": "position",
    }.get(capability, capability)


def _capability_role(capability: str) -> str:
    """Return the canonical role for a capability."""
    if capability in {"battery", "signal_quality"}:
        return "health"
    if capability == "button_event":
        return "event_source"
    if capability in {"numeric_setting", "option_setting"}:
        return "setting"
    if capability in {*_MEASUREMENT_CAPABILITIES, "motion", "presence", "open_close"}:
        return "secondary"
    return "primary"


def _capability_state(snapshot: EntityStateSnapshot, capability: str) -> dict[str, Any]:
    """Return a normalized state payload for a capability when available."""
    attributes = snapshot.attributes or {}
    if capability == "power":
        return {"value": snapshot.state == "on"}
    if capability == "brightness":
        brightness = attributes.get("brightness")
        if isinstance(brightness, (int, float)):
            return {
                "value": round(max(0, min(255, brightness)) / 255 * 100),
                "unit": "percent",
            }
    if capability == "color_temperature" and "color_temp" in attributes:
        kelvin = _mired_to_kelvin(attributes["color_temp"])
        if kelvin is not None:
            return {"value": kelvin, "unit": "kelvin"}
    if capability == "rgb_color" and "rgb_color" in attributes:
        rgb_color = _rgb_color_value(attributes["rgb_color"])
        if rgb_color is not None:
            return {"value": rgb_color}
    if capability == "rgb_color" and "hs_color" in attributes:
        rgb_color = _hs_color_value(attributes["hs_color"])
        if rgb_color is not None:
            return {"value": rgb_color}
    if capability == "rgb_color" and "xy_color" in attributes:
        rgb_color = _xy_color_value(attributes["xy_color"])
        if rgb_color is not None:
            return {"value": rgb_color}
    if capability == "battery":
        return _numeric_state(snapshot, default_unit="percent")
    if capability == "signal_quality":
        return _signal_quality_state(snapshot)
    if capability == "target_temperature":
        return _target_temperature_state(snapshot)
    if capability == "target_temperature_range":
        return _target_temperature_range_state(snapshot)
    if capability == "fan_speed":
        return _fan_speed_state(snapshot)
    if capability == "fan_direction":
        return _fan_direction_state(snapshot)
    if capability == "fan_oscillation":
        return _fan_oscillation_state(snapshot)
    if capability == "position":
        return _position_state(snapshot)
    if capability == "tilt_position":
        return _tilt_position_state(snapshot)
    if capability in {"motion", "presence"}:
        return _binary_boolean_state(snapshot)
    if capability == "open_close":
        return _open_close_state(snapshot)
    if capability == "lock":
        return _lock_state(snapshot)
    if capability == "mode_select":
        return _mode_select_state(snapshot)
    if capability == "preset_mode":
        return _preset_mode_state(snapshot)
    if capability == "swing_mode":
        return _swing_mode_state(snapshot)
    if capability in attributes:
        state: dict[str, Any] = {"value": attributes[capability]}
        unit = attributes.get("unit_of_measurement")
        if unit:
            state["unit"] = unit
        return state
    if capability in _MEASUREMENT_CAPABILITIES:
        state = {"value": snapshot.state}
        unit = attributes.get("unit_of_measurement")
        if unit:
            state["unit"] = unit
        return state
    return {}


def _setting_capabilities_from_presentation(
    snapshot: EntityStateSnapshot,
) -> list[SmartlyCapability]:
    """Return canonical capabilities for editable sibling setting controls."""
    capabilities: list[SmartlyCapability] = []
    for control in snapshot.presentation.get("setting_controls", []):
        if control.get("domain") == "number" and control.get("action") == "set_value":
            state: dict[str, Any] = {"value": control.get("value")}
            if control.get("unit"):
                state["unit"] = control["unit"]
            constraints = {
                key: control[key]
                for key in ("min", "max", "step")
                if key in control
            }
            capabilities.append(
                _setting_capability_from_control(
                    snapshot,
                    control,
                    capability_type="numeric_setting",
                    command="set_value",
                    state=state,
                    constraints=constraints,
                )
            )
        if control.get("domain") == "select" and control.get("action") == "select_option":
            options = control.get("options")
            constraints = {"values": options} if isinstance(options, list) else {}
            capabilities.append(
                _setting_capability_from_control(
                    snapshot,
                    control,
                    capability_type="option_setting",
                    command="select_option",
                    state={"value": control.get("value")},
                    constraints=constraints,
                )
            )
    return capabilities


def _setting_capability_from_control(
    snapshot: EntityStateSnapshot,
    control: dict[str, Any],
    *,
    capability_type: str,
    command: str,
    state: dict[str, Any],
    constraints: dict[str, Any],
) -> SmartlyCapability:
    """Return a canonical setting capability from a presentation control."""
    domain = str(control.get("domain"))
    return SmartlyCapability(
        type=capability_type,
        role="setting",
        readable=True,
        writable=True,
        state=state,
        commands=[command],
        constraints=constraints,
        presentation={
            "key": control.get("key"),
            "name": control.get("name"),
        },
        source_refs=[
            {
                "source": "home_assistant",
                "source_device_id": snapshot.source_device_id,
                "source_entity_id": control["entity_id"],
                "domain": domain,
                "role": "setting",
                "capability_types": [capability_type],
            }
        ],
    )


def _numeric_state(
    snapshot: EntityStateSnapshot,
    *,
    default_unit: str | None = None,
) -> dict[str, Any]:
    """Return a normalized numeric state payload when possible."""
    value = _numeric_value(snapshot.attributes.get("battery") if snapshot.attributes else None)
    if value is None:
        value = _numeric_value(snapshot.state)
    if value is None:
        return {}

    state: dict[str, Any] = {"value": value}
    unit = _normalized_unit(
        (snapshot.attributes or {}).get("unit_of_measurement"),
        default_unit=default_unit,
    )
    if unit:
        state["unit"] = unit
    return state


def _numeric_value(value: Any) -> int | float | None:
    """Return int or float for numeric values."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return value
    if not isinstance(value, str):
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _normalized_unit(value: Any, *, default_unit: str | None = None) -> str | None:
    """Return a canonical unit name for capability state."""
    if value == "%":
        return "percent"
    if isinstance(value, str) and value:
        return value
    return default_unit


def _temperature_unit(value: Any) -> str:
    """Return canonical temperature unit names."""
    if value in {"°F", "F", "fahrenheit"}:
        return "fahrenheit"
    return "celsius"


def _signal_quality_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical signal quality state from source signal metadata."""
    attributes = snapshot.attributes or {}
    raw_value = _numeric_value(attributes.get("signal_strength"))
    if raw_value is None:
        raw_value = _numeric_value(attributes.get("linkquality"))
    if raw_value is None:
        raw_value = _numeric_value(attributes.get("link_quality"))
    if raw_value is None:
        raw_value = _numeric_value(attributes.get("lqi"))
    if raw_value is None:
        return {}

    signal_unit = attributes.get("signal_unit")
    raw_kind = _signal_raw_kind(signal_unit)
    if raw_kind == "lqi":
        value = round(max(0, min(255, raw_value)) / 255 * 100)
    elif raw_kind == "rssi":
        value = round(max(0, min(100, (raw_value + 100) * 2)))
    else:
        value = max(0, min(100, raw_value))

    return {
        "value": value,
        "unit": "percent",
        "raw_metric": {"kind": raw_kind, "value": raw_value},
    }


def _signal_raw_kind(signal_unit: Any) -> str:
    """Return the raw signal metric kind from source signal metadata."""
    if signal_unit == "lqi":
        return "lqi"
    if signal_unit == "dBm":
        return "rssi"
    return "signal_strength"


def _fan_speed_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical fan speed state from Home Assistant fan metadata."""
    attributes = snapshot.attributes or {}
    percentage = _numeric_value(attributes.get("percentage"))
    if percentage is None:
        fan_mode = attributes.get("fan_mode")
        if isinstance(fan_mode, str):
            return {"speed": fan_mode}
        preset_mode = attributes.get("preset_mode")
        return {"speed": preset_mode} if isinstance(preset_mode, str) else {}
    return {"percentage": max(0, min(100, percentage)), "unit": "percent"}


def _fan_direction_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical fan direction state from Home Assistant fan metadata."""
    direction = (snapshot.attributes or {}).get("direction")
    return {"value": direction} if isinstance(direction, str) else {}


def _fan_oscillation_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical fan oscillation state from Home Assistant fan metadata."""
    oscillating = (snapshot.attributes or {}).get("oscillating")
    return {"value": oscillating} if isinstance(oscillating, bool) else {}


def _target_temperature_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical target temperature from Home Assistant climate metadata."""
    attributes = snapshot.attributes or {}
    temperature = _numeric_value(attributes.get("target_temperature"))
    if temperature is None:
        temperature = _numeric_value(attributes.get("target_temp"))
    if temperature is None:
        temperature = _numeric_value(attributes.get("temperature"))
    if temperature is None:
        return {}
    return {
        "value": temperature,
        "unit": _temperature_unit(attributes.get("unit_of_measurement")),
    }


def _target_temperature_range_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical target temperature range from Home Assistant climate metadata."""
    attributes = snapshot.attributes or {}
    low = _numeric_value(attributes.get("target_temp_low"))
    high = _numeric_value(attributes.get("target_temp_high"))
    if low is None or high is None:
        return {}
    return {
        "low": low,
        "high": high,
        "unit": _temperature_unit(attributes.get("unit_of_measurement")),
    }


def _position_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical percentage position from cover metadata."""
    attributes = snapshot.attributes or {}
    position = _numeric_value(attributes.get("current_position"))
    if position is None:
        position = _numeric_value(attributes.get("position"))
    if position is None:
        return {}
    return {"value": max(0, min(100, position)), "unit": "percent"}


def _tilt_position_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical percentage tilt position from cover metadata."""
    attributes = snapshot.attributes or {}
    position = _numeric_value(attributes.get("current_tilt_position"))
    if position is None:
        position = _numeric_value(attributes.get("tilt_position"))
    if position is None:
        return {}
    return {"value": max(0, min(100, position)), "unit": "percent"}


def _open_close_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical open/close state from cover or contact metadata."""
    if snapshot.state in {"open", "opening", "on"}:
        return {"value": "open"}
    if snapshot.state in {"closed", "closing", "off"}:
        return {"value": "closed"}
    return {}


def _binary_boolean_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical boolean state from Home Assistant binary sensors."""
    if snapshot.state == "on":
        return {"value": True}
    if snapshot.state == "off":
        return {"value": False}
    return {}


def _lock_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical lock state from Home Assistant lock metadata."""
    if snapshot.state in {"locked", "unlocked"}:
        return {"value": snapshot.state}
    return {}


def _mode_select_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical mode state from Home Assistant mode metadata."""
    attributes = snapshot.attributes or {}
    mode = attributes.get("hvac_mode")
    if mode is None:
        mode = snapshot.state
    return {"value": mode} if isinstance(mode, str) else {}


def _preset_mode_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical preset mode state from Home Assistant climate metadata."""
    mode = (snapshot.attributes or {}).get("preset_mode")
    return {"value": mode} if isinstance(mode, str) else {}


def _swing_mode_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical swing mode state from Home Assistant climate metadata."""
    mode = (snapshot.attributes or {}).get("swing_mode")
    return {"value": mode} if isinstance(mode, str) else {}


def _source_ref(snapshot: EntityStateSnapshot, capability: str) -> dict[str, Any]:
    """Return source reference metadata for a capability."""
    return {
        "source": "home_assistant",
        "source_device_id": snapshot.source_device_id,
        "source_entity_id": snapshot.entity_id,
        "domain": snapshot.domain or snapshot.entity_id.split(".", 1)[0],
        "role": _source_entity_role(snapshot, capability),
        "capability_types": [capability],
    }


def _source_entity_role(snapshot: EntityStateSnapshot, capability: str) -> str:
    """Return the source entity role for a capability mapping."""
    if capability in {"battery", "signal_quality"}:
        return "health"
    if capability == "button_event":
        return "event_source"
    if capability in _WRITABLE_CAPABILITIES:
        return "primary_control"
    domain = snapshot.domain or snapshot.entity_id.split(".", 1)[0]
    if domain in {"sensor", "binary_sensor"}:
        return "sensor"
    return "secondary_control"


def _mired_to_kelvin(value: Any) -> int | None:
    """Convert Home Assistant mired color temperature to kelvin."""
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    return round(1_000_000 / value)


def _rgb_color_value(value: Any) -> dict[str, int] | None:
    """Return canonical RGB channel values from Home Assistant RGB data."""
    if not isinstance(value, list | tuple) or len(value) != 3:
        return None
    red, green, blue = value
    if not all(isinstance(channel, (int, float)) for channel in (red, green, blue)):
        return None
    return {"r": int(red), "g": int(green), "b": int(blue)}


def _hs_color_value(value: Any) -> dict[str, int] | None:
    """Return canonical RGB channel values from Home Assistant HS color data."""
    if not isinstance(value, list | tuple) or len(value) != 2:
        return None
    hue, saturation = value
    if not all(isinstance(channel, (int, float)) for channel in (hue, saturation)):
        return None
    hue = hue % 360
    saturation = max(0, min(100, saturation)) / 100
    red, green, blue = colorsys.hsv_to_rgb(hue / 360, saturation, 1)
    return {
        "r": round(red * 255),
        "g": round(green * 255),
        "b": round(blue * 255),
    }


def _xy_color_value(value: Any) -> dict[str, int] | None:
    """Return canonical RGB channel values from Home Assistant XY color data."""
    if not isinstance(value, list | tuple) or len(value) != 2:
        return None
    x_value, y_value = value
    if not all(isinstance(channel, (int, float)) for channel in (x_value, y_value)):
        return None
    if y_value <= 0:
        return None

    y_luminance = 1.0
    x_luminance = (y_luminance / y_value) * x_value
    z_luminance = (y_luminance / y_value) * (1 - x_value - y_value)

    red = (
        x_luminance * 1.656492
        - y_luminance * 0.354851
        - z_luminance * 0.255038
    )
    green = (
        -x_luminance * 0.707196
        + y_luminance * 1.655397
        + z_luminance * 0.036152
    )
    blue = (
        x_luminance * 0.051713
        - y_luminance * 0.121364
        + z_luminance * 1.011530
    )

    red = _gamma_correct(red)
    green = _gamma_correct(green)
    blue = _gamma_correct(blue)

    max_channel = max(red, green, blue)
    if max_channel > 1:
        red /= max_channel
        green /= max_channel
        blue /= max_channel

    return {
        "r": int(max(0, min(1, red)) * 255),
        "g": int(max(0, min(1, green)) * 255),
        "b": int(max(0, min(1, blue)) * 255),
    }


def _gamma_correct(channel: float) -> float:
    """Apply sRGB gamma correction to a normalized channel."""
    if channel <= 0:
        return 0
    if channel <= 0.0031308:
        return 12.92 * channel
    return (1.0 + 0.055) * pow(channel, 1.0 / 2.4) - 0.055


def _commands_for_capability(capability: str) -> list[str]:
    """Return command names supported by canonical capabilities."""
    return {
        "power": ["turn_on", "turn_off", "toggle"],
        "brightness": [
            "set_brightness",
            "increase_brightness",
            "decrease_brightness",
        ],
        "color_temperature": ["set_color_temperature"],
        "rgb_color": ["set_rgb_color"],
        "effect": ["set_effect"],
        "target_temperature": ["set_temperature"],
        "target_temperature_range": ["set_temperature_range"],
        "position": ["set_position", "open", "close", "stop"],
        "tilt_position": ["set_tilt_position"],
        "fan_speed": ["set_fan_speed"],
        "fan_direction": ["set_direction"],
        "fan_oscillation": ["set_oscillation"],
        "mode_select": ["set_mode"],
        "preset_mode": ["set_preset_mode"],
        "swing_mode": ["set_swing_mode"],
        "numeric_setting": ["set_value"],
        "option_setting": ["select_option"],
        "lock": ["lock", "unlock"],
        "run": ["run"],
        "button_press": ["press"],
    }.get(capability, [])


def _constraints_for_capability(
    snapshot: EntityStateSnapshot,
    capability: str,
) -> dict[str, Any]:
    """Return default constraints for canonical capabilities."""
    if capability == "brightness":
        return {"min": 0, "max": 100, "step": 1}
    if capability == "color_temperature":
        return _color_temperature_constraints(snapshot.attributes or {})
    if capability == "effect":
        effects = (snapshot.attributes or {}).get("effect_list")
        if isinstance(effects, list) and all(isinstance(effect, str) for effect in effects):
            return {"values": effects}
    if capability == "target_temperature":
        return _target_temperature_constraints(snapshot.attributes or {})
    if capability == "target_temperature_range":
        return _target_temperature_constraints(snapshot.attributes or {})
    if capability == "fan_speed":
        modes = (snapshot.attributes or {}).get("fan_modes")
        if isinstance(modes, list) and all(isinstance(mode, str) for mode in modes):
            return {"values": modes}
        return {"min": 0, "max": 100, "step": 1}
    if capability == "fan_direction":
        return {"values": ["forward", "reverse"]}
    if capability == "position":
        return {"min": 0, "max": 100, "step": 1}
    if capability == "tilt_position":
        return {"min": 0, "max": 100, "step": 1}
    if capability == "mode_select":
        modes = (snapshot.attributes or {}).get("hvac_modes")
        if isinstance(modes, list) and all(isinstance(mode, str) for mode in modes):
            return {"values": modes}
    if capability == "preset_mode":
        modes = (snapshot.attributes or {}).get("preset_modes")
        if isinstance(modes, list) and all(isinstance(mode, str) for mode in modes):
            return {"values": modes}
    if capability == "swing_mode":
        modes = (snapshot.attributes or {}).get("swing_modes")
        if isinstance(modes, list) and all(isinstance(mode, str) for mode in modes):
            return {"values": modes}
    return {}


def _color_temperature_constraints(attributes: dict[str, Any]) -> dict[str, Any]:
    """Return kelvin constraints from Home Assistant color temperature metadata."""
    min_mired = attributes.get("min_mireds")
    max_mired = attributes.get("max_mireds")
    min_kelvin = _mired_to_kelvin(max_mired)
    max_kelvin = _mired_to_kelvin(min_mired)
    if min_kelvin is None or max_kelvin is None:
        return {}
    return {"min": min_kelvin, "max": max_kelvin, "step": 50}


def _target_temperature_constraints(attributes: dict[str, Any]) -> dict[str, Any]:
    """Return target temperature constraints from Home Assistant climate metadata."""
    constraints: dict[str, Any] = {}
    min_temp = _numeric_value(attributes.get("min_temp"))
    max_temp = _numeric_value(attributes.get("max_temp"))
    step = _numeric_value(attributes.get("target_temp_step"))
    if min_temp is not None:
        constraints["min"] = min_temp
    if max_temp is not None:
        constraints["max"] = max_temp
    if step is not None:
        constraints["step"] = step
    return constraints


def _logical_device_presentation(
    presentation: dict[str, Any],
    capabilities: list[SmartlyCapability],
) -> dict[str, Any]:
    """Translate existing UI metadata into API vNext presentation hints."""
    capability_types = [capability.type for capability in capabilities]
    template_by_source_card = {
        "light_card": "light_control",
        "control_card": "switch_control",
        "metric_card": "sensor_summary",
        "binary_state_card": "sensor_summary",
        "event_card": "button_automation",
        "multi_control_card": "button_automation",
        "unknown_card": "diagnostic_device",
    }
    template = template_by_source_card.get(
        str(presentation.get("card_template", "")),
        "diagnostic_device",
    )
    primary_controls = [
        capability for capability in capability_types if capability in _WRITABLE_CAPABILITIES
    ]
    status_badges = [
        capability for capability in capability_types if capability in {"battery", "signal_quality"}
    ]
    return {
        "template": template,
        "primary_controls": primary_controls,
        "status_badges": status_badges,
    }
