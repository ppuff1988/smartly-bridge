"""Device event application use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import uuid
from typing import Any, Callable

from ..domain.models import BridgeResponse
from .ports import (
    DeviceEventDeduplicatorPort,
    DeviceEventPublisherPort,
    LocalAutomationPort,
)

_BUTTON_EVENT_BY_ACTION = {
    "single": "single_press",
    "double": "double_press",
    "hold": "long_press",
    "release": "long_release",
}

SMARTLY_API_SCHEMA_VERSION = "2026.06"


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
        automation: LocalAutomationPort | None = None,
    ) -> None:
        self._publisher = publisher
        self._event_id_factory = event_id_factory or _new_event_id
        self._received_at_factory = received_at_factory or _utc_now
        self._deduplicator = deduplicator or _NoEventDeduplicator()
        self._automation = automation

    async def execute(self, client_id: str, command: DeviceEventCommand) -> BridgeResponse:
        """Publish a normalized event or return a validation error."""
        if command.type != "button_action":
            return device_event_error_response(
                command=command,
                error="missing_required_fields",
                message="Missing required event fields",
                target="event.type",
            )
        canonical = _canonical_button_event(command.action)
        if canonical is None:
            return device_event_error_response(
                command=command,
                error="invalid_action",
                message="Unsupported button action",
                target="event.action",
            )

        received_at = self._received_at_factory()
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
        automation_results: list[dict[str, Any]] = []
        if self._automation is not None:
            automation_results = await self._automation.handle_device_event(
                client_id,
                canonical_event,
            )

        body = {
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {
                "event_id": event_id,
                "device_id": command.device_id,
                "action": command.action,
                "received_at": received_at,
                **canonical,
                "status": "accepted",
                "events": [canonical_event],
            },
            "warnings": [],
            "errors": [],
        }
        if self._automation is not None:
            body["data"]["automations"] = automation_results
        return BridgeResponse(body, status=202)


class _NoEventDeduplicator:
    """Default deduplicator for non-idempotent event handling."""

    def event_id_for_key(self, key: str) -> str | None:
        """Return no existing event."""
        return None

    def remember_event(self, key: str, event_id: str) -> None:
        """Ignore remembered events."""


def is_supported_button_action(action: Any) -> bool:
    """Return whether a source button action can be normalized."""
    return isinstance(action, str) and _canonical_button_event(action) is not None


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
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {
                "event_id": event_id,
                "device_id": command.device_id,
                "action": command.action,
                "received_at": received_at,
                **canonical,
                "status": "duplicate",
                "duplicate": True,
                "events": [canonical_event],
            },
            "warnings": [],
            "errors": [],
        },
        status=200,
    )


def device_event_error_response(
    *,
    command: DeviceEventCommand,
    error: str,
    message: str,
    target: str,
    status: int = 400,
) -> BridgeResponse:
    """Return an API vNext event error response."""
    return BridgeResponse(
        {
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {
                "device_id": command.device_id,
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": error.upper(),
                    "message": message,
                    "target": target,
                    "retryable": False,
                }
            ],
        },
        status=status,
    )


def _canonical_button_event(action: str) -> dict[str, Any] | None:
    """Map source button action to canonical Smartly event fields."""
    source_event, _, button = action.partition("_")
    if source_event == "rotate":
        if button not in {"left", "right"}:
            return None
        return {
            "capability": "button_event",
            "event": action,
            "payload": {"direction": button},
        }
    if source_event not in _BUTTON_EVENT_BY_ACTION:
        button, _, source_event = action.partition("_")
    if source_event not in _BUTTON_EVENT_BY_ACTION or not button:
        return None
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
