"""Tests for Phase 6 release evidence status checks."""

from __future__ import annotations

import importlib.util
import json
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

    statuses = checker.load_statuses(PROJECT_ROOT / "docs/specs/phase6-release-evidence.md")

    pending = [status for status in statuses if not status.ready]
    assert {status.gate for status in pending} == {
        "Active Platform clients support API vNext",
        "Retired endpoint usage below removal threshold",
        "Alias window announced and elapsed",
        "Rollback playbook verified",
        "Platform render source audit completed",
        "API support policy decided",
    }


def test_phase6_release_evidence_json_reports_pending_gates(capsys) -> None:
    """The CLI can emit machine-readable pending release gates."""
    checker = _load_phase6_release_evidence()

    result = checker.main(
        [
            str(PROJECT_ROOT / "docs/specs/phase6-release-evidence.md"),
            "--allow-pending",
            "--json",
        ]
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ready"] is False
    assert output["pending_count"] == 6
    assert output["pending_gates"][0] == {
        "gate": "Active Platform clients support API vNext",
        "owner": "TBD",
        "evidence_source": "TBD",
        "decision": "Pending",
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


def test_phase6_release_evidence_treats_placeholder_text_as_incomplete(
    tmp_path: Path,
) -> None:
    """Ready gates cannot hide placeholder wording inside owner or evidence text."""
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
                "| Active Platform clients support API vNext | TBD Platform owner | release/client-matrix.md | Ready | All active clients checked. |",
                "| Retired endpoint usage below removal threshold | Data owner | pending telemetry link | Ready | Usage is below threshold. |",
                "| Alias window announced and elapsed | Release owner | release/announcement.md | Ready | Window elapsed. |",
                "| Rollback playbook verified | Ops owner | runbooks/phase6.md | Ready | Dry run passed. |",
                "| Platform render source audit completed | Platform owner | platform/render-audit.md | Ready | Source audit passed. |",
                "| API support policy decided | Product owner | release/api-policy.md | Ready | Policy accepted. |",
                "",
            ]
        ),
    )

    statuses = checker.load_statuses(evidence_path)

    pending = [status.gate for status in statuses if not status.ready]
    assert pending == [
        "Active Platform clients support API vNext",
        "Retired endpoint usage below removal threshold",
    ]


def test_phase6_release_evidence_rejects_placeholder_status_notes(
    tmp_path: Path,
) -> None:
    """Ready gates cannot hide placeholder wording inside notes."""
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
                "| Active Platform clients support API vNext | Platform owner | release/client-matrix.md | Ready | TBD client exception. |",
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
                "| 2026-07-02 | Active Platform clients support API vNext | Platform reviewer | Approved | release/client-matrix.md |",
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


def test_phase6_release_evidence_rejects_verbal_evidence_sources(
    tmp_path: Path,
) -> None:
    """Ready gates need auditable evidence sources, not verbal confirmation."""
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
                "| Active Platform clients support API vNext | Platform owner | verbal confirmation | Ready | All active clients checked. |",
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
                "| 2026-07-02 | Active Platform clients support API vNext | Platform reviewer | Approved | verbal confirmation |",
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


def test_phase6_release_evidence_requires_iso_signoff_dates(
    tmp_path: Path,
) -> None:
    """Completed sign-off rows require an auditable ISO date."""
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
                "| after rollout | Active Platform clients support API vNext | Platform reviewer | Approved | release/client-matrix.md |",
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


def test_phase6_release_evidence_rejects_invalid_calendar_dates(
    tmp_path: Path,
) -> None:
    """Completed sign-off dates must be valid calendar dates."""
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
                "| 2026-99-99 | Active Platform clients support API vNext | Platform reviewer | Approved | release/client-matrix.md |",
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


def test_phase6_release_evidence_rejects_future_signoff_dates(
    tmp_path: Path,
) -> None:
    """Completed sign-off dates must not be in the future."""
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
                "| 9999-12-31 | Active Platform clients support API vNext | Platform reviewer | Approved | release/client-matrix.md |",
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


