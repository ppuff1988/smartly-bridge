"""Raw diagnostic application use cases."""

from __future__ import annotations

import ipaddress
from typing import Any

from ..domain.models import BridgeResponse
from .ports import RawDiagnosticStorePort

SMARTLY_API_SCHEMA_VERSION = "2026.06"
REDACTED = "<redacted>"

_SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "credential",
    "api_key",
    "apikey",
)


class RawDiagnosticFetchUseCase:
    """Fetch raw diagnostic payloads through a storage port."""

    def __init__(self, store: RawDiagnosticStorePort) -> None:
        self._store = store

    def execute(self, raw_ref: str) -> BridgeResponse:
        """Return a raw diagnostic payload."""
        payload = self._store.get_raw_diagnostic(raw_ref)
        if payload is None:
            return BridgeResponse(
                {
                    "success": False,
                    "schema_version": SMARTLY_API_SCHEMA_VERSION,
                    "raw_ref": raw_ref,
                    "error": "raw_diagnostic_not_found",
                    "data": {"raw_ref": raw_ref, "status": "not_found"},
                    "warnings": [],
                    "errors": [
                        {
                            "code": "RAW_DIAGNOSTIC_NOT_FOUND",
                            "message": (
                                "Raw diagnostic payload was not found or has expired."
                            ),
                            "target": "raw_ref",
                            "retryable": False,
                        }
                    ],
                },
                status=404,
            )
        masked_payload = _mask_sensitive_payload(payload)
        return BridgeResponse(
            {
                "success": True,
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "raw_ref": raw_ref,
                "data": {
                    "raw_ref": raw_ref,
                    "payload": masked_payload,
                },
                "warnings": [],
                "errors": [],
            },
            status=200,
        )


def _mask_sensitive_payload(payload: Any) -> Any:
    """Return a diagnostic payload with sensitive values redacted."""
    if isinstance(payload, dict):
        return {
            key: REDACTED if _is_sensitive_key(key) else _mask_sensitive_payload(value)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [_mask_sensitive_payload(value) for value in payload]
    if isinstance(payload, str) and _is_ip_address(payload):
        return REDACTED
    return payload


def _is_sensitive_key(key: object) -> bool:
    """Return whether a diagnostic key should always be redacted."""
    normalized = str(key).lower()
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _is_ip_address(value: str) -> bool:
    """Return whether a string is an IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True
