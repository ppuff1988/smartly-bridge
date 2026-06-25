"""Utility functions for Smartly Bridge integration."""

from __future__ import annotations

import ipaddress
from datetime import date, datetime
from typing import Any

from .const import NUMERIC_PRECISION_CONFIG, UNIT_SPECIFIC_PRECISION_CONFIG


def parse_allowed_networks(
    allowed_cidrs: str,
) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Parse comma-separated CIDR ranges, including simple octet wildcards."""
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []

    for raw_range in allowed_cidrs.split(","):
        ip_range = raw_range.strip().replace("＊", "*")
        if not ip_range:
            continue

        if "*" in ip_range:
            ip_range = _wildcard_to_cidr(ip_range)

        networks.append(ipaddress.ip_network(ip_range, strict=False))

    return networks


def _wildcard_to_cidr(ip_range: str) -> str:
    """Convert ranges like 10.* or 192.168.* to IPv4 CIDR notation."""
    parts = ip_range.split(".")
    if not 1 < len(parts) <= 4:
        raise ValueError(f"Invalid wildcard range: {ip_range}")

    wildcard_index = None
    for index, part in enumerate(parts):
        if part == "*":
            wildcard_index = index
            break
        if not part.isdigit() or not 0 <= int(part) <= 255:
            raise ValueError(f"Invalid wildcard range: {ip_range}")

    if wildcard_index is None or any(part != "*" for part in parts[wildcard_index:]):
        raise ValueError(f"Invalid wildcard range: {ip_range}")

    prefix = wildcard_index * 8
    network_parts = parts[:wildcard_index] + ["0"] * (4 - wildcard_index)
    return f"{'.'.join(network_parts)}/{prefix}"


def get_decimal_places(key: str, unit: str = "") -> int | None:
    """Get decimal places for formatting based on attribute/device_class and unit.

    Args:
        key: Attribute name or device_class (e.g., 'voltage', 'current', 'power')
        unit: Unit of measurement (e.g., 'V', 'mA', 'W', 'kW')

    Returns:
        Number of decimal places, or None if no configuration found
    """
    # Check unit-specific config first
    if key and unit:
        if (key, unit) in UNIT_SPECIFIC_PRECISION_CONFIG:
            return UNIT_SPECIFIC_PRECISION_CONFIG[(key, unit)]

    # Fall back to base config
    if key in NUMERIC_PRECISION_CONFIG:
        return NUMERIC_PRECISION_CONFIG[key]

    return None


def format_numeric_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """Format numeric attributes with configurable decimal places.

    Formats common electrical measurements (voltage, current, power, etc.)
    with appropriate decimal places based on units for cleaner API responses.
    """
    unit = attributes.get("unit_of_measurement", "")

    formatted = attributes.copy()

    for attr in NUMERIC_PRECISION_CONFIG:
        if attr in formatted and isinstance(formatted[attr], (int, float)):
            try:
                decimal_places = get_decimal_places(attr, unit)
                if decimal_places is not None:
                    formatted[attr] = round(float(formatted[attr]), decimal_places)
            except (ValueError, TypeError):
                pass  # Keep original value if conversion fails

    return {key: _json_safe_attribute_value(value) for key, value in formatted.items()}


def _json_safe_attribute_value(value: Any) -> Any:
    """Convert common Home Assistant attribute values to JSON-safe values."""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe_attribute_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe_attribute_value(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe_attribute_value(item) for item in value]
    return value


def format_sensor_state(state_value: str, attributes: dict[str, Any]) -> str:
    """Format sensor state value with configurable decimal places.

    Args:
        state_value: The state value as string
        attributes: Entity attributes containing device_class and unit_of_measurement

    Returns:
        Formatted state value as string
    """
    # 只處理數值型態的 sensor
    try:
        numeric_value = float(state_value)
    except (ValueError, TypeError):
        return state_value

    # 取得 device_class 和 unit
    device_class = attributes.get("device_class", "")
    unit = attributes.get("unit_of_measurement", "")

    # 取得對應的小數位數配置
    decimal_places = get_decimal_places(device_class, unit)

    if decimal_places is not None:
        return str(round(numeric_value, decimal_places))

    return state_value
