"""Logical device normalization for migration toward capability contracts."""

from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any

from ..domain.models import EntityStateSnapshot, SmartlyCapability, SmartlyLogicalDevice

_WRITABLE_CAPABILITIES = {
    "power",
    "brightness",
    "color_temperature",
    "rgb_color",
    "position",
    "fan_speed",
    "mode_select",
    "lock",
}


def logical_device_from_state(snapshot: EntityStateSnapshot) -> SmartlyLogicalDevice:
    """Build a shadow logical device from normalized entity metadata."""
    return _logical_device_from_group([snapshot])


def logical_devices_from_states(
    snapshots: list[EntityStateSnapshot],
) -> list[SmartlyLogicalDevice]:
    """Build grouped logical devices from normalized entity state snapshots."""
    grouped: OrderedDict[str, list[EntityStateSnapshot]] = OrderedDict()
    for snapshot in snapshots:
        grouped.setdefault(_group_key(snapshot), []).append(snapshot)

    return [_logical_device_from_group(group) for group in grouped.values()]


def logical_device_id_for_source_id(source_id: str) -> str:
    """Return the deterministic logical device ID for a source identifier."""
    return _logical_device_id(source_id)


def canonical_capability_name(capability: str) -> str:
    """Return the canonical capability name for a legacy capability."""
    return _canonical_capability(capability)


def _logical_device_from_group(snapshots: list[EntityStateSnapshot]) -> SmartlyLogicalDevice:
    """Build a logical device from one source-device group."""
    primary = _primary_snapshot(snapshots)
    canonical_capabilities = _capabilities_from_group(snapshots)
    return SmartlyLogicalDevice(
        id=_logical_device_id(primary.source_device_id or primary.entity_id),
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
    )


def _group_key(snapshot: EntityStateSnapshot) -> str:
    """Return the logical-device grouping key for a snapshot."""
    return snapshot.source_device_id or snapshot.entity_id


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
        for legacy_capability in snapshot.capabilities:
            capability = _capability_from_snapshot(snapshot, legacy_capability)
            existing = capabilities.get(capability.type)
            if existing is None:
                capabilities[capability.type] = capability
                continue
            capabilities[capability.type] = SmartlyCapability(
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
                source_refs=[*existing.source_refs, *capability.source_refs],
            )
    return list(capabilities.values())


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
    """Map legacy presentation capabilities to canonical capability contracts."""
    canonical = _canonical_capability(capability)
    state = _capability_state(snapshot, canonical)
    return SmartlyCapability(
        type=canonical,
        role=_capability_role(canonical),
        readable=canonical != "button_event",
        writable=canonical in _WRITABLE_CAPABILITIES,
        event_only=canonical == "button_event",
        state=state,
        commands=_commands_for_capability(canonical),
        constraints=_constraints_for_capability(snapshot, canonical),
        source_refs=[_source_ref(snapshot, canonical)],
    )


def _canonical_capability(capability: str) -> str:
    """Return the canonical capability name for a legacy capability."""
    return {
        "on_off": "power",
        "color_temp": "color_temperature",
        "signal_strength": "signal_quality",
        "event": "button_event",
        "occupancy": "presence",
        "contact": "open_close",
        "opening": "open_close",
        "door": "open_close",
        "window": "open_close",
    }.get(capability, capability)


def _capability_role(capability: str) -> str:
    """Return the canonical role for a capability."""
    if capability in {"battery", "signal_quality"}:
        return "health"
    if capability == "button_event":
        return "event_source"
    if capability in {
        "temperature",
        "humidity",
        "pressure",
        "illuminance",
        "presence",
        "open_close",
    }:
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
    if capability == "battery":
        return _numeric_state(snapshot, default_unit="percent")
    if capability == "signal_quality":
        return _signal_quality_state(snapshot)
    if capability == "fan_speed":
        return _fan_speed_state(snapshot)
    if capability == "position":
        return _position_state(snapshot)
    if capability == "open_close":
        return _open_close_state(snapshot)
    if capability == "lock":
        return _lock_state(snapshot)
    if capability in attributes:
        state: dict[str, Any] = {"value": attributes[capability]}
        unit = attributes.get("unit_of_measurement")
        if unit:
            state["unit"] = unit
        return state
    if capability in {"temperature", "humidity", "pressure", "illuminance"}:
        state = {"value": snapshot.state}
        unit = attributes.get("unit_of_measurement")
        if unit:
            state["unit"] = unit
        return state
    return {}


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


def _signal_quality_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical signal quality state from legacy signal metadata."""
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
    """Return the raw signal metric kind from legacy signal metadata."""
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
        preset_mode = attributes.get("preset_mode")
        return {"speed": preset_mode} if isinstance(preset_mode, str) else {}
    return {"percentage": max(0, min(100, percentage)), "unit": "percent"}


def _position_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical percentage position from cover metadata."""
    attributes = snapshot.attributes or {}
    position = _numeric_value(attributes.get("current_position"))
    if position is None:
        position = _numeric_value(attributes.get("position"))
    if position is None:
        return {}
    return {"value": max(0, min(100, position)), "unit": "percent"}


def _open_close_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical open/close state from cover or contact metadata."""
    if snapshot.state in {"open", "opening"}:
        return {"value": "open"}
    if snapshot.state in {"closed", "closing"}:
        return {"value": "closed"}
    return {}


def _lock_state(snapshot: EntityStateSnapshot) -> dict[str, Any]:
    """Return canonical lock state from Home Assistant lock metadata."""
    if snapshot.state in {"locked", "unlocked"}:
        return {"value": snapshot.state}
    return {}


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


def _commands_for_capability(capability: str) -> list[str]:
    """Return command names supported by canonical capabilities."""
    return {
        "power": ["turn_on", "turn_off", "toggle"],
        "brightness": ["set_brightness"],
        "color_temperature": ["set_color_temperature"],
        "rgb_color": ["set_rgb_color"],
        "position": ["set_position", "open", "close", "stop"],
        "fan_speed": ["set_fan_speed"],
        "mode_select": ["set_mode"],
        "lock": ["lock", "unlock"],
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
    if capability == "fan_speed":
        return {"min": 0, "max": 100, "step": 1}
    if capability == "position":
        return {"min": 0, "max": 100, "step": 1}
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


def _logical_device_presentation(
    presentation: dict[str, Any],
    capabilities: list[SmartlyCapability],
) -> dict[str, Any]:
    """Translate existing UI metadata into API vNext presentation hints."""
    capability_types = [capability.type for capability in capabilities]
    template_by_legacy = {
        "light_card": "light_control",
        "control_card": "switch_control",
        "metric_card": "sensor_summary",
        "binary_state_card": "sensor_summary",
        "event_card": "button_automation",
        "multi_control_card": "button_automation",
        "unknown_card": "diagnostic_device",
    }
    template = template_by_legacy.get(
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
