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


def _build_mappings(
    allowed_entities: list[str],
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    area_registry: AreaRegistry,
) -> tuple[dict[str, str | None], dict[str, str | None], dict[str, str | None]]:
    """Build entity->device, device->area, and area->floor mappings."""
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

    return entity_to_device, device_to_area, area_to_floor


def _initialize_floor(
    floor_id: str | None,
    floors_dict: dict[str, dict[str, Any]],
    floor_registry: FloorRegistry,
) -> str:
    """Initialize floor in floors_dict and return floor_key."""
    floor_key = floor_id or "_no_floor"
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
    return floor_key


def _initialize_area(
    area_id: str | None,
    floor_key: str,
    floors_dict: dict[str, dict[str, Any]],
    area_registry: AreaRegistry,
) -> str:
    """Initialize area in floors_dict and return area_key."""
    area_key = area_id or "_no_area"
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
    return area_key


def _initialize_device(
    device_id: str,
    floor_key: str,
    area_key: str,
    floors_dict: dict[str, dict[str, Any]],
    device_registry: DeviceRegistry,
) -> None:
    """Initialize device in floors_dict."""
    if device_id not in floors_dict[floor_key]["areas"][area_key]["devices"]:
        device = device_registry.async_get(device_id)
        device_name = device.name if device else None
        floors_dict[floor_key]["areas"][area_key]["devices"][device_id] = {
            "id": device_id,
            "name": device_name,
            "entities": [],
        }


def _build_floors_dict(
    allowed_entities: list[str],
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    area_registry: AreaRegistry,
    floor_registry: FloorRegistry,
    entity_to_device: dict[str, str | None],
    device_to_area: dict[str, str | None],
    area_to_floor: dict[str, str | None],
) -> dict[str, dict[str, Any]]:
    """Build hierarchical floors dictionary."""
    floors_dict: dict[str, dict[str, Any]] = {}

    for entity_id in allowed_entities:
        entry = entity_registry.async_get(entity_id)
        if not entry:
            _LOGGER.debug("Skipping entity %s: not found in registry", entity_id)
            continue

        device_id = entry.device_id

        # Handle entities without device (e.g., input_boolean, input_button)
        if not device_id:
            _LOGGER.debug("Entity %s has no device, using virtual device", entity_id)
            # Use a virtual device ID for entities without devices
            device_id = f"_virtual_{get_entity_domain(entity_id)}"
            area_id = entry.area_id
            floor_id = area_to_floor.get(area_id) if area_id else None
        else:
            area_id = entry.area_id or device_to_area.get(device_id)
            floor_id = area_to_floor.get(area_id) if area_id else None

        # Initialize floor, area, device
        floor_key = _initialize_floor(floor_id, floors_dict, floor_registry)
        area_key = _initialize_area(area_id, floor_key, floors_dict, area_registry)

        # For virtual devices, use a simplified initialization
        if device_id.startswith("_virtual_"):
            if device_id not in floors_dict[floor_key]["areas"][area_key]["devices"]:
                domain = get_entity_domain(entity_id)
                floors_dict[floor_key]["areas"][area_key]["devices"][device_id] = {
                    "id": device_id,
                    "name": f"Virtual {domain.replace('_', ' ').title()} Device",
                    "entities": [],
                }
        else:
            _initialize_device(device_id, floor_key, area_key, floors_dict, device_registry)

        # Add entity
        entity_data = {
            "entity_id": entity_id,
            "domain": get_entity_domain(entity_id),
            "name": entry.name or entry.original_name,
        }
        floors_dict[floor_key]["areas"][area_key]["devices"][device_id]["entities"].append(
            entity_data
        )

    return floors_dict


def _convert_to_result_format(floors_dict: dict[str, dict[str, Any]]) -> dict[str, list]:
    """Convert floors_dict to flat result format with all items."""
    result: dict[str, list] = {
        "floors": [],
        "areas": [],
        "devices": [],
        "entities": [],
    }

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
                result["areas"].append(
                    {
                        "id": area_data["id"],
                        "name": area_data["name"],
                        "floor_id": floor_data["id"],
                    }
                )

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
                    result["devices"].append(
                        {
                            "id": device_data["id"],
                            "name": device_data["name"],
                            # Only include area_id if it's not a null area
                            "area_id": area_data["id"] if area_key != "_no_area" else None,
                        }
                    )

                # Add all entities to top-level entities list
                for entity in device_data["entities"]:
                    result["entities"].append(
                        {
                            "entity_id": entity["entity_id"],
                            "domain": entity["domain"],
                            "name": entity["name"],
                            "device_id": device_data["id"],
                        }
                    )

            # Only add area to floor output if it's not a null area
            if area_key != "_no_area":
                floor_output["areas"].append(area_output)

        # Only add floor to result if it's not a null floor
        if floor_key != "_no_floor":
            result["floors"].append(floor_output)

    return result


def get_structure(
    hass: HomeAssistant,
    allowed_entities: list[str],
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    area_registry: AreaRegistry,
    floor_registry: FloorRegistry,
) -> dict[str, list]:
    """Get hierarchical structure of allowed entities organized by floors/areas/devices.

    Returns a dictionary with lists of floors, areas, devices, and entities.
    Each entity is grouped within its device, area, and floor.
    Complexity reduced by extracting helper functions.
    """
    # Build all mappings
    _, device_to_area, area_to_floor = _build_mappings(
        allowed_entities,
        entity_registry,
        device_registry,
        area_registry,
    )

    # Build hierarchical dictionary
    floors_dict = _build_floors_dict(
        allowed_entities,
        entity_registry,
        device_registry,
        area_registry,
        floor_registry,
        {},  # entity_to_device not needed
        device_to_area,
        area_to_floor,
    )

    # Convert to result format
    return _convert_to_result_format(floors_dict)
