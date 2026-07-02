"""Tests for the Phase 6 legacy cleanup audit helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_phase6_audit():
    spec = importlib.util.spec_from_file_location(
        "phase6_audit",
        PROJECT_ROOT / "scripts" / "phase6_audit.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_phase6_audit_passes_current_repo() -> None:
    """The checked-in Bridge code satisfies the code-verifiable Phase 6 gates."""
    audit = _load_phase6_audit()

    findings = audit.audit(PROJECT_ROOT)

    assert findings == []


def test_phase6_audit_detects_legacy_states_alias(tmp_path: Path) -> None:
    """The audit rejects reintroducing the expired states alias."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "custom_components/smartly_bridge/const.py",
        'API_PATH_STATES = "/api/smartly/states"\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "legacy-states-alias" for finding in findings)


def test_phase6_audit_detects_legacy_top_level_response_dict(tmp_path: Path) -> None:
    """The audit rejects production dict literals that rebuild legacy response bodies."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "custom_components/smartly_bridge/application/example.py",
        "def response():\n"
        "    return BridgeResponse({\n"
        "        'success': True,\n"
        "        'message': 'ok',\n"
        "    })\n",
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "legacy-top-level-response" for finding in findings)


def test_phase6_audit_allows_vnext_data_and_errors(tmp_path: Path) -> None:
    """The audit allows legacy-looking names inside vNext data/errors payloads."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "custom_components/smartly_bridge/application/example.py",
        "def response():\n"
        "    return BridgeResponse({\n"
        "        'schema_version': '2026.06',\n"
        "        'data': {'status': 'accepted', 'count': 1},\n"
        "        'warnings': [],\n"
        "        'errors': [{'message': 'invalid'}],\n"
        "    })\n",
    )

    findings = audit.audit(tmp_path)

    assert findings == []


def test_phase6_audit_detects_request_time_fallback_constructor(tmp_path: Path) -> None:
    """The audit rejects view-level request-time fallback adapter construction."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "custom_components/smartly_bridge/views/example.py",
        "def build(hass):\n"
        "    return HomeAssistantHistoryGateway(hass)\n",
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "request-time-fallback-constructor" for finding in findings)


def test_phase6_audit_detects_legacy_http_reexport_module(tmp_path: Path) -> None:
    """The audit rejects the Phase 6 legacy HTTP re-export module."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "custom_components/smartly_bridge/http.py",
        "from .views import register_views\n",
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "legacy-http-reexport-module" for finding in findings)


def test_phase6_audit_detects_manual_legacy_control_body(tmp_path: Path) -> None:
    """The audit rejects manual scripts that still demonstrate legacy control bodies."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "scripts/manual_tests/test_smartly_api.py",
        "body = {\n"
        '    "entity_id": entity_id,\n'
        '    "action": action,\n'
        '    "service_data": service_data,\n'
        "}\n",
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "manual-legacy-control-body" for finding in findings)


def test_phase6_audit_detects_camera_legacy_wording(tmp_path: Path) -> None:
    """The audit rejects camera path wording that still labels runtime behavior legacy."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "custom_components/smartly_bridge/views/camera.py",
        '"""Camera gateway resolver uses setup runtime gateway before legacy manager."""\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "camera-legacy-wording" for finding in findings)


def test_phase6_audit_detects_device_event_legacy_wording(tmp_path: Path) -> None:
    """The audit rejects device-event wording that still labels source behavior legacy."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "custom_components/smartly_bridge/application/device_events.py",
        '"""Map legacy source button action to canonical Smartly event fields."""\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "device-event-legacy-wording" for finding in findings)


def test_phase6_audit_detects_logical_device_legacy_wording(tmp_path: Path) -> None:
    """The audit rejects logical-device wording that still labels source data legacy."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "custom_components/smartly_bridge/application/logical_devices.py",
        '"""Return the canonical capability name for a legacy capability."""\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "logical-device-legacy-wording" for finding in findings)


def test_phase6_audit_detects_control_application_legacy_wording(
    tmp_path: Path,
) -> None:
    """The audit rejects control application wording that still labels vNext data legacy."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "custom_components/smartly_bridge/application/control.py",
        '"""Return API vNext command data without requiring legacy top-level fields."""\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "control-application-legacy-wording" for finding in findings)


def test_phase6_audit_detects_production_legacy_wording(tmp_path: Path) -> None:
    """The audit rejects generic legacy wording in production Bridge modules."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "custom_components/smartly_bridge/application/example.py",
        '"""Temporary legacy compatibility helper."""\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "production-legacy-wording" for finding in findings)


def test_phase6_audit_detects_api_vnext_fixture_legacy_top_level_key(
    tmp_path: Path,
) -> None:
    """The audit rejects API vNext fixtures with legacy top-level fields."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "tests/fixtures/api-vnext/control.json",
        "{\n"
        '  "schema_version": "2026.06",\n'
        '  "data": {},\n'
        '  "warnings": [],\n'
        '  "errors": [],\n'
        '  "success": true\n'
        "}\n",
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "api-vnext-fixture-top-level" for finding in findings)


def test_phase6_audit_detects_raw_payload_in_sync_fixture(tmp_path: Path) -> None:
    """The audit rejects raw payloads in sync/current-sync fixtures."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "tests/fixtures/current-sync/states-vnext-data.json",
        "{\n"
        '  "logical_devices": [\n'
        '    {"id": "ldev_1", "raw_payload": {"secret": "value"}}\n'
        "  ]\n"
        "}\n",
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "sync-fixture-raw-payload" for finding in findings)


def test_phase6_audit_detects_api_vnext_fixture_data_success_flag(
    tmp_path: Path,
) -> None:
    """The audit rejects legacy success flags inside API vNext fixture data."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "tests/fixtures/api-vnext/camera-config-register.json",
        "{\n"
        '  "schema_version": "2026.06",\n'
        '  "data": {"success": true, "action": "registered"},\n'
        '  "warnings": [],\n'
        '  "errors": []\n'
        "}\n",
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "api-vnext-fixture-data-success" for finding in findings)
