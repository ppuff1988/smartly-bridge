"""Tests for Phase 6 release evidence status checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_phase6_release_evidence():
    spec = importlib.util.spec_from_file_location(
        "phase6_release_evidence",
        PROJECT_ROOT / "scripts" / "phase6_release_evidence.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_phase6_release_evidence_reports_pending_gates() -> None:
    """The checked-in evidence file reports pending external gates."""
    checker = _load_phase6_release_evidence()

    statuses = checker.load_statuses(
        PROJECT_ROOT / "docs/specs/phase6-release-evidence.md"
    )

    pending = [status for status in statuses if not status.ready]
    assert {status.gate for status in pending} == {
        "Active Platform clients support API vNext",
        "Retired endpoint usage below removal threshold",
        "Alias window announced and elapsed",
        "Rollback playbook verified",
        "Platform render source audit completed",
        "API support policy decided",
    }


def test_phase6_release_evidence_accepts_ready_gate_table(tmp_path: Path) -> None:
    """The checker accepts gates only when owner, evidence, and decision are set."""
    checker = _load_phase6_release_evidence()
    evidence_path = tmp_path / "phase6-release-evidence.md"
    _write(
        evidence_path,
        "\n".join(
            [
                "# Phase 6 API vNext Release Evidence",
                "",
                "| Gate | Owner | Evidence source | Decision | Notes |",
                "|---|---|---|---|---|",
                "| Active Platform clients support API vNext | Platform owner | release/client-matrix.md | Ready | All active clients checked. |",
                "| Retired endpoint usage below removal threshold | Data owner | release/telemetry.md | Ready | Usage is below threshold. |",
                "| Alias window announced and elapsed | Release owner | release/announcement.md | Ready | Window elapsed. |",
                "| Rollback playbook verified | Ops owner | runbooks/phase6.md | Ready | Dry run passed. |",
                "| Platform render source audit completed | Platform owner | platform/render-audit.md | Ready | Source audit passed. |",
                "| API support policy decided | Product owner | release/api-policy.md | Ready | Policy accepted. |",
                "",
            ]
        ),
    )

    statuses = checker.load_statuses(evidence_path)

    assert [status.gate for status in statuses] == [
        "Active Platform clients support API vNext",
        "Retired endpoint usage below removal threshold",
        "Alias window announced and elapsed",
        "Rollback playbook verified",
        "Platform render source audit completed",
        "API support policy decided",
    ]
    assert all(status.ready for status in statuses)


def test_phase6_release_evidence_reports_missing_required_gates(
    tmp_path: Path,
) -> None:
    """The checker rejects evidence tables that omit required release gates."""
    checker = _load_phase6_release_evidence()
    evidence_path = tmp_path / "phase6-release-evidence.md"
    _write(
        evidence_path,
        "\n".join(
            [
                "# Phase 6 API vNext Release Evidence",
                "",
                "| Gate | Owner | Evidence source | Decision | Notes |",
                "|---|---|---|---|---|",
                "| Active Platform clients support API vNext | Platform owner | release/client-matrix.md | Ready | All active clients checked. |",
                "",
            ]
        ),
    )

    missing = checker.missing_required_gates(checker.load_statuses(evidence_path))

    assert missing == [
        "Retired endpoint usage below removal threshold",
        "Alias window announced and elapsed",
        "Rollback playbook verified",
        "Platform render source audit completed",
        "API support policy decided",
    ]


def test_phase6_release_evidence_blocks_ready_gates_without_signoff(
    tmp_path: Path,
) -> None:
    """Strict release checks require sign-off rows for ready gates."""
    checker = _load_phase6_release_evidence()
    evidence_path = tmp_path / "phase6-release-evidence.md"
    _write(
        evidence_path,
        "\n".join(
            [
                "# Phase 6 API vNext Release Evidence",
                "",
                "| Gate | Owner | Evidence source | Decision | Notes |",
                "|---|---|---|---|---|",
                "| Active Platform clients support API vNext | Platform owner | release/client-matrix.md | Ready | All active clients checked. |",
                "| Retired endpoint usage below removal threshold | Data owner | release/telemetry.md | Ready | Usage is below threshold. |",
                "| Alias window announced and elapsed | Release owner | release/announcement.md | Ready | Window elapsed. |",
                "| Rollback playbook verified | Ops owner | runbooks/phase6.md | Ready | Dry run passed. |",
                "| Platform render source audit completed | Platform owner | platform/render-audit.md | Ready | Source audit passed. |",
                "| API support policy decided | Product owner | release/api-policy.md | Ready | Policy accepted. |",
                "",
                "## Sign-off Record",
                "",
                "| Date | Gate | Reviewer | Decision | Evidence link |",
                "|---|---|---|---|---|",
                "| TBD | TBD | TBD | Pending | TBD |",
                "",
            ]
        ),
    )

    assert checker.main([str(evidence_path)]) == 1


def test_phase6_release_evidence_blocks_mismatched_signoff_evidence(
    tmp_path: Path,
) -> None:
    """Strict release checks require sign-off evidence to match gate evidence."""
    checker = _load_phase6_release_evidence()
    evidence_path = tmp_path / "phase6-release-evidence.md"
    _write(
        evidence_path,
        "\n".join(
            [
                "# Phase 6 API vNext Release Evidence",
                "",
                "| Gate | Owner | Evidence source | Decision | Notes |",
                "|---|---|---|---|---|",
                "| Active Platform clients support API vNext | Platform owner | release/client-matrix.md | Ready | All active clients checked. |",
                "| Retired endpoint usage below removal threshold | Data owner | release/telemetry.md | Ready | Usage is below threshold. |",
                "| Alias window announced and elapsed | Release owner | release/announcement.md | Ready | Window elapsed. |",
                "| Rollback playbook verified | Ops owner | runbooks/phase6.md | Ready | Dry run passed. |",
                "| Platform render source audit completed | Platform owner | platform/render-audit.md | Ready | Source audit passed. |",
                "| API support policy decided | Product owner | release/api-policy.md | Ready | Policy accepted. |",
                "",
                "## Sign-off Record",
                "",
                "| Date | Gate | Reviewer | Decision | Evidence link |",
                "|---|---|---|---|---|",
                "| 2026-07-02 | Active Platform clients support API vNext | Platform reviewer | Approved | release/other-client-matrix.md |",
                "| 2026-07-02 | Retired endpoint usage below removal threshold | Data reviewer | Approved | release/telemetry.md |",
                "| 2026-07-02 | Alias window announced and elapsed | Release reviewer | Approved | release/announcement.md |",
                "| 2026-07-02 | Rollback playbook verified | Ops reviewer | Approved | runbooks/phase6.md |",
                "| 2026-07-02 | Platform render source audit completed | Platform reviewer | Approved | platform/render-audit.md |",
                "| 2026-07-02 | API support policy decided | Product reviewer | Approved | release/api-policy.md |",
                "",
            ]
        ),
    )

    assert checker.main([str(evidence_path)]) == 1
