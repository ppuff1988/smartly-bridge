"""Tests for metadata device_class extraction from history."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.smartly_bridge.views.history import _get_entity_metadata


class TestMetadataDeviceClass:
    """Test device_class extraction from states."""

    def test_device_class_from_first_state(self):
        """Test extracting device_class from first state."""
        first_state = {
            "state": "23.5",
            "attributes": {
                "device_class": "temperature",
                "unit_of_measurement": "°C",
                "friendly_name": "Temperature Sensor",
            },
        }

        metadata = _get_entity_metadata("sensor.temperature", first_state)

        assert metadata["device_class"] == "temperature"
        assert metadata["unit_of_measurement"] == "°C"
        assert metadata["domain"] == "sensor"

    def test_device_class_from_later_state_when_first_empty(self):
        """Test extracting device_class from later state when first has empty attributes."""
        first_state = {
            "state": "0.0",
            "attributes": {},  # Empty attributes like in the user's issue
        }

        all_states = [
            {"state": "0.0", "attributes": {}},
            {"state": "34.0", "attributes": {}},
            {"state": "0.0", "attributes": {}},
            {
                "state": "35.0",
                "attributes": {
                    "device_class": "current",
                    "unit_of_measurement": "A",
                    "friendly_name": "PZEM-004T Current",
                },
            },
        ]

        metadata = _get_entity_metadata("sensor.pzem_004t_current", first_state, all_states)

        # Should find device_class from the 4th state
        assert metadata["device_class"] == "current"
        assert metadata["unit_of_measurement"] == "A"
        assert metadata["domain"] == "sensor"

    def test_device_class_none_when_not_found(self):
        """Test device_class is None when not found in any state."""
        first_state = {
            "state": "0.0",
            "attributes": {},
        }

        all_states = [
            {"state": "0.0", "attributes": {}},
            {"state": "34.0", "attributes": {}},
            {"state": "35.0", "attributes": {"friendly_name": "Sensor"}},
        ]

        metadata = _get_entity_metadata("sensor.unknown", first_state, all_states)

        assert metadata["device_class"] is None
        assert metadata["domain"] == "sensor"

    def test_unit_fallback_from_later_state(self):
        """Test unit_of_measurement fallback from later state."""
        first_state = {
            "state": "0.0",
            "attributes": {},
        }

        all_states = [
            {"state": "0.0", "attributes": {}},
            {
                "state": "220.5",
                "attributes": {
                    "device_class": "voltage",
                    "unit_of_measurement": "V",
                },
            },
        ]

        metadata = _get_entity_metadata("sensor.voltage", first_state, all_states)

        assert metadata["device_class"] == "voltage"
        assert metadata["unit_of_measurement"] == "V"

    def test_no_all_states_provided(self):
        """Test behavior when all_states is not provided."""
        first_state = {
            "state": "0.0",
            "attributes": {},
        }

        metadata = _get_entity_metadata("sensor.test", first_state)

        # Should work without error, device_class will be None
        assert metadata["device_class"] is None
        assert metadata["domain"] == "sensor"

    def test_numeric_sensor_with_device_class(self):
        """Test numeric sensor with device_class gets proper visualization."""
        first_state = {
            "state": "0.0",
            "attributes": {},
        }

        all_states = [
            {"state": "0.0", "attributes": {}},
            {
                "state": "35.0",
                "attributes": {
                    "device_class": "current",
                    "unit_of_measurement": "A",
                },
            },
        ]

        metadata = _get_entity_metadata("sensor.current", first_state, all_states)

        assert metadata["is_numeric"] is True
        assert metadata["device_class"] == "current"
        assert metadata["visualization"]["type"] == "chart"
        assert "decimal_places" in metadata

    def test_fallback_to_current_state(self):
        """Test fallback to current state when history has no device_class."""
        first_state = {
            "state": "113.9",
            "attributes": {},
        }

        all_states = [
            {"state": "113.9", "attributes": {}},
            {"state": "114.0", "attributes": {}},
        ]

        # Mock hass with current state
        mock_hass = MagicMock()
        mock_current_state = MagicMock()
        mock_current_state.attributes = {
            "device_class": "voltage",
            "unit_of_measurement": "V",
            "friendly_name": "Voltage Sensor",
        }
        mock_hass.states.get.return_value = mock_current_state

        metadata = _get_entity_metadata("sensor.voltage", first_state, all_states, hass=mock_hass)

        assert metadata["device_class"] == "voltage"
        assert metadata["unit_of_measurement"] == "V"
        assert metadata["friendly_name"] == "Voltage Sensor"

    def test_no_current_state_available(self):
        """Test when entity no longer exists in hass."""
        first_state = {
            "state": "0.0",
            "attributes": {},
        }

        all_states = [{"state": "0.0", "attributes": {}}]

        # Mock hass with no current state
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        metadata = _get_entity_metadata("sensor.deleted", first_state, all_states, hass=mock_hass)

        # Should still work, device_class will be None
        assert metadata["device_class"] is None
        assert metadata["domain"] == "sensor"
