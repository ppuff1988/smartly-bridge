"""Device event application use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import uuid
from typing import Any, Callable

from ..domain.models import BridgeResponse
from .ports import DeviceEventDeduplicatorPort, DeviceEventPublisherPort

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
    "rotate_left",
    "rotate_right",
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
        deduplicator: DeviceEventDeduplicatorPort | None = None,
    ) -> None:
        self._publisher = publisher
        self._event_id_factory = event_id_factory or _new_event_id
        self._received_at_factory = received_at_factory or _utc_now
        self._deduplicator = deduplicator or _NoEventDeduplicator()

    async def execute(self, client_id: str, command: DeviceEventCommand) -> BridgeResponse:
        """Publish a normalized event or return a validation error."""
        if command.type != "button_action":
            return BridgeResponse({"error": "missing_required_fields"}, status=400)
        if command.action not in SUPPORTED_BUTTON_ACTIONS:
            return BridgeResponse(
                {"error": "invalid_action", "message": "Unsupported button action"},
                status=400,
            )

        received_at = self._received_at_factory()
        canonical = _canonical_button_event(command.action)
        dedupe_key = _event_dedupe_key(client_id, command)
        existing_event_id = self._deduplicator.event_id_for_key(dedupe_key)
        if existing_event_id is not None:
            canonical_event = _event_ingestion_payload(
                event_id=existing_event_id,
                device_id=command.device_id,
                occurred_at=command.timestamp,
                canonical=canonical,
            )
            return _duplicate_event_response(
                command=command,
                event_id=existing_event_id,
                received_at=received_at,
                canonical=canonical,
                canonical_event=canonical_event,
            )

        event_id = self._event_id_factory()
        canonical_event = _event_ingestion_payload(
            event_id=event_id,
            device_id=command.device_id,
            occurred_at=command.timestamp,
            canonical=canonical,
        )
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
            "events": [canonical_event],
        }
        self._publisher.publish_device_event(event_data)
        self._deduplicator.remember_event(dedupe_key, event_id)

        return BridgeResponse(
            {
                "success": True,
                "event_id": event_id,
                "device_id": command.device_id,
                "action": command.action,
                "received_at": received_at,
                **canonical,
                "events": [canonical_event],
            },
            status=202,
        )


class _NoEventDeduplicator:
    """Default deduplicator that preserves legacy non-idempotent behavior."""

    def event_id_for_key(self, key: str) -> str | None:
        """Return no existing event."""
        return None

    def remember_event(self, key: str, event_id: str) -> None:
        """Ignore remembered events."""


def _event_dedupe_key(client_id: str, command: DeviceEventCommand) -> str:
    """Return the event idempotency key."""
    return "|".join(
        [
            client_id,
            command.device_id,
            command.type,
            command.action,
            command.timestamp,
        ]
    )


def _duplicate_event_response(
    *,
    command: DeviceEventCommand,
    event_id: str,
    received_at: str,
    canonical: dict[str, Any],
    canonical_event: dict[str, Any],
) -> BridgeResponse:
    """Return the canonical duplicate event response."""
    return BridgeResponse(
        {
            "success": True,
            "duplicate": True,
            "status": "duplicate",
            "event_id": event_id,
            "device_id": command.device_id,
            "action": command.action,
            "received_at": received_at,
            **canonical,
            "events": [canonical_event],
        },
        status=200,
    )


def _canonical_button_event(action: str) -> dict[str, Any]:
    """Map legacy source button action to canonical Smartly event fields."""
    source_event, _, button = action.partition("_")
    if source_event == "rotate":
        return {
            "capability": "button_event",
            "event": action,
            "payload": {"direction": button},
        }
    return {
        "capability": "button_event",
        "event": _BUTTON_EVENT_BY_ACTION[source_event],
        "payload": {"button": button},
    }


def _event_ingestion_payload(
    *,
    event_id: str,
    device_id: str,
    occurred_at: str,
    canonical: dict[str, Any],
) -> dict[str, Any]:
    """Return the API vNext event ingestion payload."""
    return {
        "event_id": event_id,
        "device_id": device_id,
        "capability": canonical["capability"],
        "event": canonical["event"],
        "payload": canonical["payload"],
        "occurred_at": occurred_at,
    }


def _new_event_id() -> str:
    """Return a new event ID."""
    return f"evt_{uuid.uuid4().hex}"


def _utc_now() -> str:
    """Return current UTC timestamp."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
