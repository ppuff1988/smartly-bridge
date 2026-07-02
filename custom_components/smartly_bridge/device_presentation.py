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
    "aqi",
    "co2",
    "carbon_dioxide",
    "carbon_monoxide",
    "pm25",
    "pm10",
    "illuminance",
    "pressure",
    "atmospheric_pressure",
)
ELECTRICAL_CAPABILITY_BY_DEVICE_CLASS = {
    "current": "current",
    "energy": "energy_meter",
    "power": "power_meter",
    "voltage": "voltage",
}
ELECTRICAL_CAPABILITIES = tuple(ELECTRICAL_CAPABILITY_BY_DEVICE_CLASS.values())
SENSOR_MEASUREMENT_CAPABILITIES = (*ENVIRONMENT_CAPABILITIES, *ELECTRICAL_CAPABILITIES)
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
    by_domain = {
        "light": _light_capabilities,
        "switch": _switch_capabilities,
        "sensor": _sensor_capabilities,
        "binary_sensor": _binary_sensor_capabilities,
        "cover": _cover_capabilities,
        "climate": _climate_capabilities,
        "fan": _fan_capabilities,
        "scene": _scene_or_script_capabilities,
        "script": _scene_or_script_capabilities,
        "button": _button_capabilities,
    }
    capabilities = by_domain.get(domain, _no_capabilities)(attributes)
    return _with_health_capabilities(capabilities, attributes)


def _light_capabilities(attributes: dict[str, Any]) -> list[str]:
    """Infer light capabilities."""
    capabilities = ["on_off"]
    color_modes = _normalized_values(attributes.get("supported_color_modes"))

    if "brightness" in attributes or "brightness" in color_modes:
        capabilities.append("brightness")
    if _supports_color_temperature(attributes, color_modes):
        capabilities.append("color_temperature")
    if _supports_rgb_color(attributes, color_modes):
        capabilities.append("rgb_color")
    if "effect" in attributes or "effect_list" in attributes:
        capabilities.append("effect")

    return capabilities


def _switch_capabilities(attributes: dict[str, Any]) -> list[str]:
    """Infer switch capabilities."""
    return ["on_off"]


def _sensor_capabilities(attributes: dict[str, Any]) -> list[str]:
    """Infer numeric or text sensor capabilities."""
    capabilities: list[str] = []
    device_class = str(attributes.get("device_class", "")).lower()
    if device_class in ENVIRONMENT_CAPABILITIES:
        capabilities.append(device_class)
    if device_class in ELECTRICAL_CAPABILITY_BY_DEVICE_CLASS:
        capabilities.append(ELECTRICAL_CAPABILITY_BY_DEVICE_CLASS[device_class])
    for capability in ENVIRONMENT_CAPABILITIES:
        if capability in attributes:
            _append_unique(capabilities, capability)
    for source, canonical in ELECTRICAL_CAPABILITY_BY_DEVICE_CLASS.items():
        if source in attributes:
            _append_unique(capabilities, canonical)
    return capabilities


def _binary_sensor_capabilities(attributes: dict[str, Any]) -> list[str]:
    """Infer binary sensor capabilities."""
    capabilities: list[str] = []
    device_class = str(attributes.get("device_class", "")).lower()
    for capability in (*PRESENCE_CAPABILITIES, *CONTACT_CAPABILITIES):
        if device_class == capability or capability in attributes:
            capabilities.append(capability)
    return capabilities


def _cover_capabilities(attributes: dict[str, Any]) -> list[str]:
    """Infer cover capabilities."""
    capabilities = ["open_close"]
    if "current_position" in attributes or "position" in attributes:
        capabilities.append("position")
    if "current_tilt_position" in attributes or "tilt_position" in attributes:
        capabilities.append("tilt_position")
    capabilities.append("stop")
    return capabilities


