"""Tests for device event application use cases."""

from __future__ import annotations

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
        "event_id": "evt_fixed",
        "device_id": "device_abc123",
        "action": "single_left",
        "received_at": "2026-06-29T00:00:00Z",
        "capability": "button_event",
        "event": "single_press",
        "payload": {"button": "left"},
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
        }
    ]


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
    assert result.body == {"error": "invalid_action", "message": "Unsupported button action"}
    assert publisher.events == []
