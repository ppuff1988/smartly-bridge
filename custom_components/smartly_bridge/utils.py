"""Utility functions for Smartly Bridge integration."""

from __future__ import annotations

from typing import Any

from .const import NUMERIC_PRECISION_CONFIG, UNIT_SPECIFIC_PRECISION_CONFIG


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

    return formatted
