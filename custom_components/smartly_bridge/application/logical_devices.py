"""Logical device normalization for migration toward capability contracts."""

from __future__ import annotations

import re
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
    canonical_capabilities = [
        _capability_from_snapshot(snapshot, capability) for capability in snapshot.capabilities
    ]
    return SmartlyLogicalDevice(
        id=_logical_device_id(snapshot.entity_id),
        name=snapshot.name or snapshot.entity_id,
        primary_type=_primary_type_for_snapshot(snapshot),
        device_class=_logical_device_class(snapshot),
        status=snapshot.status,
        source_entities=[snapshot.entity_id],
        capabilities=canonical_capabilities,
        presentation=_logical_device_presentation(
            snapshot.presentation,
            canonical_capabilities,
        ),
    )


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
    canonical = {
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
    state = _capability_state(snapshot, canonical)
    return SmartlyCapability(
        type=canonical,
        role=_capability_role(canonical),
        readable=canonical != "button_event",
        writable=canonical in _WRITABLE_CAPABILITIES,
        event_only=canonical == "button_event",
        state=state,
        commands=_commands_for_capability(canonical),
        constraints=_constraints_for_capability(canonical),
    )


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
        return {"value": attributes["rgb_color"]}
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


def _mired_to_kelvin(value: Any) -> int | None:
    """Convert Home Assistant mired color temperature to kelvin."""
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    return round(1_000_000 / value)


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


def _constraints_for_capability(capability: str) -> dict[str, Any]:
    """Return default constraints for canonical capabilities."""
    if capability == "brightness":
        return {"min": 0, "max": 100, "step": 1}
    return {}


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
