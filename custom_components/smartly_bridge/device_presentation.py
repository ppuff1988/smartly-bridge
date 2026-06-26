"""Capability-driven device card metadata for Smartly Platform."""

from __future__ import annotations

from typing import Any, Iterable

from .acl import get_entity_domain

HIGH_RISK_DOMAINS = {"alarm_control_panel", "camera", "lock"}

SMARTLY_DEVICE_CLASSES = {
    "smart_light",
    "simple_light_switch",
    "simple_switch",
    "fan_control",
    "environment_sensor",
    "presence_sensor",
    "contact_sensor",
    "button_device",
    "multi_button_device",
    "cover_control",
    "climate_control",
    "scene_trigger",
    "unknown_device",
}

CARD_TEMPLATE_BY_CLASS = {
    "smart_light": "light_card",
    "simple_light_switch": "control_card",
    "simple_switch": "control_card",
    "fan_control": "control_card",
    "environment_sensor": "metric_card",
    "presence_sensor": "binary_state_card",
    "contact_sensor": "binary_state_card",
    "button_device": "event_card",
    "multi_button_device": "multi_control_card",
    "cover_control": "cover_card",
    "climate_control": "climate_card",
    "scene_trigger": "scene_card",
    "unknown_device": "unknown_card",
}

ENVIRONMENT_CAPABILITIES = (
    "temperature",
    "humidity",
    "air_quality",
    "co2",
    "pm25",
    "illuminance",
)
HEALTH_CAPABILITIES = ("battery", "signal_strength")
PRESENCE_CAPABILITIES = ("occupancy", "motion", "presence")
CONTACT_CAPABILITIES = ("contact", "opening", "door", "window")
RGB_COLOR_MODES = {"hs", "rgb", "rgbw", "rgbww", "xy"}


