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


def test_phase6_audit_detects_active_contract_legacy_wording(tmp_path: Path) -> None:
    """The audit rejects legacy/deprecated wording in active contract docs."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/openapi.yaml",
        "description: Legacy Home Assistant style state payload\n",
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "active-contract-legacy-wording" for finding in findings)


def test_phase6_audit_detects_active_contract_backward_compatible_wording(
    tmp_path: Path,
) -> None:
    """The audit rejects backward-compatible wording in active contract docs."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/specs/api-vnext-contract.md",
        "- Backward compatible optional fields\n",
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "active-contract-legacy-wording" for finding in findings)


def test_phase6_audit_detects_openapi_legacy_control_body(tmp_path: Path) -> None:
    """The audit rejects OpenAPI docs that still publish entity/action control body."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/openapi.yaml",
        "paths:\n"
        "  /api/smartly/control:\n"
        "    post:\n"
        "      requestBody:\n"
        "        content:\n"
        "          application/json:\n"
        "            schema:\n"
        "              $ref: '#/components/schemas/ControlRequest'\n"
        "components:\n"
        "  schemas:\n"
        "    ControlRequest:\n"
        "      required: [entity_id, action]\n",
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "openapi-legacy-control-body" for finding in findings)


def test_phase6_audit_detects_openapi_top_level_error_response_schema(
    tmp_path: Path,
) -> None:
    """The audit rejects OpenAPI ErrorResponse schemas with top-level error."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/openapi.yaml",
        (
            "components:\n"
            "  schemas:\n"
            "    ErrorResponse:\n"
            "      type: object\n"
            "      properties:\n"
            "        error:\n"
            "          type: string\n"
        ),
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "openapi-top-level-error-response-schema"
        for finding in findings
    )


def test_phase6_audit_detects_openapi_component_response_top_level_error_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects reusable OpenAPI response examples with top-level errors."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/openapi.yaml",
        (
            "components:\n"
            "  responses:\n"
            "    UnauthorizedError:\n"
            "      content:\n"
            "        application/json:\n"
            "          example:\n"
            "            error: invalid_signature\n"
        ),
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "openapi-component-response-top-level-error-example"
        for finding in findings
    )


def test_phase6_audit_detects_openapi_control_top_level_error_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects control response examples with top-level errors."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/openapi.yaml",
        (
            "paths:\n"
            "  /api/smartly/control:\n"
            "    post:\n"
            "      responses:\n"
            "        '400':\n"
            "          content:\n"
            "            application/json:\n"
            "              examples:\n"
            "                invalidJson:\n"
            "                  value:\n"
            "                    error: invalid_json\n"
        ),
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "openapi-control-top-level-error-example"
        for finding in findings
    )


def test_phase6_audit_detects_openapi_device_event_top_level_success_schema(
    tmp_path: Path,
) -> None:
    """The audit rejects DeviceEventResponse schemas with top-level success."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/openapi.yaml",
        (
            "components:\n"
            "  schemas:\n"
            "    DeviceEventResponse:\n"
            "      type: object\n"
            "      properties:\n"
            "        success:\n"
            "          type: boolean\n"
            "        event_id:\n"
            "          type: string\n"
        ),
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "openapi-device-event-top-level-success-schema"
        for finding in findings
    )


def test_phase6_audit_detects_openapi_sync_top_level_success_schemas(
    tmp_path: Path,
) -> None:
    """The audit rejects sync response schemas with top-level payload fields."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/openapi.yaml",
        (
            "components:\n"
            "  schemas:\n"
            "    StructureResponse:\n"
            "      type: object\n"
            "      properties:\n"
            "        floors:\n"
            "          type: array\n"
            "    StatesResponse:\n"
            "      type: object\n"
            "      properties:\n"
            "        states:\n"
            "          type: array\n"
            "        count:\n"
            "          type: integer\n"
        ),
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "openapi-sync-top-level-success-schema"
        for finding in findings
    )