def _climate_capabilities(attributes: dict[str, Any]) -> list[str]:
    """Infer climate capabilities."""
    capabilities: list[str] = []
    if all(key in attributes for key in ("target_temp_low", "target_temp_high")):
        capabilities.append("target_temperature_range")
    if any(key in attributes for key in ("temperature", "target_temp", "target_temperature")):
        capabilities.append("target_temperature")
    if "hvac_modes" in attributes or "hvac_mode" in attributes:
        capabilities.append("hvac_mode")
    if "fan_modes" in attributes or "fan_mode" in attributes:
        capabilities.append("fan_speed")
    if "preset_modes" in attributes or "preset_mode" in attributes:
        capabilities.append("preset_mode")
    if "swing_modes" in attributes or "swing_mode" in attributes:
        capabilities.append("swing_mode")
    return capabilities


def _fan_capabilities(attributes: dict[str, Any]) -> list[str]:
    """Infer fan capabilities."""
    capabilities = ["on_off"]
    if "percentage" in attributes or "preset_mode" in attributes or "preset_modes" in attributes:
        capabilities.append("fan_speed")
    if "direction" in attributes:
        capabilities.append("fan_direction")
    if "oscillating" in attributes:
        capabilities.append("fan_oscillation")
    return capabilities


def _scene_or_script_capabilities(attributes: dict[str, Any]) -> list[str]:
    """Infer scene and script capabilities."""
    return ["run"]


def _button_capabilities(attributes: dict[str, Any]) -> list[str]:
    """Infer button capabilities."""
    return ["event", "button_press"]


def _no_capabilities(attributes: dict[str, Any]) -> list[str]:
    """Return no capabilities for unsupported domains."""
    return []


def _with_health_capabilities(
    capabilities: list[str],
    attributes: dict[str, Any],
) -> list[str]:
    """Append common health capabilities."""
    for capability in HEALTH_CAPABILITIES:
        if capability in attributes:
            _append_unique(capabilities, capability)
    return capabilities


def _supports_color_temperature(
    attributes: dict[str, Any],
    color_modes: set[str],
) -> bool:
    """Return whether light attributes indicate color-temperature support."""
    return (
        "color_temp" in attributes
        or "color_temp" in color_modes
        or "min_mireds" in attributes
        or "max_mireds" in attributes
    )


def _supports_rgb_color(attributes: dict[str, Any], color_modes: set[str]) -> bool:
    """Return whether light attributes indicate RGB color support."""
    return bool(
        RGB_COLOR_MODES.intersection(color_modes)
        or any(key in attributes for key in ("rgb_color", "hs_color", "xy_color"))
    )


def _append_unique(values: list[str], value: str) -> None:
    """Append a value if it is not already present."""
    if value not in values:
        values.append(value)


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
        if capability_set.intersection({"brightness", "color_temperature", "rgb_color"}):
            return "smart_light"
        return "simple_light_switch"

    if domain == "switch":
        return "simple_switch" if "on_off" in capability_set else "unknown_device"

    if domain == "fan":
        return "fan_control"

    if domain == "sensor":
        if capability_set.intersection(SENSOR_MEASUREMENT_CAPABILITIES):
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

    if domain == "cover" and capability_set.intersection(
        {"open_close", "position", "tilt_position", "stop"}
    ):
        return "cover_control"

    if domain == "climate" and capability_set.intersection(
        {
            "target_temperature",
            "target_temperature_range",
            "hvac_mode",
            "fan_speed",
            "preset_mode",
            "swing_mode",
        }
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
        primary_metric = _first_present(
            capabilities,
            SENSOR_MEASUREMENT_CAPABILITIES,
        )
        presentation["primary_metric"] = primary_metric
        presentation["secondary_metrics"] = _secondary_metrics(
            capabilities,
            primary_metric,
            (
                "humidity",
                "battery",
                "signal_strength",
                "co2",
                "pm25",
                "illuminance",
                "power_meter",
                "energy_meter",
                "voltage",
                "current",
            ),
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
            capability_set.intersection({"brightness", "color_temperature", "rgb_color"})
        )
    if device_class == "environment_sensor":
        return domain == "sensor" and bool(
            capability_set.intersection(SENSOR_MEASUREMENT_CAPABILITIES)
        )
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
    *,
    limit: int = 2,
) -> list[str]:
    """Return dashboard secondary metrics."""
    capability_set = set(capabilities)
    return [
        capability
        for capability in priority
        if capability in capability_set and capability != primary_metric
    ][:limit]
