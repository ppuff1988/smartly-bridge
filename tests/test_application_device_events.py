"""Tests for device event application use cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from custom_components.smartly_bridge.application.device_events import (
    DeviceEventCommand,
    DeviceEventUseCase,
)


class FakeDeviceEventPublisher:
    """Fake event publisher port."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def publish_device_event(self, event_data: dict[str, Any]) -> None:
        self.events.append(event_data)


class FakeEventDeduplicator:
    """Fake event dedupe store."""

    def __init__(self) -> None:
        self.events: dict[str, str] = {}

    def event_id_for_key(self, key: str) -> str | None:
        return self.events.get(key)

    def remember_event(self, key: str, event_id: str) -> None:
        self.events[key] = event_id


class FakeLocalAutomation:
    """Fake local automation port."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def handle_device_event(
        self,
        client_id: str,
        event: dict[str, Any],
    ) -> list[dict[str, Any]]:
        self.events.append((client_id, event))
        return [
            {
                "rule_id": "rule-left-single",
                "action_index": 0,
                "type": "device_command",
                "command_id": "cmd-auto",
                "status": "completed",
                "response_status": 200,
            }
        ]


def _fixture(name: str) -> dict[str, Any]:
    """Load an API vNext fixture."""
    return json.loads(
        (Path(__file__).parent / "fixtures" / "api-vnext" / name).read_text()
    )


@pytest.mark.asyncio
async def test_button_action_is_published_with_canonical_event_payload() -> None:
    """Legacy button action events are normalized to canonical button_event payloads."""
    publisher = FakeDeviceEventPublisher()
    use_case = DeviceEventUseCase(
        publisher,
        event_id_factory=lambda: "evt_fixed",
        received_at_factory=lambda: "2026-06-29T00:00:00Z",
    )

    result = await use_case.execute(
        "client-1",
        DeviceEventCommand(
            device_id="device_abc123",
            type="button_action",
            action="single_left",
            timestamp="2026-06-27T10:20:00.000Z",
            meta={"source": "zigbee2mqtt"},
        ),
    )

    assert result.status == 202
    assert result.body == {
        "success": True,
        "schema_version": "2026.06",
        "event_id": "evt_fixed",
        "device_id": "device_abc123",
        "action": "single_left",
        "received_at": "2026-06-29T00:00:00Z",
        "capability": "button_event",
        "event": "single_press",
        "payload": {"button": "left"},
        "events": [
            {
                "event_id": "evt_fixed",
                "device_id": "device_abc123",
                "capability": "button_event",
                "event": "single_press",
                "payload": {"button": "left"},
                "occurred_at": "2026-06-27T10:20:00.000Z",
            }
        ],
        "data": {
            "event_id": "evt_fixed",
            "status": "accepted",
            "events": [
                {
                    "event_id": "evt_fixed",
                    "device_id": "device_abc123",
                    "capability": "button_event",
                    "event": "single_press",
                    "payload": {"button": "left"},
                    "occurred_at": "2026-06-27T10:20:00.000Z",
                }
            ],
        },
        "warnings": [],
        "errors": [],
    }
    assert publisher.events == [
        {
            "event_id": "evt_fixed",
            "device_id": "device_abc123",
            "type": "button_action",
            "action": "single_left",
            "timestamp": "2026-06-27T10:20:00.000Z",
            "received_at": "2026-06-29T00:00:00Z",
            "client_id": "client-1",
            "meta": {"source": "zigbee2mqtt"},
            "capability": "button_event",
            "event": "single_press",
            "payload": {"button": "left"},
            "events": [
                {
                    "event_id": "evt_fixed",
                    "device_id": "device_abc123",
                    "capability": "button_event",
                    "event": "single_press",
                    "payload": {"button": "left"},
                    "occurred_at": "2026-06-27T10:20:00.000Z",
                }
            ],
        }
    ]


@pytest.mark.asyncio
async def test_button_action_response_includes_vnext_envelope() -> None:
    """Accepted device event responses expose API vNext envelope fields."""
    publisher = FakeDeviceEventPublisher()
    use_case = DeviceEventUseCase(
        publisher,
        event_id_factory=lambda: "evt_fixed",
        received_at_factory=lambda: "2026-06-29T00:00:00Z",
    )

    result = await use_case.execute(
        "client-1",
        DeviceEventCommand(
            device_id="device_abc123",
            type="button_action",
            action="single_left",
            timestamp="2026-06-27T10:20:00.000Z",
        ),
    )

    assert result.status == 202
    assert result.body["success"] is True
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {
        "event_id": "evt_fixed",
        "status": "accepted",
        "events": [
            {
                "event_id": "evt_fixed",
                "device_id": "device_abc123",
                "capability": "button_event",
                "event": "single_press",
                "payload": {"button": "left"},
                "occurred_at": "2026-06-27T10:20:00.000Z",
            }
        ],
    }


@pytest.mark.asyncio
async def test_button_action_response_matches_api_vnext_fixture() -> None:
    """Accepted device event full response remains stable for legacy and vNext clients."""
    publisher = FakeDeviceEventPublisher()
    use_case = DeviceEventUseCase(
        publisher,
        event_id_factory=lambda: "evt_fixed",
        received_at_factory=lambda: "2026-06-29T00:00:00Z",
    )

    result = await use_case.execute(
        "client-1",
        DeviceEventCommand(
            device_id="device_abc123",
            type="button_action",
            action="single_left",
            timestamp="2026-06-27T10:20:00.000Z",
        ),
    )

    assert result.body == _fixture("device-event-accepted.json")


@pytest.mark.asyncio
async def test_duplicate_button_action_reuses_event_id_without_republishing() -> None:
    """Repeated source events are idempotent and do not retrigger automation."""
    publisher = FakeDeviceEventPublisher()
    deduplicator = FakeEventDeduplicator()
    event_ids = iter(["evt_first", "evt_second"])
    use_case = DeviceEventUseCase(
        publisher,
        event_id_factory=lambda: next(event_ids),
        received_at_factory=lambda: "2026-06-29T00:00:00Z",
        deduplicator=deduplicator,
    )
    command = DeviceEventCommand(
        device_id="device_abc123",
        type="button_action",
        action="single_left",
        timestamp="2026-06-27T10:20:00.000Z",
    )

    first = await use_case.execute("client-1", command)
    second = await use_case.execute("client-1", command)

    assert first.status == 202
    assert first.body["event_id"] == "evt_first"
    assert second.status == 200
    assert second.body == {
        "success": True,
        "schema_version": "2026.06",
        "duplicate": True,
        "status": "duplicate",
        "event_id": "evt_first",
        "device_id": "device_abc123",
        "action": "single_left",
        "received_at": "2026-06-29T00:00:00Z",
        "capability": "button_event",
        "event": "single_press",
        "payload": {"button": "left"},
        "events": [
            {
                "event_id": "evt_first",
                "device_id": "device_abc123",
                "capability": "button_event",
                "event": "single_press",
                "payload": {"button": "left"},
                "occurred_at": "2026-06-27T10:20:00.000Z",
            }
        ],
        "data": {
            "event_id": "evt_first",
            "status": "duplicate",
            "events": [
                {
                    "event_id": "evt_first",
                    "device_id": "device_abc123",
                    "capability": "button_event",
                    "event": "single_press",
                    "payload": {"button": "left"},
                    "occurred_at": "2026-06-27T10:20:00.000Z",
                }
            ],
        },
        "warnings": [],
        "errors": [],
    }
    assert len(publisher.events) == 1


@pytest.mark.asyncio
async def test_button_action_triggers_local_automation_once() -> None:
    """Accepted canonical button events are dispatched to local automation."""
    publisher = FakeDeviceEventPublisher()
    automation = FakeLocalAutomation()
    use_case = DeviceEventUseCase(
        publisher,
        event_id_factory=lambda: "evt_fixed",
        received_at_factory=lambda: "2026-06-29T00:00:00Z",
        automation=automation,
    )

    result = await use_case.execute(
        "client-1",
        DeviceEventCommand(
            device_id="ldev_button",
            type="button_action",
            action="single_left",
            timestamp="2026-06-27T10:20:00.000Z",
        ),
    )

    assert result.status == 202
    assert automation.events == [
        (
            "client-1",
            {
                "event_id": "evt_fixed",
                "device_id": "ldev_button",
                "capability": "button_event",
                "event": "single_press",
                "payload": {"button": "left"},
                "occurred_at": "2026-06-27T10:20:00.000Z",
            },
        )
    ]
    assert result.body["automations"] == [
        {
            "rule_id": "rule-left-single",
            "action_index": 0,
            "type": "device_command",
            "command_id": "cmd-auto",
            "status": "completed",
            "response_status": 200,
        }
    ]
    assert result.body["data"]["automations"] == result.body["automations"]


@pytest.mark.asyncio
async def test_duplicate_button_action_does_not_trigger_local_automation() -> None:
    """Duplicate canonical button events are not dispatched to local automation."""
    publisher = FakeDeviceEventPublisher()
    deduplicator = FakeEventDeduplicator()
    automation = FakeLocalAutomation()
    event_ids = iter(["evt_first", "evt_second"])
    use_case = DeviceEventUseCase(
        publisher,
        event_id_factory=lambda: next(event_ids),
        received_at_factory=lambda: "2026-06-29T00:00:00Z",
        deduplicator=deduplicator,
        automation=automation,
    )
    command = DeviceEventCommand(
        device_id="ldev_button",
        type="button_action",
        action="single_left",
        timestamp="2026-06-27T10:20:00.000Z",
    )

    await use_case.execute("client-1", command)
    duplicate = await use_case.execute("client-1", command)

    assert duplicate.status == 200
    assert len(automation.events) == 1
    assert duplicate.body["data"].get("automations") is None


@pytest.mark.asyncio
async def test_duplicate_button_action_response_includes_vnext_envelope() -> None:
    """Duplicate event responses expose API vNext envelope fields."""
    publisher = FakeDeviceEventPublisher()
    deduplicator = FakeEventDeduplicator()
    event_ids = iter(["evt_first", "evt_second"])
    use_case = DeviceEventUseCase(
        publisher,
        event_id_factory=lambda: next(event_ids),
        received_at_factory=lambda: "2026-06-29T00:00:00Z",
        deduplicator=deduplicator,
    )
    command = DeviceEventCommand(
        device_id="device_abc123",
        type="button_action",
        action="single_left",
        timestamp="2026-06-27T10:20:00.000Z",
    )

    await use_case.execute("client-1", command)
    duplicate = await use_case.execute("client-1", command)

    assert duplicate.status == 200
    assert duplicate.body["success"] is True
    assert duplicate.body["duplicate"] is True
    assert duplicate.body["schema_version"] == "2026.06"
    assert duplicate.body["warnings"] == []
    assert duplicate.body["errors"] == []
    assert duplicate.body["data"] == {
        "event_id": "evt_first",
        "status": "duplicate",
        "events": [
            {
                "event_id": "evt_first",
                "device_id": "device_abc123",
                "capability": "button_event",
                "event": "single_press",
                "payload": {"button": "left"},
                "occurred_at": "2026-06-27T10:20:00.000Z",
            }
        ],
    }


@pytest.mark.asyncio
async def test_duplicate_button_action_response_matches_api_vnext_fixture() -> None:
    """Duplicate device event full response remains stable for legacy and vNext clients."""
    publisher = FakeDeviceEventPublisher()
    deduplicator = FakeEventDeduplicator()
    event_ids = iter(["evt_first", "evt_second"])
    use_case = DeviceEventUseCase(
        publisher,
        event_id_factory=lambda: next(event_ids),
        received_at_factory=lambda: "2026-06-29T00:00:00Z",
        deduplicator=deduplicator,
    )
    command = DeviceEventCommand(
        device_id="device_abc123",
        type="button_action",
        action="single_left",
        timestamp="2026-06-27T10:20:00.000Z",
    )

    await use_case.execute("client-1", command)
    duplicate = await use_case.execute("client-1", command)

    assert duplicate.status == 200
    assert duplicate.body == _fixture("device-event-duplicate.json")


@pytest.mark.asyncio
async def test_rotate_button_action_is_published_with_canonical_event_payload() -> None:
    """Rotary button actions are normalized to canonical rotate events."""
    publisher = FakeDeviceEventPublisher()
    use_case = DeviceEventUseCase(
        publisher,
        event_id_factory=lambda: "evt_rotate",
        received_at_factory=lambda: "2026-06-29T00:00:00Z",
    )

    result = await use_case.execute(
        "client-1",
        DeviceEventCommand(
            device_id="device_knob",
            type="button_action",
            action="rotate_left",
            timestamp="2026-06-27T10:20:00.000Z",
        ),
    )

    assert result.status == 202
    assert result.body["capability"] == "button_event"
    assert result.body["event"] == "rotate_left"
    assert result.body["payload"] == {"direction": "left"}
    assert result.body["events"] == [
        {
            "event_id": "evt_rotate",
            "device_id": "device_knob",
            "capability": "button_event",
            "event": "rotate_left",
            "payload": {"direction": "left"},
            "occurred_at": "2026-06-27T10:20:00.000Z",
        }
    ]
    assert publisher.events[0]["event"] == "rotate_left"
    assert publisher.events[0]["payload"] == {"direction": "left"}


@pytest.mark.parametrize(
    ("action", "expected_button"),
    [
        ("left_single", "left"),
        ("1_single", "1"),
    ],
)
@pytest.mark.asyncio
async def test_button_action_alias_formats_are_normalized_to_canonical_events(
    action: str,
    expected_button: str,
) -> None:
    """Brand-specific button action aliases normalize to canonical events."""
    publisher = FakeDeviceEventPublisher()
    use_case = DeviceEventUseCase(
        publisher,
        event_id_factory=lambda: "evt_alias",
        received_at_factory=lambda: "2026-06-29T00:00:00Z",
    )

    result = await use_case.execute(
        "client-1",
        DeviceEventCommand(
            device_id="device_abc123",
            type="button_action",
            action=action,
            timestamp="2026-06-27T10:20:00.000Z",
        ),
    )

    assert result.status == 202
    assert result.body["event"] == "single_press"
    assert result.body["payload"] == {"button": expected_button}
    assert publisher.events[0]["event"] == "single_press"
    assert publisher.events[0]["payload"] == {"button": expected_button}


@pytest.mark.asyncio
async def test_unsupported_button_action_is_rejected_before_publish() -> None:
    """Unsupported source actions do not reach the event publisher."""
    publisher = FakeDeviceEventPublisher()
    use_case = DeviceEventUseCase(
        publisher,
        event_id_factory=lambda: "evt_fixed",
        received_at_factory=lambda: "2026-06-29T00:00:00Z",
    )

    result = await use_case.execute(
        "client-1",
        DeviceEventCommand(
            device_id="device_abc123",
            type="button_action",
            action="triple_left",
            timestamp="2026-06-27T10:20:00.000Z",
        ),
    )

    assert result.status == 400
    assert result.body == {
        "error": "invalid_action",
        "message": "Unsupported button action",
        "schema_version": "2026.06",
        "data": {
            "device_id": "device_abc123",
            "status": "rejected",
        },
        "warnings": [],
        "errors": [
            {
                "code": "INVALID_ACTION",
                "message": "Unsupported button action",
                "target": "event.action",
                "retryable": False,
            }
        ],
    }
    assert publisher.events == []


@pytest.mark.asyncio
async def test_unsupported_button_action_response_includes_vnext_error_envelope() -> None:
    """Unsupported device event actions expose API vNext error envelope fields."""
    publisher = FakeDeviceEventPublisher()
    use_case = DeviceEventUseCase(
        publisher,
        event_id_factory=lambda: "evt_fixed",
        received_at_factory=lambda: "2026-06-29T00:00:00Z",
    )

    result = await use_case.execute(
        "client-1",
        DeviceEventCommand(
            device_id="device_abc123",
            type="button_action",
            action="triple_left",
            timestamp="2026-06-27T10:20:00.000Z",
        ),
    )

    assert result.status == 400
    assert result.body["error"] == "invalid_action"
    assert result.body["message"] == "Unsupported button action"
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {
        "device_id": "device_abc123",
        "status": "rejected",
    }
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "INVALID_ACTION",
            "message": "Unsupported button action",
            "target": "event.action",
            "retryable": False,
        }
    ]
    assert publisher.events == []


@pytest.mark.asyncio
async def test_unsupported_button_action_response_matches_api_vnext_fixture() -> None:
    """Device event error full response remains stable for legacy and vNext clients."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "api-vnext" / "device-event-error.json"
    )
    expected_body = json.loads(fixture_path.read_text())
    publisher = FakeDeviceEventPublisher()
    use_case = DeviceEventUseCase(
        publisher,
        event_id_factory=lambda: "evt_fixed",
        received_at_factory=lambda: "2026-06-29T00:00:00Z",
    )

    result = await use_case.execute(
        "client-1",
        DeviceEventCommand(
            device_id="device_abc123",
            type="button_action",
            action="triple_left",
            timestamp="2026-06-27T10:20:00.000Z",
        ),
    )

    assert result.body == expected_body


@pytest.mark.asyncio
async def test_unsupported_rotate_direction_is_rejected_before_publish() -> None:
    """Rotate events only accept canonical left/right directions."""
    publisher = FakeDeviceEventPublisher()
    use_case = DeviceEventUseCase(
        publisher,
        event_id_factory=lambda: "evt_fixed",
        received_at_factory=lambda: "2026-06-29T00:00:00Z",
    )

    result = await use_case.execute(
        "client-1",
        DeviceEventCommand(
            device_id="device_abc123",
            type="button_action",
            action="rotate_up",
            timestamp="2026-06-27T10:20:00.000Z",
        ),
    )

    assert result.status == 400
    assert result.body == {
        "error": "invalid_action",
        "message": "Unsupported button action",
        "schema_version": "2026.06",
        "data": {
            "device_id": "device_abc123",
            "status": "rejected",
        },
        "warnings": [],
        "errors": [
            {
                "code": "INVALID_ACTION",
                "message": "Unsupported button action",
                "target": "event.action",
                "retryable": False,
            }
        ],
    }
    assert publisher.events == []
