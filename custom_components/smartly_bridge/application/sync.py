"""Sync application use cases."""

from __future__ import annotations

from typing import Any

from ..domain.models import BridgeResponse, EntityStateSnapshot
from .logical_devices import logical_devices_from_states
from .ports import RawDiagnosticRecorderPort, SyncStatesPort, SyncStructurePort

SMARTLY_API_SCHEMA_VERSION = "2026.06"


def sync_error_response(error: str, *, status: int, target: str) -> BridgeResponse:
    """Return an API vNext sync error response."""
    return BridgeResponse(
        {
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": error.upper(),
                    "message": error.replace("_", " "),
                    "target": target,
                    "retryable": False,
                }
            ],
        },
        status=status,
    )


class SyncStructureUseCase:
    """Return the platform-visible Home Assistant structure."""

    def __init__(self, gateway: SyncStructurePort) -> None:
        self._gateway = gateway

    def execute(self) -> BridgeResponse:
        """Return the structure payload."""
        structure = self._gateway.get_structure()
        data = {
            **structure,
            "device_count": len(structure.get("devices", [])),
        }
        return BridgeResponse(
            {
                **structure,
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": data,
                "warnings": [],
                "errors": [],
            },
            status=200,
        )


class SyncStatesUseCase:
    """Return platform-visible entity states."""

    def __init__(
        self,
        gateway: SyncStatesPort,
        *,
        use_logical_devices: bool = False,
        raw_diagnostic_recorder: RawDiagnosticRecorderPort | None = None,
    ) -> None:
        self._gateway = gateway
        self._use_logical_devices = use_logical_devices
        self._raw_diagnostic_recorder = raw_diagnostic_recorder

    async def execute(self) -> BridgeResponse:
        """Return states and count."""
        snapshots = await self._gateway.list_states()
        states = [state.to_sync_dict() for state in snapshots]
        logical_device_models = logical_devices_from_states(snapshots)
        logical_devices = [device.to_dict() for device in logical_device_models]
        self._attach_raw_diagnostic_refs(logical_devices, snapshots)
        warnings = _normalization_warnings(logical_devices)
        updates = _state_updates(logical_devices, snapshots)
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
                "device_count": len(logical_devices),
                "updates": updates,
            },
            "warnings": warnings,
            "errors": [],
        }
        if self._use_logical_devices:
            logical_read_path = {
                "read_path": "logical_devices",
                "devices": logical_devices,
                "device_count": len(logical_devices),
            }
            body.update(logical_read_path)
            body["data"].update(logical_read_path)
        return BridgeResponse(body, status=200)

    def _attach_raw_diagnostic_refs(
        self,
        logical_devices: list[dict[str, Any]],
        snapshots: list[EntityStateSnapshot],
    ) -> None:
        """Attach raw diagnostic refs and persist payloads out-of-band."""
        if self._raw_diagnostic_recorder is None:
            return

        snapshots_by_entity = {snapshot.entity_id: snapshot for snapshot in snapshots}
        for device in logical_devices:
            if device.get("device_class") != "diagnostic_device":
                continue

            raw_ref = f"raw_{device['id']}"
            entity_ids = [
                entity_id
                for entity_id in device.get("source_entities", [])
                if isinstance(entity_id, str)
            ]
            device["raw_refs"] = [
                {
                    "raw_ref": raw_ref,
                    "kind": "normalization_diagnostic",
                    "source": "home_assistant",
                    "entity_ids": entity_ids,
                }
            ]
            self._raw_diagnostic_recorder.record_raw_diagnostic(
                raw_ref,
                {
                    "logical_device_id": device["id"],
                    "device_class": device["device_class"],
                    "source_entities": [
                        snapshots_by_entity[entity_id].to_sync_dict()
                        for entity_id in entity_ids
                        if entity_id in snapshots_by_entity
                    ],
                },
            )


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


def _state_updates(
    logical_devices: list[dict[str, Any]],
    snapshots: list[EntityStateSnapshot],
) -> list[dict[str, Any]]:
    """Return API vNext capability state updates from logical-device state."""
    updated_at_by_entity = {
        snapshot.entity_id: snapshot.last_updated or snapshot.last_changed
        for snapshot in snapshots
    }
    updates: list[dict[str, Any]] = []
    for device in logical_devices:
        for capability in device.get("capabilities", []):
            state = capability.get("state") or {}
            if not capability.get("readable", True) or capability.get("event_only") or not state:
                continue
            update_state = dict(state)
            updated_at = _capability_updated_at(capability, updated_at_by_entity)
            if updated_at:
                update_state["updated_at"] = updated_at
            updates.append(
                {
                    "device_id": device["id"],
                    "capability": capability["type"],
                    "state": update_state,
                }
            )
    return updates


def _capability_updated_at(
    capability: dict[str, Any],
    updated_at_by_entity: dict[str, str | None],
) -> str | None:
    """Return the first source timestamp available for a capability."""
    for source_ref in capability.get("source_refs", []):
        entity_id = source_ref.get("source_entity_id")
        if not isinstance(entity_id, str):
            continue
        updated_at = updated_at_by_entity.get(entity_id)
        if updated_at:
            return updated_at
    return None
