#!/usr/bin/env python3
"""Check Phase 6 API vNext release evidence readiness."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import NamedTuple


DEFAULT_EVIDENCE_PATH = Path("docs/specs/phase6-release-evidence.md")
REQUIRED_COLUMNS = ("Gate", "Owner", "Evidence source", "Decision", "Notes")
SIGNOFF_COLUMNS = ("Date", "Gate", "Reviewer", "Decision", "Evidence link")
REQUIRED_GATES = (
    "Active Platform clients support API vNext",
    "Retired endpoint usage below removal threshold",
    "Alias window announced and elapsed",
    "Rollback playbook verified",
    "Platform render source audit completed",
    "API support policy decided",
)
INCOMPLETE_MARKERS = {"", "tbd", "pending", "n/a"}
READY_DECISIONS = {"ready", "accepted", "approved", "complete", "completed", "passed"}


class GateStatus(NamedTuple):
    """Release evidence status for one Phase 6 gate."""

    gate: str
    owner: str
    evidence_source: str
    decision: str
    notes: str
    ready: bool


class Signoff(NamedTuple):
    """Reviewer sign-off for one Phase 6 release gate."""

    date: str
    gate: str
    reviewer: str
    decision: str
    evidence_link: str
    ready: bool


def load_statuses(path: Path | str = DEFAULT_EVIDENCE_PATH) -> list[GateStatus]:
    """Load Phase 6 release gate statuses from the evidence Markdown table."""
    evidence_path = Path(path)
    lines = evidence_path.read_text(encoding="utf-8").splitlines()
    rows = _status_table_rows(lines)
    return [_status_from_row(row) for row in rows]


def load_signoffs(path: Path | str = DEFAULT_EVIDENCE_PATH) -> list[Signoff]:
    """Load Phase 6 release gate sign-off rows from the evidence Markdown file."""
    evidence_path = Path(path)
    lines = evidence_path.read_text(encoding="utf-8").splitlines()
    rows = _signoff_table_rows(lines)
    return [_signoff_from_row(row) for row in rows]


def missing_required_gates(statuses: list[GateStatus]) -> list[str]:
    """Return required Phase 6 release gates missing from the evidence table."""
    present_gates = {status.gate for status in statuses}
    return [gate for gate in REQUIRED_GATES if gate not in present_gates]


def duplicate_status_gates(statuses: list[GateStatus]) -> list[str]:
    """Return gate names that appear more than once in the status table."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for status in statuses:
        if status.gate in seen and status.gate not in duplicates:
            duplicates.append(status.gate)
        seen.add(status.gate)
    return duplicates


def duplicate_signoff_evidence(signoffs: list[Signoff]) -> list[str]:
    """Return sign-off gate/evidence pairs that appear more than once."""
    seen: set[tuple[str, str]] = set()
    duplicates: list[str] = []
    for signoff in signoffs:
        key = (signoff.gate, signoff.evidence_link)
        label = f"{signoff.gate} ({signoff.evidence_link})"
        if key in seen and label not in duplicates:
            duplicates.append(label)
        seen.add(key)
    return duplicates


def missing_ready_gate_signoffs(
    statuses: list[GateStatus],
    signoffs: list[Signoff],
) -> list[str]:
    """Return ready gates that do not have a completed sign-off row."""
    signed_off_evidence = {
        (signoff.gate, signoff.evidence_link) for signoff in signoffs if signoff.ready
    }
    return [
        status.gate
        for status in statuses
        if status.ready
        and status.gate in REQUIRED_GATES
        and (status.gate, status.evidence_source) not in signed_off_evidence
    ]


def _status_table_rows(lines: list[str]) -> list[dict[str, str]]:
    header_index = _status_table_header_index(lines)
    if header_index is None:
        raise ValueError("Phase 6 release evidence status table was not found.")

    headers = _split_markdown_row(lines[header_index])
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing_columns:
        raise ValueError(
            "Phase 6 release evidence table is missing columns: "
            + ", ".join(missing_columns)
        )

    rows: list[dict[str, str]] = []
    for line in lines[header_index + 2 :]:
        if not line.startswith("|"):
            break
        values = _split_markdown_row(line)
        if len(values) != len(headers):
            continue
        rows.append(dict(zip(headers, values, strict=True)))
    return rows


