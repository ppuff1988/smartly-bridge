"""Sync application use cases."""

from __future__ import annotations

from ..domain.models import BridgeResponse
from .logical_devices import logical_device_from_state
from .ports import SyncStatesPort, SyncStructurePort


class SyncStructureUseCase:
    """Return the platform-visible Home Assistant structure."""

    def __init__(self, gateway: SyncStructurePort) -> None:
        self._gateway = gateway

    def execute(self) -> BridgeResponse:
        """Return the structure payload."""
        return BridgeResponse(self._gateway.get_structure(), status=200)


class SyncStatesUseCase:
    """Return platform-visible entity states."""

    def __init__(self, gateway: SyncStatesPort) -> None:
        self._gateway = gateway

    async def execute(self) -> BridgeResponse:
        """Return states and count."""
        snapshots = await self._gateway.list_states()
        states = [state.to_sync_dict() for state in snapshots]
        logical_devices = [logical_device_from_state(state).to_dict() for state in snapshots]
        return BridgeResponse(
            {"states": states, "count": len(states), "logical_devices": logical_devices},
            status=200,
        )
