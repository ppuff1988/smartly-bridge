# Phase 6 API vNext Release Evidence

This document is the evidence workspace for Phase 6 API vNext cleanup release gates. It records external proof that cannot be produced by Bridge unit tests or static audit alone.

Do not mark a gate as ready from intent, verbal confirmation, or a local-only check. Each gate needs an owner, source link or command output, review date, and explicit decision.

## Status

| Gate | Owner | Evidence source | Decision | Notes |
|---|---|---|---|---|
| Active Platform clients support API vNext | TBD | TBD | Pending | Need app/web/client version inventory and supported envelope matrix. |
| Retired endpoint usage below removal threshold | TBD | TBD | Pending | Need telemetry over the agreed release window. |
| Alias window announced and elapsed | TBD | TBD | Pending | Need release note or customer communication record. |
| Rollback playbook verified | TBD | TBD | Pending | Need rehearsal result and owner sign-off. |
| Platform render source audit completed | TBD | TBD | Pending | Need dashboard/card/automation editor audit from Platform repo or client build. |
| API support policy decided | TBD | TBD | Pending | Need product/release decision for removed paths and any retained support horizon. |

## Evidence Requirements

### Active Platform Clients

Required evidence:

- Platform release inventory with every active app, web, and client build that can connect to this Bridge release.
- Compatibility matrix showing each client can consume API vNext `schema_version`, `data`, `warnings`, and `errors`.
- Confirmation that command, sync, event, diagnostics, history, camera, WebRTC, and media exception contracts are covered.

Acceptance:

- Every active client version is marked compatible, or the release notes name an explicit block with an owner and next action.

### Retired Endpoint Usage

Required evidence:

- Telemetry query or dashboard link for the agreed release window.
- Usage counts for retired endpoints and entity/action control request shapes.
- Outlier list with owner and decision.

Acceptance:

- Usage is below the product-defined threshold for the full window, and every outlier is triaged or accepted by release owner.

### Alias Window

Required evidence:

- Announcement link or release note.
- Announcement date.
- Target removal date.
- Affected alias and retired path list.

Acceptance:

- The announced window has elapsed before removal is enabled for release.

### Rollback Playbook

Required evidence:

- Runbook link or checked-in release procedure.
- Rehearsal date and result.
- Verification commands.
- Owner and escalation contact.

Acceptance:

- The playbook can restore the prior API behavior or redeploy a compatible build, and rehearsal verification passed.

### Platform Render Source Audit

Required evidence:

- Platform repo commit, PR, or client build audit.
- Dashboard, device card, detail page, and automation editor review results.
- Confirmation that rendering uses capability and presentation contracts rather than Home Assistant entity ids, brand fields, or source payload shape for core UI.

Acceptance:

- No required render path depends on source-specific fields for core presentation.

### API Support Policy

Required evidence:

- Product or release decision record.
- Removed path list.
- Retained support path list, if any.
- Owner and support horizon for any retained path.
- Customer communication plan.

Acceptance:

- Every pre-vNext API path is either removed, retained with owner and horizon, or blocked by a documented dependency.

## Local Verification Before Attaching Evidence

Run these from the existing devcontainer:

```bash
pytest tests/test_phase6_audit.py -q
python scripts/phase6_audit.py
python docs/validate-openapi.py
```

Expected result:

- Phase 6 audit tests pass.
- Phase 6 code audit passes.
- OpenAPI validation passes.

## Sign-off Record

| Date | Gate | Reviewer | Decision | Evidence link |
|---|---|---|---|---|
| TBD | TBD | TBD | Pending | TBD |
