#!/usr/bin/env python3
"""Audit code-verifiable Phase 6 legacy cleanup gates."""

from __future__ import annotations

import ast
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
    if not package_root.exists():
        return []

    findings: list[Finding] = []
    python_files = sorted(package_root.rglob("*.py"))
    findings.extend(_legacy_states_alias_findings(root_path, python_files))
    findings.extend(_legacy_top_level_response_findings(root_path, python_files))
    findings.extend(_request_time_fallback_constructor_findings(root_path, package_root))
    return findings


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
    keys: set[str] = set()
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            if key.value in LEGACY_TOP_LEVEL_KEYS:
                keys.add(key.value)
    return keys


def _python_files_from_paths(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            files.append(path)
        elif path.is_dir():
            files.extend(path.rglob("*.py"))
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
