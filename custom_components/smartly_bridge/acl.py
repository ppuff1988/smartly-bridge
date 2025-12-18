"""Access Control List handling for Smartly Bridge."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .const import ALLOWED_SERVICES, PLATFORM_CONTROL_LABEL

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.area_registry import AreaRegistry
    from homeassistant.helpers.device_registry import DeviceRegistry
    from homeassistant.helpers.entity_registry import EntityRegistry
    from homeassistant.helpers.floor_registry import FloorRegistry


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
    """Get list of all entities with platform_control label."""
    allowed = []

    for entity_id, entry in entity_registry.entities.items():
        if entry.labels and PLATFORM_CONTROL_LABEL in entry.labels:
            allowed.append(entity_id)

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

    Returns only entities with platform_control label.
    Structure: floors -> areas -> devices -> entities
    """
    # Get allowed entities
    allowed_entities = get_allowed_entities(hass, entity_registry)

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
        area_id = None
        floor_id = None

        if device_id:
            area_id = device_to_area.get(device_id)
            if area_id:
                floor_id = area_to_floor.get(area_id)

        # Handle entities without device/area/floor
        floor_key = floor_id or "_no_floor"
        area_key = area_id or "_no_area"
        device_key = device_id or "_no_device"

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

    # Convert to list format
    result = {"floors": []}

    for floor_key, floor_data in floors_dict.items():
        floor_output = {
            "id": floor_data["id"],
            "name": floor_data["name"],
            "areas": [],
        }

        for area_key, area_data in floor_data["areas"].items():
            area_output = {
                "id": area_data["id"],
                "name": area_data["name"],
                "devices": [],
            }

            for device_key, device_data in area_data["devices"].items():
                device_output = {
                    "id": device_data["id"],
                    "name": device_data["name"],
                    "entities": device_data["entities"],
                }
                area_output["devices"].append(device_output)

            floor_output["areas"].append(area_output)

        result["floors"].append(floor_output)

    return result
