"""Tests for Home Assistant diagnostic adapters."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.smartly_bridge.adapters.home_assistant import (
    HomeAssistantRawDiagnosticStore,
)
from custom_components.smartly_bridge.const import DOMAIN


def test_raw_diagnostic_store_expires_payloads_after_ttl() -> None:
    """Raw diagnostic payloads expire and are removed from runtime storage."""
    now = 1_000.0

    def now_fn() -> float:
        return now

    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    store = HomeAssistantRawDiagnosticStore(hass, ttl_seconds=10, now_fn=now_fn)

    store.record_raw_diagnostic("raw_camera_porch", {"entity_id": "camera.porch"})

    assert store.get_raw_diagnostic("raw_camera_porch") == {"entity_id": "camera.porch"}

    now = 1_011.0

    assert store.get_raw_diagnostic("raw_camera_porch") is None
    assert "raw_camera_porch" not in hass.data[DOMAIN]["raw_diagnostics"]
