"""Tests for device event application use cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from custom_components.smartly_bridge.application.device_events import (
    DeviceEventCapabilityRegistry,
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


class FakeDeviceEventCapabilities:
    """Fake declared device event capability registry."""

    def __init__(self, supported: set[tuple[str, str, str]]) -> None:
        self.supported = supported
        self.lookups: list[tuple[str, str, str]] = []

    def supports_event(self, device_id: str, channel: str, event: str) -> bool | None:
        lookup = (device_id, channel, event)
        self.lookups.append(lookup)
        return lookup in self.supported


def _fixture(name: str) -> dict[str, Any]:
    """Load an API vNext fixture."""
    return json.loads((Path(__file__).parent / "fixtures" / "api-vnext" / name).read_text())


@pytest.mark.asyncio
async def test_declared_triple_press_is_accepted() -> None:
    """Triple press is accepted only when the device schema declares it."""
    publisher = FakeDeviceEventPublisher()
    capabilities = FakeDeviceEventCapabilities({("device_h1", "left", "triple_press")})
    use_case = DeviceEventUseCase(
        publisher,
        capabilities=capabilities,
        event_id_factory=lambda: "evt_triple",
        received_at_factory=lambda: "2026-07-13T14:00:00Z",
    )

    result = await use_case.execute(
        "client-1",
        DeviceEventCommand(
            device_id="device_h1",
            type="button_action",
            action="triple_left",
            timestamp="2026-07-13T14:00:00Z",
        ),
    )

    assert result.status == 202
    assert result.body["data"]["event"] == "triple_press"
    assert result.body["data"]["payload"] == {"button": "left"}
    assert capabilities.lookups == [("device_h1", "left", "triple_press")]


@pytest.mark.asyncio
async def test_undeclared_gesture_is_rejected_for_known_device_schema() -> None:
    """A known device schema rejects vocabulary that its channel does not support."""
    publisher = FakeDeviceEventPublisher()
    capabilities = FakeDeviceEventCapabilities({("device_fast_mode", "left", "single_press")})
    use_case = DeviceEventUseCase(publisher, capabilities=capabilities)

    result = await use_case.execute(
        "client-1",
        DeviceEventCommand(
            device_id="device_fast_mode",
            type="button_action",
            action="double_left",
            timestamp="2026-07-13T14:00:00Z",
        ),
    )

    assert result.status == 400
    assert result.body["errors"][0]["code"] == "INVALID_ACTION"
    assert publisher.events == []


def test_event_capability_registry_distinguishes_unknown_and_undeclared_events() -> None:
    """The registry keeps unknown devices compatible and known schemas strict."""
    registry = DeviceEventCapabilityRegistry()
    registry.replace(
        [
            {
                "id": "device_h1",
                "capabilities": [
                    {
                        "type": "button_event",
                        "constraints": {
                            "event_schema_version": 1,
                            "channels": [
                                {
                                    "key": "left",
                                    "events": ["single_press", "triple_press"],
                                }
                            ],
                        },
                    }
                ],
            }
        ]
    )

    assert registry.supports_event("device_h1", "left", "triple_press") is True
    assert registry.supports_event("device_h1", "left", "double_press") is False
    assert registry.supports_event("unknown_device", "left", "single_press") is None


@pytest.mark.asyncio
async def test_button_action_is_published_with_canonical_event_payload() -> None:
    """Source button action events are normalized to canonical button_event payloads."""
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
        "schema_version": "2026.06",
        "data": {
            "event_id": "evt_fixed",
            "device_id": "device_abc123",
            "action": "single_left",
            "received_at": "2026-06-29T00:00:00Z",
            "capability": "button_event",
            "event": "single_press",
            "payload": {"button": "left"},
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
    assert set(result.body) == {"schema_version", "data", "warnings", "errors"}
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {
        "event_id": "evt_fixed",
        "device_id": "device_abc123",
        "action": "single_left",
        "received_at": "2026-06-29T00:00:00Z",
        "capability": "button_event",
        "event": "single_press",
        "payload": {"button": "left"},
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
    """Accepted device event full response matches the API vNext envelope contract."""
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
    assert first.body["data"]["event_id"] == "evt_first"
    assert second.status == 200
    assert second.body == {
        "schema_version": "2026.06",
        "data": {
            "event_id": "evt_first",
            "device_id": "device_abc123",
            "action": "single_left",
            "received_at": "2026-06-29T00:00:00Z",
            "capability": "button_event",
            "event": "single_press",
            "payload": {"button": "left"},
            "status": "duplicate",
            "duplicate": True,
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
    assert result.body["data"]["automations"] == [
        {
            "rule_id": "rule-left-single",
            "action_index": 0,
            "type": "device_command",
            "command_id": "cmd-auto",
            "status": "completed",
            "response_status": 200,
        }
    ]


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
    assert set(duplicate.body) == {"schema_version", "data", "warnings", "errors"}
    assert duplicate.body["schema_version"] == "2026.06"
    assert duplicate.body["warnings"] == []
    assert duplicate.body["errors"] == []
    assert duplicate.body["data"] == {
        "event_id": "evt_first",
        "device_id": "device_abc123",
        "action": "single_left",
        "received_at": "2026-06-29T00:00:00Z",
        "capability": "button_event",
        "event": "single_press",
        "payload": {"button": "left"},
        "status": "duplicate",
        "duplicate": True,
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
    """Duplicate device event full response matches the API vNext envelope contract."""
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
    assert result.body["data"]["capability"] == "button_event"
    assert result.body["data"]["event"] == "rotate_left"
    assert result.body["data"]["payload"] == {"direction": "left"}
    assert result.body["data"]["events"] == [
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
    assert result.body["data"]["event"] == "single_press"
    assert result.body["data"]["payload"] == {"button": expected_button}
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
    assert set(result.body) == {"schema_version", "data", "warnings", "errors"}
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
    """Device event error full response matches the API vNext envelope contract."""
    fixture_path = Path(__file__).parent / "fixtures" / "api-vnext" / "device-event-error.json"
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
