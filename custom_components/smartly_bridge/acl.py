"""Access Control List handling for Smartly Bridge."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .const import ALLOWED_SERVICES, PLATFORM_CONTROL_LABEL

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.area_registry import AreaRegistry
    from homeassistant.helpers.device_registry import DeviceRegistry
    from homeassistant.helpers.entity_registry import EntityRegistry
    from homeassistant.helpers.floor_registry import FloorRegistry

_LOGGER = logging.getLogger(__name__)


def is_entity_allowed(
    hass: HomeAssistant,
    entity_id: str,
    entity_registry: EntityRegistry,
) -> bool:
    """Check if entity is allowed for platform control.

    An entity is allowed if it has the 'platform_control' label.
    """
    entry = entity_registry.async_get(entity_id)
    if entry is None:
        return False

    # Check for smartly_control label
    if entry.labels and PLATFORM_CONTROL_LABEL in entry.labels:
        return True

    return False


def is_service_allowed(domain: str, service: str) -> bool:
    """Check if service is in the allowed whitelist."""
    if domain not in ALLOWED_SERVICES:
        return False

    return service in ALLOWED_SERVICES[domain]


def get_allowed_entities(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
) -> list[str]:
    """Get list of all entities with smartly label."""
    allowed = []
    total_entities = 0

    for entity_id, entry in entity_registry.entities.items():
        total_entities += 1
        if entry.labels and PLATFORM_CONTROL_LABEL in entry.labels:
            allowed.append(entity_id)
            _LOGGER.debug(
                "Entity %s has '%s' label (labels: %s)",
                entity_id,
                PLATFORM_CONTROL_LABEL,
                entry.labels,
            )

    _LOGGER.info(
        "Found %d entities with '%s' label out of %d total entities",
        len(allowed),
        PLATFORM_CONTROL_LABEL,
        total_entities,
    )
    
    if len(allowed) == 0:
        _LOGGER.warning(
            "No entities found with entity label '%s'. "
            "Note: This requires Entity Labels (for organizing entities), NOT NFC Tags. "
            "Entity Labels feature may not be available in all Home Assistant versions. "
            "If unavailable, entities will need to be whitelisted using an alternative method. "
            "Total entities in registry: %d",
            PLATFORM_CONTROL_LABEL,
            total_entities,
        )
    
    return allowed


def get_entity_domain(entity_id: str) -> str:
    """Extract domain from entity_id."""
    return entity_id.split(".")[0] if "." in entity_id else ""


def filter_entities_by_area(
    hass: HomeAssistant,
    entity_ids: list[str],
    allowed_areas: list[str] | None,
    entity_registry: EntityRegistry,
) -> list[str]:
    """Filter entities by allowed areas."""
    if allowed_areas is None:
        return entity_ids

    filtered = []
    for entity_id in entity_ids:
        entry = entity_registry.async_get(entity_id)
        if entry and entry.area_id and entry.area_id in allowed_areas:
            filtered.append(entity_id)
        elif entry and entry.area_id is None:
            # Entities without area are excluded when area filter is active
            pass

    return filtered


def get_structure(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    area_registry: AreaRegistry,
    floor_registry: FloorRegistry,
) -> dict[str, Any]:
    """Get the hierarchical structure of floors/areas/devices/entities.

    Returns only entities with smartly label.
    Structure: floors -> areas -> devices -> entities
    """
    # Get allowed entities
    allowed_entities = get_allowed_entities(hass, entity_registry)

    if not allowed_entities:
        _LOGGER.warning(
            "No entities found with '%s' entity label. "
            "Note: Entity Labels (for organizing entities) are different from NFC Tags. "
            "This feature may not be available in all Home Assistant versions.",
            PLATFORM_CONTROL_LABEL,
        )
        return {
            "floors": [],
            "areas": [],
            "devices": [],
            "entities": [],
        }

    # Build entity -> device mapping
    entity_to_device: dict[str, str | None] = {}
    for entity_id in allowed_entities:
        entry = entity_registry.async_get(entity_id)
        if entry:
            entity_to_device[entity_id] = entry.device_id

    # Build device -> area mapping
    device_to_area: dict[str, str | None] = {}
    for device_id in set(entity_to_device.values()):
        if device_id:
            device = device_registry.async_get(device_id)
            if device:
                device_to_area[device_id] = device.area_id

    # Build area -> floor mapping
    area_to_floor: dict[str, str | None] = {}
    for area_id in set(device_to_area.values()):
        if area_id:
            area = area_registry.async_get_area(area_id)
            if area:
                area_to_floor[area_id] = area.floor_id

    # Build structure
    floors_dict: dict[str, dict[str, Any]] = {}

    for entity_id in allowed_entities:
        entry = entity_registry.async_get(entity_id)
        if not entry:
            continue

        device_id = entry.device_id
        # First check entity's direct area_id, then fall back to device's area
        area_id = entry.area_id
        if area_id is None and device_id:
            area_id = device_to_area.get(device_id)

        # Get floor_id from area
        floor_id = None
        if area_id:
            floor_id = area_to_floor.get(area_id)

        # Skip entities without proper organization (no device or area)
        # to avoid creating null structures
        if not device_id:
            _LOGGER.debug(
                "Skipping entity %s: no device assigned",
                entity_id,
            )
            continue

        # Handle entities without device/area/floor
        floor_key = floor_id or "_no_floor"
        area_key = area_id or "_no_area"
        device_key = device_id

        # Initialize floor
        if floor_key not in floors_dict:
            floor_name = None
            if floor_id:
                floor = floor_registry.async_get_floor(floor_id)
                floor_name = floor.name if floor else None
            floors_dict[floor_key] = {
                "id": floor_id,
                "name": floor_name,
                "areas": {},
            }

        # Initialize area
        if area_key not in floors_dict[floor_key]["areas"]:
            area_name = None
            if area_id:
                area = area_registry.async_get_area(area_id)
                area_name = area.name if area else None
            floors_dict[floor_key]["areas"][area_key] = {
                "id": area_id,
                "name": area_name,
                "devices": {},
            }

        # Initialize device
        if device_key not in floors_dict[floor_key]["areas"][area_key]["devices"]:
            device_name = None
            if device_id:
                device = device_registry.async_get(device_id)
                device_name = device.name if device else None
            floors_dict[floor_key]["areas"][area_key]["devices"][device_key] = {
                "id": device_id,
                "name": device_name,
                "entities": [],
            }

        # Add entity
        entity_data = {
            "entity_id": entity_id,
            "domain": get_entity_domain(entity_id),
            "name": entry.name or entry.original_name,
        }
        floors_dict[floor_key]["areas"][area_key]["devices"][device_key]["entities"].append(
            entity_data
        )

    # Convert to list format and collect all items
    result: dict[str, list] = {
        "floors": [],
        "areas": [],
        "devices": [],
        "entities": [],
    }

    # Track unique areas and devices to avoid duplicates
    seen_areas: set[str] = set()
    seen_devices: set[str] = set()

    for floor_key, floor_data in floors_dict.items():
        # Include "_no_floor" entries but don't add them to floors list
        floor_output = {
            "id": floor_data["id"],
            "name": floor_data["name"],
            "areas": [],
        }

        for area_key, area_data in floor_data["areas"].items():
            # Include "_no_area" entries but don't add them to areas list

            area_output = {
                "id": area_data["id"],
                "name": area_data["name"],
                "devices": [],
            }

            # Add to top-level areas list if not already added (skip null areas)
            if area_key not in seen_areas and area_key != "_no_area":
                seen_areas.add(area_key)
                result["areas"].append({
                    "id": area_data["id"],
                    "name": area_data["name"],
                    "floor_id": floor_data["id"],
                })

            for device_key, device_data in area_data["devices"].items():
                device_output = {
                    "id": device_data["id"],
                    "name": device_data["name"],
                    "entities": device_data["entities"],
                }
                area_output["devices"].append(device_output)

                # Add to top-level devices list if not already added
                if device_key not in seen_devices:
                    seen_devices.add(device_key)
                    result["devices"].append({
                        "id": device_data["id"],
                        "name": device_data["name"],
                        # Only include area_id if it's not a null area
                        "area_id": area_data["id"] if area_key != "_no_area" else None,
                    })

                # Add all entities to top-level entities list
                for entity in device_data["entities"]:
                    result["entities"].append({
                        "entity_id": entity["entity_id"],
                        "domain": entity["domain"],
                        "name": entity["name"],
                        "device_id": device_data["id"],
                    })

            # Only add area to floor output if it's not a null area
            if area_key != "_no_area":
                floor_output["areas"].append(area_output)

        # Only add floor to result if it's not a null floor
        if floor_key != "_no_floor":
            result["floors"].append(floor_output)

    return result
