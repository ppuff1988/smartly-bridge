"""Sync application use cases."""

from __future__ import annotations

from typing import Any

from ..domain.models import BridgeResponse
from .logical_devices import logical_devices_from_states
from .ports import SyncStatesPort, SyncStructurePort

SMARTLY_API_SCHEMA_VERSION = "2026.06"


class SyncStructureUseCase:
    """Return the platform-visible Home Assistant structure."""

    def __init__(self, gateway: SyncStructurePort) -> None:
        self._gateway = gateway

    def execute(self) -> BridgeResponse:
        """Return the structure payload."""
        return BridgeResponse(self._gateway.get_structure(), status=200)


class SyncStatesUseCase:
    """Return platform-visible entity states."""

    def __init__(self, gateway: SyncStatesPort, *, use_logical_devices: bool = False) -> None:
        self._gateway = gateway
        self._use_logical_devices = use_logical_devices

    async def execute(self) -> BridgeResponse:
        """Return states and count."""
        snapshots = await self._gateway.list_states()
        states = [state.to_sync_dict() for state in snapshots]
        logical_device_models = logical_devices_from_states(snapshots)
        logical_devices = [device.to_dict() for device in logical_device_models]
        warnings = _normalization_warnings(logical_devices)
        body: dict[str, Any] = {
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "states": states,
            "count": len(states),
            "normalization_warnings": warnings,
            "logical_devices": logical_devices,
            "data": {
                "states": states,
                "count": len(states),
                "logical_devices": logical_devices,
                "normalization_warnings": warnings,
            },
            "warnings": warnings,
            "errors": [],
        }
        if self._use_logical_devices:
            body.update(
                {
                    "read_path": "logical_devices",
                    "devices": logical_devices,
                    "device_count": len(logical_devices),
                }
            )
        return BridgeResponse(body, status=200)


def _normalization_warnings(logical_devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return shadow-normalization warnings for diagnostic fallback devices."""
    warnings: list[dict[str, Any]] = []
    for device in logical_devices:
        if device.get("device_class") != "diagnostic_device" and device.get("capabilities"):
            continue
        warnings.append(
            {
                "code": "diagnostic_device",
                "message": "Entity group could not be normalized to supported capabilities",
                "logical_device_id": device["id"],
                "entity_ids": device["source_entities"],
            }
        )
    return warnings
