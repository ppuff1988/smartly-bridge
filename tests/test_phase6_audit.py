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