def _signoff_table_rows(lines: list[str]) -> list[dict[str, str]]:
    header_index = _signoff_table_header_index(lines)
    if header_index is None:
        return []

    headers = _split_markdown_row(lines[header_index])
    missing_columns = [column for column in SIGNOFF_COLUMNS if column not in headers]
    if missing_columns:
        raise ValueError(
            "Phase 6 release sign-off table is missing columns: "
            + ", ".join(missing_columns)
        )

    rows: list[dict[str, str]] = []
    for line in lines[header_index + 2 :]:
        if not line.startswith("|"):
            break
        values = _split_markdown_row(line)
        if len(values) != len(headers):
            continue
        rows.append(dict(zip(headers, values, strict=True)))
    return rows


def _status_table_header_index(lines: list[str]) -> int | None:
    expected_header = "| Gate | Owner | Evidence source | Decision | Notes |"
    for index, line in enumerate(lines):
        if line.strip() == expected_header:
            return index
    return None


def _signoff_table_header_index(lines: list[str]) -> int | None:
    expected_header = "| Date | Gate | Reviewer | Decision | Evidence link |"
    for index, line in enumerate(lines):
        if line.strip() == expected_header:
            return index
    return None


def _split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _status_from_row(row: dict[str, str]) -> GateStatus:
    gate = row["Gate"]
    owner = row["Owner"]
    evidence_source = row["Evidence source"]
    decision = row["Decision"]
    notes = row["Notes"]
    ready = (
        _is_complete(owner)
        and _is_complete(evidence_source)
        and _is_ready_decision(decision)
    )
    return GateStatus(
        gate=gate,
        owner=owner,
        evidence_source=evidence_source,
        decision=decision,
        notes=notes,
        ready=ready,
    )


def _signoff_from_row(row: dict[str, str]) -> Signoff:
    date = row["Date"]
    gate = row["Gate"]
    reviewer = row["Reviewer"]
    decision = row["Decision"]
    evidence_link = row["Evidence link"]
    ready = (
        _is_complete(date)
        and _is_iso_date(date)
        and _is_complete(gate)
        and _is_complete(reviewer)
        and _is_complete(evidence_link)
        and _is_ready_decision(decision)
    )
    return Signoff(
        date=date,
        gate=gate,
        reviewer=reviewer,
        decision=decision,
        evidence_link=evidence_link,
        ready=ready,
    )


def _is_complete(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in INCOMPLETE_MARKERS:
        return False
    return not re.search(r"\b(tbd|pending|n/a)\b", normalized)


def _is_iso_date(value: str) -> bool:
    candidate = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate) is None:
        return False
    try:
        date.fromisoformat(candidate)
    except ValueError:
        return False
    return True


def _is_ready_decision(value: str) -> bool:
    return value.strip().lower() in READY_DECISIONS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check Phase 6 API vNext release evidence readiness."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=str(DEFAULT_EVIDENCE_PATH),
        help="Path to phase6-release-evidence.md.",
    )
    parser.add_argument(
        "--allow-pending",
        action="store_true",
        help="Print pending gates but return success.",
    )
    args = parser.parse_args(argv)

    statuses = load_statuses(args.path)
    signoffs = load_signoffs(args.path)
    missing = missing_required_gates(statuses)
    duplicates = duplicate_status_gates(statuses)
    duplicate_signoffs = duplicate_signoff_evidence(signoffs)
    missing_signoffs = missing_ready_gate_signoffs(statuses, signoffs)
    pending = [status for status in statuses if not status.ready]
    if (
        not missing
        and not duplicates
        and not duplicate_signoffs
        and not missing_signoffs
        and not pending
    ):
        print("Phase 6 release evidence ready.")
        return 0

    print("Phase 6 release evidence has pending gates:")
    for gate in missing:
        print(f"- {gate}: missing required evidence row")
    for gate in duplicates:
        print(f"- {gate}: duplicate evidence rows")
    for signoff in duplicate_signoffs:
        print(f"- {signoff}: duplicate sign-off rows")
    for gate in missing_signoffs:
        print(f"- {gate}: missing completed sign-off row for gate evidence")
    for status in pending:
        print(
            f"- {status.gate}: owner={status.owner}; "
            f"evidence={status.evidence_source}; decision={status.decision}"
        )
    return 0 if args.allow_pending else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
