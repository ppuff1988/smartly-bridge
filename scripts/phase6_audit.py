#!/usr/bin/env python3
"""Audit code-verifiable Phase 6 legacy cleanup gates."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple


LEGACY_STATES_ALIAS = "/api/smartly/states"
LEGACY_TOP_LEVEL_KEYS = {
    "error",
    "success",
    "status",
    "message",
    "states",
    "count",
    "rules",
    "rule_id",
    "rule",
    "entity_id",
    "action",
    "token",
    "session_id",
    "history",
    "statistics",
    "snapshot",
    "raw_ref",
}
FALLBACK_CONSTRUCTORS = {
    "HomeAssistantCameraGateway",
    "HomeAssistantHistoryGateway",
    "HomeAssistantLocalAutomationRuleStore",
    "HomeAssistantRawDiagnosticStore",
    "HomeAssistantSmartlyCommandExecutor",
    "HomeAssistantStateSyncGateway",
    "HomeAssistantSyncGateway",
    "HomeAssistantWebRTCGateway",
    "HomeAssistantDeviceEventPublisher",
    "InMemoryDeviceEventDeduplicator",
}
RESPONSE_BUILDERS = {"BridgeResponse", "_json_response"}
API_VNEXT_TOP_LEVEL_KEYS = {"schema_version", "data", "warnings", "errors"}
GENERAL_LEGACY_WORDING_ROOTS = [
    Path("custom_components"),
    Path("tests"),
    Path("docs"),
    Path("scripts"),
]
GENERAL_LEGACY_WORDING_EXCLUDED_PATHS = {
    Path("docs/specs/migration-progress.md"),
    Path("scripts/phase6_audit.py"),
    Path("tests/test_phase6_audit.py"),
}
GENERAL_LEGACY_WORDING_TERMS = (
    "legacy",
    "deprecated",
    "backward compatibility",
    "LTS",
)
ACTIVE_CONTRACT_DOCS = [
    Path("docs/openapi.yaml"),
    Path("docs/specs/api-vnext-contract.md"),
    Path("docs/specs/device-abstraction.md"),
]
ACTIVE_CONTRACT_LEGACY_TERMS = (
    "legacy",
    "deprecated",
    "backward compatibility",
    "backward compatible",
)
MIGRATION_PLAN_DOCS = [
    Path("docs/specs/migration-plan.md"),
]
MIGRATION_PLAN_LEGACY_TERMS = (
    "legacy",
    "deprecated",
    "backward compatibility",
    "LTS",
)
CONTROL_TEST_LEGACY_WORDING_PATHS = [
    Path("tests/test_http.py"),
    Path("tests/test_application_hexagonal.py"),
    Path("tests/test_application_local_automation.py"),
]
APPLICATION_TEST_LEGACY_WORDING_PATHS = [
    Path("tests/test_application_device_events.py"),
    Path("tests/test_application_history.py"),
]
APPLICATION_TEST_TOP_LEVEL_ERROR_PATHS = [
    Path("tests/test_application_hexagonal.py"),
]
HISTORY_VIEW_TEST_TOP_LEVEL_SUCCESS_PATHS = [
    Path("tests/test_history_views.py"),
]
WEBRTC_TEST_TOP_LEVEL_SUCCESS_PATHS = [
    Path("tests/test_webrtc.py"),
]
REQUEST_TIME_FALLBACK_WORDING_PATHS = [
    Path("tests/test_http.py"),
    Path("tests/test_sync_views.py"),
    Path("tests/test_device_events.py"),
    Path("tests/test_history_views.py"),
    Path("tests/test_camera_views.py"),
    Path("tests/test_webrtc.py"),
    Path("tests/test_local_automation_rules.py"),
    Path("tests/test_push.py"),
]
PUBLIC_CONTROL_DOCS = [
    Path("README.md"),
    Path("docs/README.md"),
    Path("docs/control/README.md"),
    Path("docs/control/api-basics.md"),
    Path("docs/control/code-examples.md"),
    Path("docs/control/device-types.md"),
    Path("docs/control/responses.md"),
    Path("docs/control/troubleshooting.md"),
    Path("docs/security-audit.md"),
]
PUBLIC_CONTROL_LEGACY_BODY_TERMS = (
    "service_data",
    "ControlRequest",
    "ControlResponse",
)
HISTORY_DOCS = [
    Path("docs/history-api.md"),
]
CAMERA_DOCS = [
    Path("docs/camera-api.md"),
]
SYNC_DOCS = [
    Path("docs/sync-api.md"),
]
TRUST_PROXY_DOCS = [
    Path("docs/development/trust-proxy.md"),
]
ARCHITECTURE_PLAN_DOCS = [
    Path("docs/smartly_bridge_architecture_plan.md"),
]


class Finding(NamedTuple):
    """A Phase 6 audit finding."""

    code: str
    path: str
    line: int
    message: str


def audit(root: Path | str = ".") -> list[Finding]:
    """Return Phase 6 code-verifiable legacy cleanup findings."""
    root_path = Path(root)
    package_root = root_path / "custom_components" / "smartly_bridge"

    findings: list[Finding] = []
    if package_root.exists():
        python_files = sorted(package_root.rglob("*.py"))
        findings.extend(_legacy_http_reexport_findings(root_path, package_root))
        findings.extend(_legacy_states_alias_findings(root_path, python_files))
        findings.extend(_legacy_top_level_response_findings(root_path, python_files))
        findings.extend(_request_time_fallback_constructor_findings(root_path, package_root))
        findings.extend(_production_legacy_wording_findings(root_path, python_files))
    findings.extend(_api_vnext_fixture_findings(root_path))
    findings.extend(_sync_raw_payload_fixture_findings(root_path))
    findings.extend(_general_legacy_wording_findings(root_path))
    findings.extend(_manual_legacy_control_body_findings(root_path))
    findings.extend(_camera_legacy_wording_findings(root_path))
    findings.extend(_device_event_legacy_wording_findings(root_path))
    findings.extend(_logical_device_legacy_wording_findings(root_path))
    findings.extend(_control_application_legacy_wording_findings(root_path))
    findings.extend(_active_contract_legacy_wording_findings(root_path))
    findings.extend(_migration_plan_legacy_wording_findings(root_path))
    findings.extend(_control_test_legacy_wording_findings(root_path))
    findings.extend(_application_test_legacy_wording_findings(root_path))
    findings.extend(_application_test_top_level_error_findings(root_path))
    findings.extend(_history_view_test_top_level_success_findings(root_path))
    findings.extend(_webrtc_test_top_level_success_findings(root_path))
    findings.extend(_request_time_fallback_wording_findings(root_path))
    findings.extend(_openapi_legacy_control_body_findings(root_path))
    findings.extend(_public_control_legacy_body_doc_findings(root_path))
    findings.extend(_history_doc_top_level_error_findings(root_path))
    findings.extend(_camera_doc_top_level_error_findings(root_path))
    findings.extend(_camera_doc_top_level_success_findings(root_path))
    findings.extend(_sync_doc_top_level_error_findings(root_path))
    findings.extend(_trust_proxy_doc_top_level_error_findings(root_path))
    findings.extend(_architecture_plan_doc_top_level_error_findings(root_path))
    return findings


def _legacy_http_reexport_findings(root: Path, package_root: Path) -> list[Finding]:
    path = package_root / "http.py"
    if not path.exists():
        return []
    return [
        Finding(
            code="legacy-http-reexport-module",
            path=_relative_path(root, path),
            line=1,
            message="Legacy HTTP re-export module is present; import views.register_views directly.",
        )
    ]


def _legacy_states_alias_findings(root: Path, python_files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in python_files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if LEGACY_STATES_ALIAS in line:
                findings.append(
                    Finding(
                        code="legacy-states-alias",
                        path=_relative_path(root, path),
                        line=line_number,
                        message=f"Expired states alias is present: {LEGACY_STATES_ALIAS}",
                    )
                )
    return findings


def _legacy_top_level_response_findings(root: Path, python_files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in python_files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as err:
            findings.append(
                Finding(
                    code="python-parse-error",
                    path=_relative_path(root, path),
                    line=err.lineno or 1,
                    message=err.msg,
                )
            )
            continue
        body_assignments = _response_body_assignments(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _call_name(node.func) not in RESPONSE_BUILDERS:
                continue
            if not node.args:
                continue
            first_arg = node.args[0]
            body_node = first_arg
            if isinstance(first_arg, ast.Name):
                body_node = body_assignments.get(first_arg.id, first_arg)
            if not isinstance(body_node, ast.Dict):
                continue
            keys = _legacy_keys_on_dict(body_node)
            if keys:
                findings.append(
                    Finding(
                        code="legacy-top-level-response",
                        path=_relative_path(root, path),
                        line=body_node.lineno,
                        message=(
                            "Response body rebuilds legacy top-level keys: "
                            + ", ".join(sorted(keys))
                        ),
                    )
                )
    return findings


def _request_time_fallback_constructor_findings(root: Path, package_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    scan_roots = [package_root / "views", package_root / "push.py"]
    for path in _python_files_from_paths(scan_roots):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as err:
            findings.append(
                Finding(
                    code="python-parse-error",
                    path=_relative_path(root, path),
                    line=err.lineno or 1,
                    message=err.msg,
                )
            )
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func)
            if name not in FALLBACK_CONSTRUCTORS:
                continue
            findings.append(
                Finding(
                    code="request-time-fallback-constructor",
                    path=_relative_path(root, path),
                    line=node.lineno,
                    message=f"View/runtime path constructs fallback adapter: {name}",
                )
            )
    return findings


def _api_vnext_fixture_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    fixture_root = root / "tests" / "fixtures" / "api-vnext"
    if not fixture_root.exists():
        return findings
    for path in sorted(fixture_root.rglob("*.json")):
        parsed = _load_json_finding(path, root, findings)
        if not isinstance(parsed, dict):
            continue
        extra_keys = set(parsed) - API_VNEXT_TOP_LEVEL_KEYS
        if extra_keys:
            findings.append(
                Finding(
                    code="api-vnext-fixture-top-level",
                    path=_relative_path(root, path),
                    line=1,
                    message=(
                        "API vNext fixture has legacy/unknown top-level keys: "
                        + ", ".join(sorted(extra_keys))
                    ),
                )
            )
        data = parsed.get("data")
        if isinstance(data, dict) and isinstance(data.get("success"), bool):
            findings.append(
                Finding(
                    code="api-vnext-fixture-data-success",
                    path=_relative_path(root, path),
                    line=1,
                    message="API vNext fixture data uses legacy success flag; use status.",
                )
            )
    return findings


def _sync_raw_payload_fixture_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    fixture_roots = [
        root / "tests" / "fixtures" / "current-sync",
        root / "tests" / "fixtures" / "api-vnext",
    ]
    for path in _json_files_from_paths(fixture_roots):
        parsed = _load_json_finding(path, root, findings)
        if parsed is None:
            continue
        if _contains_key(parsed, "raw_payload"):
            findings.append(
                Finding(
                    code="sync-fixture-raw-payload",
                    path=_relative_path(root, path),
                    line=1,
                    message="Sync/API fixture contains raw_payload; use raw_refs instead.",
                )
            )
    return findings


def _manual_legacy_control_body_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    manual_root = root / "scripts" / "manual_tests"
    for path in _python_files_from_paths([manual_root]):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as err:
            findings.append(
                Finding(
                    code="python-parse-error",
                    path=_relative_path(root, path),
                    line=err.lineno or 1,
                    message=err.msg,
                )
            )
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            keys = _string_keys_on_dict(node)
            if {"entity_id", "action", "service_data"}.issubset(keys):
                findings.append(
                    Finding(
                        code="manual-legacy-control-body",
                        path=_relative_path(root, path),
                        line=node.lineno,
                        message=(
                            "Manual control script uses legacy entity_id/action body; "
                            "use API vNext SmartlyCommand."
                        ),
                    )
                )
    return findings


def _camera_legacy_wording_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    paths = [
        root / "custom_components" / "smartly_bridge" / "views" / "camera.py",
        root / "tests" / "test_camera_views.py",
    ]
    for path in paths:
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if "legacy" not in line.lower():
                continue
            findings.append(
                Finding(
                    code="camera-legacy-wording",
                    path=_relative_path(root, path),
                    line=line_number,
                    message="Camera path wording still labels retained behavior as legacy.",
                )
            )
    return findings


def _device_event_legacy_wording_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    paths = [
        root / "custom_components" / "smartly_bridge" / "application" / "device_events.py",
        root / "tests" / "test_device_events.py",
    ]
    for path in paths:
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if "legacy" not in line.lower():
                continue
            findings.append(
                Finding(
                    code="device-event-legacy-wording",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "Device-event path wording still labels source/runtime "
                        "behavior as legacy."
                    ),
                )
            )
    return findings


def _logical_device_legacy_wording_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    paths = [
        root / "custom_components" / "smartly_bridge" / "application" / "logical_devices.py",
        root / "tests" / "test_application_logical_devices.py",
    ]
    for path in paths:
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if "legacy" not in line.lower():
                continue
            findings.append(
                Finding(
                    code="logical-device-legacy-wording",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "Logical-device path wording still labels source/canonical "
                        "normalization behavior as legacy."
                    ),
                )
            )
    return findings


def _control_application_legacy_wording_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    path = root / "custom_components" / "smartly_bridge" / "application" / "control.py"
    if not path.exists():
        return findings
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return findings
    for line_number, line in enumerate(lines, start=1):
        if "legacy" not in line.lower():
            continue
        findings.append(
            Finding(
                code="control-application-legacy-wording",
                path=_relative_path(root, path),
                line=line_number,
                message=(
                    "Control application wording still labels API vNext "
                    "command data as legacy-related."
                ),
            )
        )
    return findings


def _production_legacy_wording_findings(
    root: Path,
    python_files: list[Path],
) -> list[Finding]:
    findings: list[Finding] = []
    for path in python_files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if "legacy" not in line.lower():
                continue
            findings.append(
                Finding(
                    code="production-legacy-wording",
                    path=_relative_path(root, path),
                    line=line_number,
                    message="Production Bridge code still contains legacy wording.",
                )
            )
    return findings


def _general_legacy_wording_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for scan_root in GENERAL_LEGACY_WORDING_ROOTS:
        path = root / scan_root
        if not path.exists():
            continue
        files = (
            [path]
            if path.is_file()
            else sorted(p for p in path.rglob("*") if p.is_file())
        )
        for file_path in files:
            relative_path = _relative_path(root, file_path)
            if Path(relative_path) in GENERAL_LEGACY_WORDING_EXCLUDED_PATHS:
                continue
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(lines, start=1):
                lower_line = line.lower()
                if not _contains_general_legacy_wording(line, lower_line):
                    continue
                findings.append(
                    Finding(
                        code="general-legacy-wording",
                        path=relative_path,
                        line=line_number,
                        message=(
                            "General repo content still uses Phase 6 legacy wording; "
                            "describe source/current behavior directly."
                        ),
                    )
                )
    return findings


def _contains_general_legacy_wording(line: str, lower_line: str) -> bool:
    for term in GENERAL_LEGACY_WORDING_TERMS:
        if term == "LTS":
            if re.search(r"\bLTS\b", line):
                return True
            continue
        if term.lower() in lower_line:
            return True
    return False


def _active_contract_legacy_wording_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in ACTIVE_CONTRACT_DOCS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            lower_line = line.lower()
            if not any(term in lower_line for term in ACTIVE_CONTRACT_LEGACY_TERMS):
                continue
            findings.append(
                Finding(
                    code="active-contract-legacy-wording",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "Active contract docs still use legacy/deprecated wording; "
                        "describe source aliases or non-cursor behavior directly."
                    ),
                )
            )
    return findings


def _migration_plan_legacy_wording_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in MIGRATION_PLAN_DOCS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            lower_line = line.lower()
            if not any(term.lower() in lower_line for term in MIGRATION_PLAN_LEGACY_TERMS):
                continue
            findings.append(
                Finding(
                    code="migration-plan-legacy-wording",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "Migration plan still uses legacy/deprecated/LTS wording; "
                        "describe API vNext release gates and source behavior directly."
                    ),
                )
            )
    return findings


def _control_test_legacy_wording_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in CONTROL_TEST_LEGACY_WORDING_PATHS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if "legacy" not in line.lower():
                continue
            findings.append(
                Finding(
                    code="control-test-legacy-wording",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "Control/command tests still use legacy wording; "
                        "describe removed body shapes or source behavior directly."
                    ),
                )
            )
    return findings


def _application_test_legacy_wording_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in APPLICATION_TEST_LEGACY_WORDING_PATHS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if "legacy" not in line.lower():
                continue
            findings.append(
                Finding(
                    code="application-test-legacy-wording",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "Application tests still use legacy wording; "
                        "describe source behavior or current API semantics directly."
                    ),
                )
            )
    return findings


def _application_test_top_level_error_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in APPLICATION_TEST_TOP_LEVEL_ERROR_PATHS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if '"error":' not in line and '{"error"' not in line:
                continue
            findings.append(
                Finding(
                    code="application-test-top-level-error",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "Application tests still inject top-level error fields; "
                        "use API vNext errors[]."
                    ),
                )
            )
    return findings


def _history_view_test_top_level_success_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in HISTORY_VIEW_TEST_TOP_LEVEL_SUCCESS_PATHS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if '"success":' not in line and '{"success"' not in line:
                continue
            findings.append(
                Finding(
                    code="history-view-test-top-level-success",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "History view tests still inject top-level success fields; "
                        "use API vNext data.status."
                    ),
                )
            )
    return findings


def _webrtc_test_top_level_success_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in WEBRTC_TEST_TOP_LEVEL_SUCCESS_PATHS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if '"success":' not in line and '{"success"' not in line:
                continue
            findings.append(
                Finding(
                    code="webrtc-test-top-level-success",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "WebRTC tests still inject top-level success fields; "
                        "use API vNext data.status."
                    ),
                )
            )
    return findings


def _request_time_fallback_wording_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in REQUEST_TIME_FALLBACK_WORDING_PATHS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            lower_line = line.lower()
            if "fallback" not in lower_line:
                continue
            if "request-time" not in lower_line and "resolver" not in lower_line:
                continue
            findings.append(
                Finding(
                    code="request-time-fallback-wording",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "Runtime resolver tests still describe request-time "
                        "adapter construction as fallback; use setup-created "
                        "runtime adapter wording."
                    ),
                )
            )
    return findings


def _openapi_legacy_control_body_findings(root: Path) -> list[Finding]:
    path = root / "docs" / "openapi.yaml"
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return []

    findings: list[Finding] = []
    legacy_patterns = (
        "ControlRequest:",
        "ControlResponse:",
        "#/components/schemas/ControlRequest",
        "#/components/schemas/ControlResponse",
        "required: [entity_id, action]",
        "Must include entity_id and action",
        "containing `entity_id`, `action`",
    )
    for line_number, line in enumerate(lines, start=1):
        if not any(pattern in line for pattern in legacy_patterns):
            continue
        findings.append(
            Finding(
                code="openapi-legacy-control-body",
                path=_relative_path(root, path),
                line=line_number,
                message=(
                    "OpenAPI control contract still describes entity_id/action "
                    "body; publish API vNext SmartlyCommand instead."
                ),
            )
        )
    return findings


def _public_control_legacy_body_doc_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in PUBLIC_CONTROL_DOCS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        findings.extend(_legacy_control_doc_line_findings(root, path, lines))
        findings.extend(_legacy_control_doc_block_findings(root, path, lines))
    return findings


def _legacy_control_doc_line_findings(
    root: Path,
    path: Path,
    lines: list[str],
) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(lines, start=1):
        if not any(term in line for term in PUBLIC_CONTROL_LEGACY_BODY_TERMS):
            continue
        findings.append(
            Finding(
                code="public-control-legacy-body-doc",
                path=_relative_path(root, path),
                line=line_number,
                message=(
                    "Public control docs still show legacy control body terms; "
                    "use API vNext SmartlyCommand."
                ),
            )
        )
    return findings


def _legacy_control_doc_block_findings(
    root: Path,
    path: Path,
    lines: list[str],
) -> list[Finding]:
    findings: list[Finding] = []
    in_fence = False
    fence_start = 1
    block_lines: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        if line.strip().startswith("```"):
            if not in_fence:
                in_fence = True
                fence_start = line_number
                block_lines = []
                continue
            block = "\n".join(block_lines)
            if _is_legacy_control_body_block(block):
                findings.append(
                    Finding(
                        code="public-control-legacy-body-doc",
                        path=_relative_path(root, path),
                        line=fence_start,
                        message=(
                            "Public control docs still show entity_id/action "
                            "body; use API vNext SmartlyCommand."
                        ),
                    )
                )
            in_fence = False
            block_lines = []
            continue
        if in_fence:
            block_lines.append(line)
    return findings


def _is_legacy_control_body_block(block: str) -> bool:
    has_entity_id = '"entity_id"' in block
    has_action = '"action"' in block or "service_data" in block
    reads_entity_id = 'body.get("entity_id")' in block or "body.get('entity_id')" in block
    reads_action = 'body.get("action")' in block or "body.get('action')" in block
    return (has_entity_id and has_action) or (reads_entity_id and reads_action)


def _history_doc_top_level_error_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in HISTORY_DOCS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if '"error"' not in line and '{"error"' not in line:
                continue
            findings.append(
                Finding(
                    code="history-doc-top-level-error",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "History docs still show top-level error bodies; "
                        "use API vNext errors[]."
                    ),
                )
            )
    return findings


def _camera_doc_top_level_error_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in CAMERA_DOCS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if '"error"' not in line and '{"error"' not in line:
                continue
            findings.append(
                Finding(
                    code="camera-doc-top-level-error",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "Camera docs still show top-level error bodies; "
                        "use API vNext errors[]."
                    ),
                )
            )
    return findings


def _camera_doc_top_level_success_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in CAMERA_DOCS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if '"success":' not in line and '{"success"' not in line:
                continue
            findings.append(
                Finding(
                    code="camera-doc-top-level-success",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "Camera docs still show top-level success bodies; "
                        "use API vNext data.status."
                    ),
                )
            )
    return findings


def _sync_doc_top_level_error_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in SYNC_DOCS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if '"error"' not in line and '{"error"' not in line:
                continue
            findings.append(
                Finding(
                    code="sync-doc-top-level-error",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "Sync docs still show top-level error bodies; "
                        "use API vNext errors[]."
                    ),
                )
            )
    return findings


def _trust_proxy_doc_top_level_error_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in TRUST_PROXY_DOCS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if '"error"' not in line and '{"error"' not in line:
                continue
            findings.append(
                Finding(
                    code="trust-proxy-doc-top-level-error",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "Trust-proxy docs still show top-level error bodies; "
                        "use API vNext errors[]."
                    ),
                )
            )
    return findings


def _architecture_plan_doc_top_level_error_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in ARCHITECTURE_PLAN_DOCS:
        path = root / relative_path
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if '"error"' not in line and '{"error"' not in line:
                continue
            findings.append(
                Finding(
                    code="architecture-plan-doc-top-level-error",
                    path=_relative_path(root, path),
                    line=line_number,
                    message=(
                        "Architecture plan still shows top-level error bodies; "
                        "use API vNext errors[]."
                    ),
                )
            )
    return findings


def _response_body_assignments(tree: ast.AST) -> dict[str, ast.Dict]:
    assignments: dict[str, ast.Dict] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                assignments[target.id] = node.value
    return assignments


def _legacy_keys_on_dict(node: ast.Dict) -> set[str]:
    return _string_keys_on_dict(node) & LEGACY_TOP_LEVEL_KEYS


def _string_keys_on_dict(node: ast.Dict) -> set[str]:
    keys: set[str] = set()
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
    return keys


def _load_json_finding(path: Path, root: Path, findings: list[Finding]) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        findings.append(
            Finding(
                code="json-parse-error",
                path=_relative_path(root, path),
                line=err.lineno,
                message=err.msg,
            )
        )
    return None


def _contains_key(value: object, key_name: str) -> bool:
    if isinstance(value, dict):
        if key_name in value:
            return True
        return any(_contains_key(item, key_name) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key_name) for item in value)
    return False


def _python_files_from_paths(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            files.append(path)
        elif path.is_dir():
            files.extend(path.rglob("*.py"))
    return sorted(files)


def _json_files_from_paths(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".json":
            files.append(path)
        elif path.is_dir():
            files.extend(path.rglob("*.json"))
    return sorted(files)


def _call_name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _relative_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    """Run the Phase 6 audit from the command line."""
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]) if args else Path(".")
    findings = audit(root)
    if findings:
        for finding in findings:
            print(f"{finding.path}:{finding.line}: {finding.code}: {finding.message}")
        return 1
    print("Phase 6 code audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