def test_phase6_audit_detects_openapi_sync_top_level_success_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects sync response examples with top-level payload fields."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/openapi.yaml",
        (
            "paths:\n"
            "  /api/smartly/sync/states:\n"
            "    get:\n"
            "      responses:\n"
            "        '200':\n"
            "          content:\n"
            "            application/json:\n"
            "              example:\n"
            "                states: []\n"
            "                count: 0\n"
        ),
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "openapi-sync-top-level-success-example"
        for finding in findings
    )


def test_phase6_audit_detects_openapi_device_event_top_level_success_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects device-event response examples with top-level success."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/openapi.yaml",
        (
            "paths:\n"
            "  /api/smartly/devices/{device_id}/events:\n"
            "    post:\n"
            "      responses:\n"
            "        '202':\n"
            "          content:\n"
            "            application/json:\n"
            "              example:\n"
            "                success: true\n"
            "                event_id: evt_01JZABC123\n"
        ),
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "openapi-device-event-top-level-success-example"
        for finding in findings
    )


def test_phase6_audit_detects_openapi_device_event_top_level_error_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects device-event response examples with top-level errors."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/openapi.yaml",
        (
            "paths:\n"
            "  /api/smartly/devices/{device_id}/events:\n"
            "    post:\n"
            "      responses:\n"
            "        '400':\n"
            "          content:\n"
            "            application/json:\n"
            "              examples:\n"
            "                invalidAction:\n"
            "                  value:\n"
            "                    error: invalid_action\n"
            "                    message: Unsupported button action\n"
        ),
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "openapi-device-event-top-level-error-example"
        for finding in findings
    )


def test_phase6_audit_detects_openapi_history_top_level_error_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects history response examples with top-level errors."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/openapi.yaml",
        (
            "paths:\n"
            "  /api/smartly/history/{entity_id}:\n"
            "    get:\n"
            "      responses:\n"
            "        '400':\n"
            "          content:\n"
            "            application/json:\n"
            "              examples:\n"
            "                invalid_time_range:\n"
            "                  value:\n"
            "                    error: invalid_time_range\n"
            "                    message: Time range cannot exceed 30 days\n"
        ),
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "openapi-history-top-level-error-example"
        for finding in findings
    )


def test_phase6_audit_detects_openapi_webhook_top_level_success_schemas(
    tmp_path: Path,
) -> None:
    """The audit rejects webhook response schemas with top-level success."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/openapi.yaml",
        (
            "webhooks:\n"
            "  stateChanged:\n"
            "    post:\n"
            "      responses:\n"
            "        '200':\n"
            "          content:\n"
            "            application/json:\n"
            "              schema:\n"
            "                type: object\n"
            "                properties:\n"
            "                  success:\n"
            "                    type: boolean\n"
        ),
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "openapi-webhook-top-level-success-schema"
        for finding in findings
    )


def test_phase6_audit_detects_public_control_legacy_body_docs(
    tmp_path: Path,
) -> None:
    """The audit rejects public control guides that still show entity/action body."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/control/api-basics.md",
        '```json\n{"entity_id": "light.bedroom", "action": "turn_on"}\n```\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "public-control-legacy-body-doc" for finding in findings)


def test_phase6_audit_detects_device_card_home_assistant_action_payload_docs(
    tmp_path: Path,
) -> None:
    """The audit rejects Platform docs that tell UI to send HA action payloads."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/smartly-device-card-capability-spec.md",
        (
            "Smartly light controls should send Home Assistant-compatible action "
            "payloads through Platform/Bridge.\n"
        ),
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "device-card-ha-action-payload-doc" for finding in findings
    )


def test_phase6_audit_detects_device_card_stale_color_temperature_capability_docs(
    tmp_path: Path,
) -> None:
    """The audit rejects device-card docs that expose source color_temp names."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/smartly-device-card-capability-spec.md",
        "| `color_temp` | Supports color temperature |\n",
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "device-card-stale-capability-doc" for finding in findings
    )


