"""Tests for raw diagnostic application use cases."""

from __future__ import annotations

from typing import Any

from custom_components.smartly_bridge.application.diagnostics import (
    RawDiagnosticFetchUseCase,
)


class FakeRawDiagnosticStore:
    """Fake raw diagnostic storage port."""

    def __init__(self, payloads: dict[str, dict[str, Any]]) -> None:
        self.payloads = payloads
        self.refs: list[str] = []

    def get_raw_diagnostic(self, raw_ref: str) -> dict[str, Any] | None:
        self.refs.append(raw_ref)
        return self.payloads.get(raw_ref)


def test_raw_diagnostic_fetch_masks_sensitive_payload() -> None:
    """Raw diagnostic fetch returns a masked API vNext envelope."""
    store = FakeRawDiagnosticStore(
        {
            "raw_light_001": {
                "entity_id": "light.kitchen",
                "access_token": "secret-token",
                "attributes": {
                    "password": "secret-password",
                    "host": "192.168.1.25",
                    "brightness": 128,
                },
            }
        }
    )

    result = RawDiagnosticFetchUseCase(store).execute("raw_light_001")

    assert result.status == 200
    assert store.refs == ["raw_light_001"]
    assert result.body == {
        "success": True,
        "schema_version": "2026.06",
        "raw_ref": "raw_light_001",
        "data": {
            "raw_ref": "raw_light_001",
            "payload": {
                "entity_id": "light.kitchen",
                "access_token": "<redacted>",
                "attributes": {
                    "password": "<redacted>",
                    "host": "<redacted>",
                    "brightness": 128,
                },
            },
        },
        "warnings": [],
        "errors": [],
    }


def test_raw_diagnostic_fetch_returns_not_found_for_missing_ref() -> None:
    """Missing or expired raw diagnostic refs return an API vNext error envelope."""
    store = FakeRawDiagnosticStore({})

    result = RawDiagnosticFetchUseCase(store).execute("raw_missing")

    assert result.status == 404
    assert store.refs == ["raw_missing"]
    assert result.body == {
        "success": False,
        "schema_version": "2026.06",
        "raw_ref": "raw_missing",
        "error": "raw_diagnostic_not_found",
        "data": {"raw_ref": "raw_missing", "status": "not_found"},
        "warnings": [],
        "errors": [
            {
                "code": "RAW_DIAGNOSTIC_NOT_FOUND",
                "message": "Raw diagnostic payload was not found or has expired.",
                "target": "raw_ref",
                "retryable": False,
            }
        ],
    }