def test_phase6_release_evidence_rejects_duplicate_gate_rows(
    tmp_path: Path,
) -> None:
    """Status evidence must have exactly one row per required gate."""
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
                "| Active Platform clients support API vNext | Platform owner | release/client-matrix.md | Ready | Duplicate row. |",
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
                "| 2026-07-02 | Active Platform clients support API vNext | Platform reviewer | Approved | release/client-matrix.md |",
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


def test_phase6_release_evidence_rejects_unknown_status_gate_rows(
    tmp_path: Path,
) -> None:
    """Status evidence must not include gates outside the Phase 6 release scope."""
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
                "| Out-of-scope release exception | Release owner | release/release-exception.md | Ready | Out of scope row. |",
                "",
                "## Sign-off Record",
                "",
                "| Date | Gate | Reviewer | Decision | Evidence link |",
                "|---|---|---|---|---|",
                "| 2026-07-02 | Active Platform clients support API vNext | Platform reviewer | Approved | release/client-matrix.md |",
                "| 2026-07-02 | Retired endpoint usage below removal threshold | Data reviewer | Approved | release/telemetry.md |",
                "| 2026-07-02 | Alias window announced and elapsed | Release reviewer | Approved | release/announcement.md |",
                "| 2026-07-02 | Rollback playbook verified | Ops reviewer | Approved | runbooks/phase6.md |",
                "| 2026-07-02 | Platform render source audit completed | Platform reviewer | Approved | platform/render-audit.md |",
                "| 2026-07-02 | API support policy decided | Product reviewer | Approved | release/api-policy.md |",
                "| 2026-07-02 | Out-of-scope release exception | Release reviewer | Approved | release/release-exception.md |",
                "",
            ]
        ),
    )

    assert checker.main([str(evidence_path)]) == 1


def test_phase6_release_evidence_rejects_duplicate_signoff_rows(
    tmp_path: Path,
) -> None:
    """Sign-off evidence must have exactly one row per gate/evidence pair."""
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
                "| 2026-07-02 | Active Platform clients support API vNext | Platform reviewer | Approved | release/client-matrix.md |",
                "| 2026-07-02 | Active Platform clients support API vNext | Platform reviewer | Approved | release/client-matrix.md |",
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


def test_phase6_release_evidence_rejects_unmatched_signoff_evidence_rows(
    tmp_path: Path,
) -> None:
    """Sign-off evidence links must match the gate evidence source exactly."""
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
                "| 2026-07-02 | Active Platform clients support API vNext | Platform reviewer | Approved | release/client-matrix.md |",
                "| 2026-07-02 | Active Platform clients support API vNext | Platform reviewer | Approved | release/old-client-matrix.md |",
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


def test_phase6_release_evidence_rejects_unknown_signoff_gate_rows(
    tmp_path: Path,
) -> None:
    """Sign-off evidence must not include gates outside the Phase 6 release scope."""
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
                "| 2026-07-02 | Active Platform clients support API vNext | Platform reviewer | Approved | release/client-matrix.md |",
                "| 2026-07-02 | Retired endpoint usage below removal threshold | Data reviewer | Approved | release/telemetry.md |",
                "| 2026-07-02 | Alias window announced and elapsed | Release reviewer | Approved | release/announcement.md |",
                "| 2026-07-02 | Rollback playbook verified | Ops reviewer | Approved | runbooks/phase6.md |",
                "| 2026-07-02 | Platform render source audit completed | Platform reviewer | Approved | platform/render-audit.md |",
                "| 2026-07-02 | API support policy decided | Product reviewer | Approved | release/api-policy.md |",
                "| 2026-07-02 | Out-of-scope release exception | Release reviewer | Approved | release/release-exception.md |",
                "",
            ]
        ),
    )

    assert checker.main([str(evidence_path)]) == 1