def test_phase6_audit_detects_device_card_top_level_sync_success_docs(
    tmp_path: Path,
) -> None:
    """The audit rejects device-card docs with top-level sync states/count."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/smartly-device-card-capability-spec.md",
        '```json\n{"states": [], "count": 0}\n```\n',
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "device-card-top-level-sync-success-doc"
        for finding in findings
    )


def test_phase6_audit_detects_device_presentation_stale_color_temp_capability(
    tmp_path: Path,
) -> None:
    """The audit rejects production presentation emitting stale color_temp."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "custom_components/smartly_bridge/device_presentation.py",
        'def light():\n    capabilities.append("color_temp")\n',
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "device-presentation-stale-capability"
        for finding in findings
    )


def test_phase6_audit_detects_public_control_stale_light_color_command_docs(
    tmp_path: Path,
) -> None:
    """The audit rejects public control docs with non-canonical light commands."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/control/device-types.md",
        (
            "| `color_rgb` | `set_rgb` | `{}` |\n"
            "| `color_temperature` | `set_kelvin` | `{\"kelvin\": 3000}` |\n"
        ),
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "public-control-stale-light-command-doc"
        for finding in findings
    )


def test_phase6_audit_detects_nested_public_control_legacy_body_docs(
    tmp_path: Path,
) -> None:
    """The audit rejects nested public control guides with legacy body examples."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/control/device-types.md",
        '```json\n{"entity_id": "switch.office", "service_data": {}}\n```\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "public-control-legacy-body-doc" for finding in findings)


def test_phase6_audit_detects_security_audit_legacy_control_body_docs(
    tmp_path: Path,
) -> None:
    """The audit rejects security docs that still validate entity/action bodies."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/security-audit.md",
        '```python\nentity_id = body.get("entity_id")\naction = body.get("action")\n```\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "public-control-legacy-body-doc" for finding in findings)


def test_phase6_audit_detects_history_docs_top_level_error_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects history docs that still show top-level error bodies."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/history-api.md",
        '```json\n{"error": "invalid_signature"}\n```\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "history-doc-top-level-error" for finding in findings)


def test_phase6_audit_detects_camera_docs_top_level_error_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects camera docs that still show top-level error bodies."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/camera-api.md",
        '```json\n{"error": "invalid_entity_id"}\n```\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "camera-doc-top-level-error" for finding in findings)


def test_phase6_audit_detects_camera_docs_top_level_success_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects camera docs that still show top-level success bodies."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/camera-api.md",
        '```json\n{"success": true, "action": "registered"}\n```\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "camera-doc-top-level-success" for finding in findings)


def test_phase6_audit_detects_sync_docs_top_level_error_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects sync docs that still show top-level error bodies."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/sync-api.md",
        '```json\n{"error": "rate_limited"}\n```\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "sync-doc-top-level-error" for finding in findings)


def test_phase6_audit_detects_sync_docs_top_level_success_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects sync docs that still show top-level states/count."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/sync-api.md",
        '```json\n{"states": [], "count": 0}\n```\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "sync-doc-top-level-success" for finding in findings)


def test_phase6_audit_detects_trust_proxy_docs_top_level_error_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects trust-proxy docs that still show top-level error bodies."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/development/trust-proxy.md",
        '```json\n{"error": "ip_not_allowed"}\n```\n',
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "trust-proxy-doc-top-level-error" for finding in findings
    )


def test_phase6_audit_detects_architecture_plan_top_level_error_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects architecture-plan docs that still show top-level errors."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/smartly_bridge_architecture_plan.md",
        '```json\n{"status": "failed", "error": {"code": "DEVICE_OFFLINE"}}\n```\n',
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "architecture-plan-doc-top-level-error"
        for finding in findings
    )


def test_phase6_audit_detects_architecture_plan_top_level_success_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects architecture command responses without vNext envelope."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/smartly_bridge_architecture_plan.md",
        (
            '```json\n{"command_id": "cmd_1", "status": "success", '
            '"device_id": "dev_1"}\n```\n'
        ),
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "architecture-plan-doc-top-level-success"
        for finding in findings
    )


def test_phase6_audit_allows_public_docs_source_entity_references(
    tmp_path: Path,
) -> None:
    """The public control-doc audit does not reject non-control source fields."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "README.md",
        '```json\n{"states": [{"entity_id": "light.bedroom"}]}\n```\n',
    )

    findings = audit.audit(tmp_path)

    assert not any(
        finding.code == "public-control-legacy-body-doc" for finding in findings
    )