def build_device_card_metadata(
    entity_id: str,
    state: str | None,
    attributes: dict[str, Any] | None,
    labels: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build normalized metadata used by Smartly device cards."""
    attributes = attributes or {}
    labels = labels or ()
    domain = get_entity_domain(entity_id)

    capabilities = _infer_capabilities(domain, attributes)
    device_class = _classify_device(domain, capabilities, attributes, labels)
    presentation = _build_presentation(device_class, capabilities)

    return {
        "name": attributes.get("friendly_name", entity_id),
        "domain": domain,
        "device_class": device_class,
        "capabilities": capabilities,
        "status": _status_from_state(state),
        "presentation": presentation,
    }


def _infer_capabilities(domain: str, attributes: dict[str, Any]) -> list[str]:
    """Infer stable UI capabilities from Home Assistant domain and attributes."""
    capabilities: list[str] = []

    def add(capability: str) -> None:
        if capability not in capabilities:
            capabilities.append(capability)

    if domain in {"light", "switch", "fan"}:
        add("on_off")

    if domain == "light":
        color_modes = _normalized_values(attributes.get("supported_color_modes"))
        if "brightness" in attributes or "brightness" in color_modes:
            add("brightness")
        if (
            "color_temp" in attributes
            or "color_temp" in color_modes
            or "min_mireds" in attributes
            or "max_mireds" in attributes
        ):
            add("color_temp")
        if RGB_COLOR_MODES.intersection(color_modes) or any(
            key in attributes for key in ("rgb_color", "hs_color", "xy_color")
        ):
            add("rgb_color")

    elif domain == "sensor":
        device_class = str(attributes.get("device_class", "")).lower()
        if device_class in ENVIRONMENT_CAPABILITIES:
            add(device_class)
        for capability in ENVIRONMENT_CAPABILITIES:
            if capability in attributes:
                add(capability)

    elif domain == "binary_sensor":
        device_class = str(attributes.get("device_class", "")).lower()
        for capability in (*PRESENCE_CAPABILITIES, *CONTACT_CAPABILITIES):
            if device_class == capability or capability in attributes:
                add(capability)

    elif domain == "cover":
        add("open_close")
        if "current_position" in attributes or "position" in attributes:
            add("position")
        add("stop")

    elif domain == "climate":
        if any(key in attributes for key in ("temperature", "target_temp", "target_temperature")):
            add("target_temperature")
        if "hvac_modes" in attributes or "hvac_mode" in attributes:
            add("hvac_mode")
        if "fan_modes" in attributes or "fan_mode" in attributes:
            add("fan_speed")

    elif domain == "fan":
        if (
            "percentage" in attributes
            or "preset_mode" in attributes
            or "preset_modes" in attributes
        ):
            add("fan_speed")

    elif domain in {"scene", "script"}:
        add("run")

    elif domain == "button":
        add("event")

    for capability in HEALTH_CAPABILITIES:
        if capability in attributes:
            add(capability)

    return capabilities


def _classify_device(
    domain: str,
    capabilities: list[str],
    attributes: dict[str, Any],
    labels: Iterable[str],
) -> str:
    """Classify an entity into Smartly's user-facing device class."""
    if domain in HIGH_RISK_DOMAINS:
        return "unknown_device"

    override = _device_class_override(labels)
    if override and _override_allowed(override, domain, capabilities):
        return override

    capability_set = set(capabilities)
    if domain == "light":
        if capability_set.intersection({"brightness", "color_temp", "rgb_color"}):
            return "smart_light"
        return "simple_light_switch"

    if domain == "switch":
        return "simple_switch" if "on_off" in capability_set else "unknown_device"

    if domain == "fan":
        return "fan_control"

    if domain == "sensor":
        if capability_set.intersection(ENVIRONMENT_CAPABILITIES):
            return "environment_sensor"
        if "event" in capability_set:
            return "button_device"
        return "unknown_device"

    if domain == "binary_sensor":
        if capability_set.intersection(PRESENCE_CAPABILITIES):
            return "presence_sensor"
        if capability_set.intersection(CONTACT_CAPABILITIES):
            return "contact_sensor"
        return "unknown_device"

    if domain == "button":
        return "button_device"

    if domain == "cover" and capability_set.intersection({"open_close", "position", "stop"}):
        return "cover_control"

    if domain == "climate" and capability_set.intersection(
        {"target_temperature", "hvac_mode", "fan_speed"}
    ):
        return "climate_control"

    if domain in {"scene", "script"} and "run" in capability_set:
        return "scene_trigger"

    return str(attributes.get("smartly_device_class") or "unknown_device")


def _build_presentation(device_class: str, capabilities: list[str]) -> dict[str, Any]:
    """Build card presentation hints from the normalized device class."""
    card_template = CARD_TEMPLATE_BY_CLASS.get(device_class, "unknown_card")
    presentation: dict[str, Any] = {
        "card_template": card_template,
        "dashboard_priority": 50,
        "favorite": False,
    }

    if device_class == "environment_sensor":
        primary_metric = _first_present(capabilities, ENVIRONMENT_CAPABILITIES)
        presentation["primary_metric"] = primary_metric
        presentation["secondary_metrics"] = _secondary_metrics(
            capabilities,
            primary_metric,
            ("humidity", "battery", "signal_strength", "co2", "pm25", "illuminance"),
        )
        presentation["dashboard_priority"] = 40
    elif device_class == "smart_light":
        if "brightness" in capabilities:
            presentation["primary_metric"] = "brightness"
        presentation["secondary_metrics"] = _secondary_metrics(
            capabilities,
            presentation.get("primary_metric"),
            HEALTH_CAPABILITIES,
        )
    else:
        presentation["secondary_metrics"] = _secondary_metrics(
            capabilities,
            None,
            HEALTH_CAPABILITIES,
        )

    return presentation


def _status_from_state(state: str | None) -> str:
    """Map raw state to a simple availability status."""
    if state in {None, "unavailable", "unknown"}:
        return "offline"
    return "online"


def _device_class_override(labels: Iterable[str]) -> str | None:
    """Extract the first supported smartly.class label."""
    for label in labels:
        if not isinstance(label, str) or not label.startswith("smartly.class."):
            continue
        device_class = label.removeprefix("smartly.class.")
        if device_class in SMARTLY_DEVICE_CLASSES:
            return device_class
    return None


def _override_allowed(device_class: str, domain: str, capabilities: list[str]) -> bool:
    """Allow class overrides only when the domain/capability shape is compatible."""
    capability_set = set(capabilities)
    if device_class == "unknown_device":
        return True
    if device_class == "fan_control":
        return domain in {"fan", "switch"} and "on_off" in capability_set
    if device_class in {"simple_light_switch", "simple_switch"}:
        return domain == "switch" and "on_off" in capability_set
    if device_class == "smart_light":
        return domain == "light" and bool(
            capability_set.intersection({"brightness", "color_temp", "rgb_color"})
        )
    if device_class == "environment_sensor":
        return domain == "sensor" and bool(capability_set.intersection(ENVIRONMENT_CAPABILITIES))
    if device_class == "presence_sensor":
        return domain == "binary_sensor" and bool(
            capability_set.intersection(PRESENCE_CAPABILITIES)
        )
    if device_class == "contact_sensor":
        return domain == "binary_sensor" and bool(capability_set.intersection(CONTACT_CAPABILITIES))
    if device_class == "cover_control":
        return domain == "cover" and bool(capability_set)
    if device_class == "climate_control":
        return domain == "climate" and bool(capability_set)
    if device_class == "scene_trigger":
        return domain in {"scene", "script"} and "run" in capability_set
    return False


def _normalized_values(value: Any) -> set[str]:
    """Return lowercase strings from scalar or iterable values."""
    if value is None:
        return set()
    if isinstance(value, str):
        return {value.lower()}
    try:
        return {str(item).lower() for item in value}
    except TypeError:
        return {str(value).lower()}


def _first_present(values: list[str], priority: tuple[str, ...]) -> str | None:
    """Return the first value present according to priority order."""
    value_set = set(values)
    for value in priority:
        if value in value_set:
            return value
    return None


def _secondary_metrics(
    capabilities: list[str],
    primary_metric: str | None,
    priority: tuple[str, ...],
) -> list[str]:
    """Return at most two dashboard secondary metrics."""
    capability_set = set(capabilities)
    return [
        capability
        for capability in priority
        if capability in capability_set and capability != primary_metric
    ][:2]
