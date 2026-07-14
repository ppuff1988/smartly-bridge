"""Tests for stable setting identity."""

from custom_components.smartly_bridge.domain.setting_keys import setting_key_for_entity


def test_non_setting_domain_has_no_setting_key() -> None:
    """Non-setting entities cannot be routed as writable settings."""
    assert setting_key_for_entity("sensor.hall_temperature", "Hall temperature", "sensor") is None
