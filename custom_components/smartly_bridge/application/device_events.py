"""Device event application use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import uuid
from typing import Any, Callable

from ..domain.models import BridgeResponse
from .ports import DeviceEventPublisherPort

SUPPORTED_BUTTON_ACTIONS = {
    "single_left",
    "single_right",
    "double_left",
    "double_right",
    "hold_left",
    "hold_right",
    "release_left",
    "release_right",
    "single_both",
    "double_both",
    "hold_both",
}

_BUTTON_EVENT_BY_ACTION = {
    "single": "single_press",
    "double": "double_press",
    "hold": "long_press",
    "release": "long_release",
}


@dataclass(frozen=True)
class DeviceEventCommand:
    """Device event requested by Platform or a protocol adapter."""

    device_id: str
    type: str
    action: str
    timestamp: str
    meta: dict[str, Any] = field(default_factory=dict)


class DeviceEventUseCase:
    """Validate, normalize, and publish stateless device events."""

    def __init__(
        self,
        publisher: DeviceEventPublisherPort,
        *,
        event_id_factory: Callable[[], str] | None = None,
        received_at_factory: Callable[[], str] | None = None,
    ) -> None:
        self._publisher = publisher
        self._event_id_factory = event_id_factory or _new_event_id
        self._received_at_factory = received_at_factory or _utc_now

    async def execute(self, client_id: str, command: DeviceEventCommand) -> BridgeResponse:
        """Publish a normalized event or return a validation error."""
        if command.type != "button_action":
            return BridgeResponse({"error": "missing_required_fields"}, status=400)
        if command.action not in SUPPORTED_BUTTON_ACTIONS:
            return BridgeResponse(
                {"error": "invalid_action", "message": "Unsupported button action"},
                status=400,
            )

        event_id = self._event_id_factory()
        received_at = self._received_at_factory()
        canonical = _canonical_button_event(command.action)
        event_data = {
            "event_id": event_id,
            "device_id": command.device_id,
            "type": command.type,
            "action": command.action,
            "timestamp": command.timestamp,
            "received_at": received_at,
            "client_id": client_id,
            "meta": command.meta,
            **canonical,
        }
        self._publisher.publish_device_event(event_data)

        return BridgeResponse(
            {
                "success": True,
                "event_id": event_id,
                "device_id": command.device_id,
                "action": command.action,
                "received_at": received_at,
                **canonical,
            },
            status=202,
        )


def _canonical_button_event(action: str) -> dict[str, Any]:
    """Map legacy source button action to canonical Smartly event fields."""
    source_event, _, button = action.partition("_")
    return {
        "capability": "button_event",
        "event": _BUTTON_EVENT_BY_ACTION[source_event],
        "payload": {"button": button},
    }


def _new_event_id() -> str:
    """Return a new event ID."""
    return f"evt_{uuid.uuid4().hex}"


def _utc_now() -> str:
    """Return current UTC timestamp."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
