"""Tests for Home Assistant diagnostic adapters."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.smartly_bridge.adapters.home_assistant import (
    HomeAssistantRawDiagnosticStore,
    _home_assistant_raw_diagnostic_store,
)
from custom_components.smartly_bridge.const import DOMAIN
from custom_components.smartly_bridge.domain.models import BridgeResponse


class FakeRawDiagnosticFetchUseCase:
    """Raw diagnostic use case used to verify invocation factory wiring."""

    def __init__(self) -> None:
        self.refs: list[str] = []

    def execute(self, raw_ref: str) -> BridgeResponse:
        """Record invocation and return a fixed response."""
        self.refs.append(raw_ref)
        return BridgeResponse(
            {
                "success": True,
                "raw_ref": raw_ref,
                "data": {"raw_ref": raw_ref},
            },
            status=200,
        )


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


def test_home_assistant_raw_diagnostic_store_factory_builds_legacy_store() -> None:
    """Home Assistant raw diagnostic store factory preserves the legacy store type."""
    hass = MagicMock()
    hass.data = {DOMAIN: {}}

    store = _home_assistant_raw_diagnostic_store(hass)

    assert isinstance(store, HomeAssistantRawDiagnosticStore)


def test_fetch_raw_diagnostic_uses_injected_use_case_factory() -> None:
    """Raw diagnostic invocation adapter accepts an injected use-case factory."""
    from custom_components.smartly_bridge.views.diagnostics import _fetch_raw_diagnostic

    store = MagicMock()
    use_case = FakeRawDiagnosticFetchUseCase()
    factory_calls = []

    def use_case_factory(received_store):
        factory_calls.append(received_store)
        return use_case

    result = _fetch_raw_diagnostic(
        store,
        raw_ref="raw_light_001",
        use_case_factory=use_case_factory,
    )

    assert result.status == 200
    assert factory_calls == [store]
    assert use_case.refs == ["raw_light_001"]
    assert result.body["raw_ref"] == "raw_light_001"