def test_phase6_audit_detects_readme_sync_top_level_success_examples(
    tmp_path: Path,
) -> None:
    """The audit rejects README sync examples with top-level states/count."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "README.md",
        '```json\n{"states": [{"entity_id": "light.bedroom"}], "count": 1}\n```\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "sync-doc-top-level-success" for finding in findings)


def test_phase6_audit_detects_migration_plan_legacy_wording(
    tmp_path: Path,
) -> None:
    """The audit rejects migration-plan Phase 6 legacy wording."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/specs/migration-plan.md",
        "| 6 | 清理 legacy | 移除 deprecated endpoint |\n",
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "migration-plan-legacy-wording" for finding in findings)


def test_phase6_audit_detects_migration_plan_compatibility_wording(
    tmp_path: Path,
) -> None:
    """The audit rejects migration-plan compatibility wording."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs/specs/migration-plan.md",
        "- API consumer compatibility matrix\n",
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "migration-plan-legacy-wording" for finding in findings)


def test_phase6_audit_detects_control_test_legacy_wording(
    tmp_path: Path,
) -> None:
    """The audit rejects control/command test wording that still says legacy."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "tests/test_http.py",
        "def test_control_legacy_entity_action_body_is_rejected():\n"
        "    pass\n",
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "control-test-legacy-wording" for finding in findings)


def test_phase6_audit_detects_application_test_legacy_wording(
    tmp_path: Path,
) -> None:
    """The audit rejects application test wording that still says legacy."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "tests/test_application_device_events.py",
        'def test_source_button_action():\n    """Legacy button action events work."""\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "application-test-legacy-wording" for finding in findings)


def test_phase6_audit_detects_application_test_top_level_error_fields(
    tmp_path: Path,
) -> None:
    """The audit rejects application tests that still inject top-level errors."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "tests/test_application_hexagonal.py",
        'response = {"error": "service_call_failed", "errors": []}\n',
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "application-test-top-level-error" for finding in findings
    )


def test_phase6_audit_detects_history_view_test_top_level_success_fields(
    tmp_path: Path,
) -> None:
    """The audit rejects history view tests that still inject top-level success."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "tests/test_history_views.py",
        'response = {"success": True, "data": {}}\n',
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "history-view-test-top-level-success" for finding in findings
    )


def test_phase6_audit_detects_webrtc_test_top_level_success_fields(
    tmp_path: Path,
) -> None:
    """The audit rejects WebRTC tests that still inject top-level success."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "tests/test_webrtc.py",
        'response = {"success": True, "data": {}}\n',
    )

    findings = audit.audit(tmp_path)

    assert any(
        finding.code == "webrtc-test-top-level-success" for finding in findings
    )


def test_phase6_audit_detects_general_legacy_wording(tmp_path: Path) -> None:
    """The audit rejects general Phase 6 legacy wording outside audit records."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "docs" / "guide.md",
        "This deprecated control body should not be documented.\n",
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "general-legacy-wording" for finding in findings)


def test_phase6_audit_detects_request_time_fallback_wording(
    tmp_path: Path,
) -> None:
    """The audit rejects request-time fallback wording in resolver tests."""
    audit = _load_phase6_audit()
    _write(
        tmp_path / "tests/test_http.py",
        'def test_resolver():\n    """Does not create a request-time fallback."""\n',
    )

    findings = audit.audit(tmp_path)

    assert any(finding.code == "request-time-fallback-wording" for finding in findings)


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
