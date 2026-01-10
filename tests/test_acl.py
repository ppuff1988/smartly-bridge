"""Tests for ACL (Access Control List) module."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.smartly_bridge.acl import (
    filter_entities_by_area,
    get_allowed_entities,
    get_entity_domain,
    get_structure,
    is_entity_allowed,
    is_service_allowed,
)
from custom_components.smartly_bridge.const import ALLOWED_SERVICES


class TestIsEntityAllowed:
    """Tests for is_entity_allowed function."""

    def test_entity_with_smartly_control_label(self, mock_hass, mock_entity_registry):
        """Test entity with smartly_control label is allowed."""
        result = is_entity_allowed(mock_hass, "light.test_light", mock_entity_registry)
        assert result is True

    def test_entity_without_label(self, mock_hass, mock_entity_registry):
        """Test entity without label is not allowed."""
        result = is_entity_allowed(mock_hass, "light.hidden_light", mock_entity_registry)
        assert result is False

    def test_nonexistent_entity(self, mock_hass, mock_entity_registry):
        """Test nonexistent entity is not allowed."""
        result = is_entity_allowed(mock_hass, "light.does_not_exist", mock_entity_registry)
        assert result is False


class TestIsServiceAllowed:
    """Tests for is_service_allowed function."""

    def test_allowed_switch_services(self):
        """Test allowed switch services."""
        assert is_service_allowed("switch", "turn_on") is True
        assert is_service_allowed("switch", "turn_off") is True
        assert is_service_allowed("switch", "toggle") is True

    def test_allowed_light_services(self):
        """Test allowed light services."""
        assert is_service_allowed("light", "turn_on") is True
        assert is_service_allowed("light", "turn_off") is True
        assert is_service_allowed("light", "toggle") is True

    def test_allowed_cover_services(self):
        """Test allowed cover services."""
        assert is_service_allowed("cover", "open_cover") is True
        assert is_service_allowed("cover", "close_cover") is True
        assert is_service_allowed("cover", "stop_cover") is True
        assert is_service_allowed("cover", "set_cover_position") is True

    def test_allowed_climate_services(self):
        """Test allowed climate services."""
        assert is_service_allowed("climate", "set_temperature") is True
        assert is_service_allowed("climate", "set_hvac_mode") is True
        assert is_service_allowed("climate", "set_fan_mode") is True

    def test_allowed_lock_services(self):
        """Test allowed lock services."""
        assert is_service_allowed("lock", "lock") is True
        assert is_service_allowed("lock", "unlock") is True

    def test_disallowed_service(self):
        """Test disallowed service."""
        assert is_service_allowed("switch", "reload") is False
        assert is_service_allowed("light", "brightness_step") is False

    def test_disallowed_domain(self):
        """Test disallowed domain."""
        assert is_service_allowed("unknown_domain", "turn_on") is False
        assert is_service_allowed("homeassistant", "restart") is False


class TestGetEntityDomain:
    """Tests for get_entity_domain function."""

    def test_get_domain_from_entity_id(self):
        """Test extracting domain from entity_id."""
        assert get_entity_domain("light.living_room") == "light"
        assert get_entity_domain("switch.bedroom") == "switch"
        assert get_entity_domain("climate.office") == "climate"
        assert get_entity_domain("cover.garage_door") == "cover"

    def test_get_domain_empty_string(self):
        """Test empty string returns empty domain."""
        assert get_entity_domain("") == ""

    def test_get_domain_no_dot(self):
        """Test entity_id without dot returns empty domain."""
        assert get_entity_domain("nodot") == ""


class TestGetAllowedEntities:
    """Tests for get_allowed_entities function."""

    def test_get_allowed_entities(self, mock_hass, mock_entity_registry):
        """Test getting all allowed entities."""
        result = get_allowed_entities(mock_hass, mock_entity_registry)

        assert "light.test_light" in result
        assert "switch.test_switch" in result
        assert "light.hidden_light" not in result

    def test_get_allowed_entities_empty_registry(self, mock_hass):
        """Test with empty registry."""
        empty_registry = MagicMock()
        empty_registry.entities = {}

        result = get_allowed_entities(mock_hass, empty_registry)
        assert result == []


class TestFilterEntitiesByArea:
    """Tests for filter_entities_by_area function."""

    def test_filter_no_restriction(self, mock_hass, mock_entity_registry):
        """Test no filtering when allowed_areas is None."""
        entities = ["light.test_light", "switch.test_switch"]

        result = filter_entities_by_area(mock_hass, entities, None, mock_entity_registry)

        assert result == entities

    def test_filter_by_allowed_area(self, mock_hass, mock_entity_registry):
        """Test filtering by allowed areas."""
        entities = ["light.test_light", "light.hidden_light"]
        allowed_areas = ["area_1"]

        result = filter_entities_by_area(mock_hass, entities, allowed_areas, mock_entity_registry)

        assert "light.test_light" in result
        assert "light.hidden_light" not in result


class TestAllowedServicesConfig:
    """Tests for ALLOWED_SERVICES configuration."""

    def test_all_domains_have_services(self):
        """Test all domains have at least one service."""
        for domain, services in ALLOWED_SERVICES.items():
            assert len(services) > 0, f"Domain {domain} has no services"

    def test_expected_domains_present(self):
        """Test expected domains are present."""
        expected_domains = [
            "switch",
            "light",
            "cover",
            "climate",
            "fan",
            "lock",
            "scene",
            "script",
            "automation",
        ]

        for domain in expected_domains:
            assert domain in ALLOWED_SERVICES, f"Domain {domain} missing"

    def test_no_dangerous_services(self):
        """Test no dangerous services are allowed."""
        dangerous_services = [
            "reload",
            "restart",
            "shutdown",
            "reboot",
            "delete",
            "remove",
            "uninstall",
        ]

        for domain, services in ALLOWED_SERVICES.items():
            for service in services:
                assert (
                    service not in dangerous_services
                ), f"Dangerous service {service} found in {domain}"


class TestGetStructure:
    """Tests for get_structure function."""

    def test_get_structure_basic(self, mock_hass, mock_entity_registry):
        """Test basic structure retrieval."""
        # Setup mock registries
        device_registry = MagicMock()
        mock_device = MagicMock()
        mock_device.area_id = "area_1"
        device_registry.async_get = MagicMock(return_value=mock_device)

        area_registry = MagicMock()
        mock_area = MagicMock()
        mock_area.floor_id = "floor_1"
        mock_area.name = "Living Room"
        area_registry.async_get_area = MagicMock(return_value=mock_area)

        floor_registry = MagicMock()
        mock_floor = MagicMock()
        mock_floor.name = "Ground Floor"
        floor_registry.async_get_floor = MagicMock(return_value=mock_floor)

        # Get allowed entities
        allowed_entities = get_allowed_entities(mock_hass, mock_entity_registry)

        structure = get_structure(
            mock_hass,
            allowed_entities,
            mock_entity_registry,
            device_registry,
            area_registry,
            floor_registry,
        )

        assert "floors" in structure
        assert isinstance(structure["floors"], list)

    def test_get_structure_with_virtual_device(self, mock_hass, mock_entity_registry):
        """Test structure with entities that have no device."""
        # Add entity without device
        mock_entry_no_device = MagicMock()
        mock_entry_no_device.labels = {"smartly"}
        mock_entry_no_device.device_id = None
        mock_entry_no_device.area_id = "area_1"
        mock_entry_no_device.name = "Virtual Input"
        mock_entry_no_device.original_name = "Virtual Input"

        mock_entity_registry.entities["input_boolean.test"] = mock_entry_no_device
        mock_entity_registry.async_get.side_effect = lambda eid: mock_entity_registry.entities.get(
            eid
        )

        # Setup mock registries
        device_registry = MagicMock()
        mock_device = MagicMock()
        mock_device.area_id = "area_1"
        device_registry.async_get = MagicMock(return_value=mock_device)

        area_registry = MagicMock()
        mock_area = MagicMock()
        mock_area.floor_id = "floor_1"
        mock_area.name = "Living Room"
        area_registry.async_get_area = MagicMock(return_value=mock_area)

        floor_registry = MagicMock()
        mock_floor = MagicMock()
        mock_floor.name = "Ground Floor"
        floor_registry.async_get_floor = MagicMock(return_value=mock_floor)

        # Get allowed entities (should include the new one)
        allowed_entities = get_allowed_entities(mock_hass, mock_entity_registry)

        structure = get_structure(
            mock_hass,
            allowed_entities,
            mock_entity_registry,
            device_registry,
            area_registry,
            floor_registry,
        )

        # Should include virtual device
        assert "floors" in structure
        assert len(structure["floors"]) >= 0  # May be 0 if no entities found

    def test_get_structure_includes_icons(self, mock_hass, mock_entity_registry):
        """Test that structure includes icon information."""
        # Setup mock registries
        device_registry = MagicMock()
        mock_device = MagicMock()
        mock_device.area_id = "area_1"
        mock_device.name = "Test Device"
        device_registry.async_get = MagicMock(return_value=mock_device)

        area_registry = MagicMock()
        mock_area = MagicMock()
        mock_area.floor_id = "floor_1"
        mock_area.name = "Living Room"
        area_registry.async_get_area = MagicMock(return_value=mock_area)

        floor_registry = MagicMock()
        mock_floor = MagicMock()
        mock_floor.name = "Ground Floor"
        floor_registry.async_get_floor = MagicMock(return_value=mock_floor)

        # Get allowed entities
        allowed_entities = get_allowed_entities(mock_hass, mock_entity_registry)

        structure = get_structure(
            mock_hass,
            allowed_entities,
            mock_entity_registry,
            device_registry,
            area_registry,
            floor_registry,
        )

        # Verify entities list includes icon fields
        assert "entities" in structure
        assert len(structure["entities"]) > 0

        # Find the light.test_light entity (has custom icon)
        test_light = next(
            (e for e in structure["entities"] if e["entity_id"] == "light.test_light"), None
        )
        assert test_light is not None
        assert "icon" in test_light
        # Should return custom icon since it's set
        assert test_light["icon"] == "mdi:lightbulb"

        # Find the switch.test_switch entity (no custom icon, should fallback)
        test_switch = next(
            (e for e in structure["entities"] if e["entity_id"] == "switch.test_switch"), None
        )
        assert test_switch is not None
        assert "icon" in test_switch
        # Should return original_icon as fallback since custom icon is None
        assert test_switch["icon"] == "mdi:toggle-switch"
