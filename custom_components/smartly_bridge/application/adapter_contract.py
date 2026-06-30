"""Adapter manifest contract validation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


CANONICAL_CAPABILITIES = {
    "air_quality",
    "aqi",
    "battery",
    "brightness",
    "button_event",
    "button_press",
    "carbon_dioxide",
    "carbon_monoxide",
    "color_temperature",
    "current",
    "effect",
    "energy_meter",
    "fan_direction",
    "fan_oscillation",
    "fan_speed",
    "humidity",
    "illuminance",
    "lock",
    "mode_select",
    "motion",
    "numeric_setting",
    "open_close",
    "option_setting",
    "pm10",
    "pm25",
    "position",
    "power",
    "power_meter",
    "presence",
    "pressure",
    "preset_mode",
    "rgb_color",
    "run",
    "signal_quality",
    "swing_mode",
    "target_temperature",
    "target_temperature_range",
    "temperature",
    "tilt_position",
    "voltage",
}

ADAPTER_TYPES = {
    "protocol",
    "brand",
    "model",
    "generic",
    "diagnostic",
}

REQUIRED_CONTRACT_VERSIONS = {
    "device_abstraction",
    "capability",
}

COMMAND_RESULT_STATUSES = {
    "accepted",
    "rejected",
    "failed",
    "timeout",
}


@dataclass(frozen=True)
class AdapterManifestValidationResult:
    """Result returned by adapter manifest validation."""

    errors: list[dict[str, str]] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return whether the manifest passed validation."""
        return not self.errors


def validate_adapter_manifest(manifest: dict[str, Any]) -> AdapterManifestValidationResult:
    """Validate an adapter manifest against the Smartly adapter contract."""
    errors: list[dict[str, str]] = []

    _validate_required_string(manifest, "id", errors)
    adapter_id = manifest.get("id")
    if isinstance(adapter_id, str) and not re.fullmatch(
        r"[a-z0-9]+(?:[._-][a-z0-9]+)*",
        adapter_id,
    ):
        errors.append(
            _error(
                "INVALID_ADAPTER_ID",
                "id",
                "Adapter id must be stable lowercase segments.",
            )
        )

    for key in ("name", "version"):
        _validate_required_string(manifest, key, errors)

    adapter_type = manifest.get("adapter_type")
    if adapter_type not in ADAPTER_TYPES:
        errors.append(
            _error(
                "INVALID_ADAPTER_TYPE",
                "adapter_type",
                "Adapter type must be one of the supported adapter contract types.",
            )
        )

    _validate_string_list(manifest, "supported_sources", errors)
    _validate_string_list(manifest, "supported_domains", errors)
    capabilities = _validate_string_list(manifest, "supported_capabilities", errors)
    for index, capability in enumerate(capabilities):
        if capability not in CANONICAL_CAPABILITIES:
            errors.append(
                _error(
                    "UNSUPPORTED_CAPABILITY",
                    f"supported_capabilities[{index}]",
                    f"Unsupported canonical capability: {capability}",
                )
            )

    match_priority = manifest.get("match_priority")
    if not isinstance(match_priority, int) or match_priority < 0:
        errors.append(
            _error(
                "INVALID_MATCH_PRIORITY",
                "match_priority",
                "Match priority must be a non-negative integer.",
            )
        )

    _validate_contract_versions(manifest.get("contract_versions"), errors)
    _validate_permissions(manifest.get("permissions"), errors)

    return AdapterManifestValidationResult(errors)


def validate_adapter_manifest_set(
    manifests: list[dict[str, Any]],
) -> AdapterManifestValidationResult:
    """Validate a set of adapter manifests for cross-adapter contract conflicts."""
    errors: list[dict[str, str]] = []
    valid_manifest_indexes: list[int] = []

    for index, manifest in enumerate(manifests):
        result = validate_adapter_manifest(manifest)
        if result.errors:
            errors.extend(_prefix_errors(result.errors, f"manifests[{index}]"))
        else:
            valid_manifest_indexes.append(index)

    for current_position, current_index in enumerate(valid_manifest_indexes):
        current = manifests[current_index]
        for previous_index in valid_manifest_indexes[:current_position]:
            previous = manifests[previous_index]
            if (
                previous["adapter_type"] != current["adapter_type"]
                or previous["match_priority"] != current["match_priority"]
            ):
                continue

            shared_sources = sorted(
                set(previous["supported_sources"]) & set(current["supported_sources"])
            )
            shared_domains = sorted(
                set(previous["supported_domains"]) & set(current["supported_domains"])
            )
            if not shared_sources or not shared_domains:
                continue

            errors.append(
                _error(
                    "MATCH_PRIORITY_COLLISION",
                    f"manifests[{current_index}].match_priority",
                    (
                        f"Match priority collides with {previous['id']} for "
                        f"source {shared_sources[0]} and domain {shared_domains[0]}."
                    ),
                )
            )

    return AdapterManifestValidationResult(errors)


def validate_adapter_normalization_snapshot(
    manifest: dict[str, Any],
    logical_device: dict[str, Any],
) -> AdapterManifestValidationResult:
    """Validate an adapter logical-device snapshot against its manifest."""
    errors: list[dict[str, str]] = []
    manifest_result = validate_adapter_manifest(manifest)
    if manifest_result.errors:
        errors.extend(_prefix_errors(manifest_result.errors, "manifest"))
        return AdapterManifestValidationResult(errors)

    supported_capabilities = set(manifest["supported_capabilities"])
    supported_sources = set(manifest["supported_sources"])
    supported_domains = set(manifest["supported_domains"])
    capabilities = logical_device.get("capabilities")
    if not isinstance(capabilities, list):
        errors.append(
            _error(
                "INVALID_NORMALIZATION_SNAPSHOT",
                "logical_device.capabilities",
                "Normalization snapshot must contain a capabilities list.",
            )
        )
        return AdapterManifestValidationResult(errors)

    for index, capability in enumerate(capabilities):
        if not isinstance(capability, dict):
            errors.append(
                _error(
                    "INVALID_NORMALIZATION_SNAPSHOT",
                    f"logical_device.capabilities[{index}]",
                    "Snapshot capability must be an object.",
                )
            )
            continue

        capability_type = capability.get("type")
        if capability_type not in CANONICAL_CAPABILITIES:
            errors.append(
                _error(
                    "UNSUPPORTED_CAPABILITY",
                    f"logical_device.capabilities[{index}].type",
                    f"Unsupported canonical capability: {capability_type}",
                )
            )
            continue

        if capability_type not in supported_capabilities:
            errors.append(
                _error(
                    "UNDECLARED_SNAPSHOT_CAPABILITY",
                    f"logical_device.capabilities[{index}].type",
                    f"Normalization snapshot emits undeclared capability: {capability_type}",
                )
            )

        _validate_snapshot_source_refs(
            capability,
            index,
            supported_sources,
            supported_domains,
            errors,
        )

    return AdapterManifestValidationResult(errors)


def validate_adapter_command_mapping_snapshot(
    manifest: dict[str, Any],
    command_result: dict[str, Any],
) -> AdapterManifestValidationResult:
    """Validate an adapter command mapping snapshot against its manifest."""
    errors: list[dict[str, str]] = []
    manifest_result = validate_adapter_manifest(manifest)
    if manifest_result.errors:
        errors.extend(_prefix_errors(manifest_result.errors, "manifest"))
        return AdapterManifestValidationResult(errors)

    adapter_id = command_result.get("adapter_id")
    if adapter_id != manifest["id"]:
        errors.append(
            _error(
                "COMMAND_ADAPTER_ID_MISMATCH",
                "command_result.adapter_id",
                f"Command mapping snapshot adapter_id must match manifest id: {manifest['id']}",
            )
        )

    status = command_result.get("status")
    if status not in COMMAND_RESULT_STATUSES:
        errors.append(
            _error(
                "INVALID_COMMAND_RESULT_STATUS",
                "command_result.status",
                "Command mapping snapshot status is not supported.",
            )
        )

    expected_state = command_result.get("expected_state", {})
    if not isinstance(expected_state, dict):
        errors.append(
            _error(
                "INVALID_COMMAND_EXPECTED_STATE",
                "command_result.expected_state",
                "Command mapping snapshot expected_state must be an object.",
            )
        )
        return AdapterManifestValidationResult(errors)

    supported_capabilities = set(manifest["supported_capabilities"])
    for capability in expected_state:
        if capability not in CANONICAL_CAPABILITIES:
            errors.append(
                _error(
                    "UNSUPPORTED_CAPABILITY",
                    f"command_result.expected_state.{capability}",
                    f"Unsupported canonical capability: {capability}",
                )
            )
            continue

        if capability not in supported_capabilities:
            errors.append(
                _error(
                    "UNDECLARED_COMMAND_EXPECTED_STATE",
                    f"command_result.expected_state.{capability}",
                    (
                        "Command mapping snapshot expected_state uses undeclared "
                        f"capability: {capability}"
                    ),
                )
            )

    return AdapterManifestValidationResult(errors)


def _validate_snapshot_source_refs(
    capability: dict[str, Any],
    capability_index: int,
    supported_sources: set[str],
    supported_domains: set[str],
    errors: list[dict[str, str]],
) -> None:
    source_refs = capability.get("source_refs", [])
    if not isinstance(source_refs, list):
        errors.append(
            _error(
                "INVALID_NORMALIZATION_SNAPSHOT",
                f"logical_device.capabilities[{capability_index}].source_refs",
                "Snapshot source_refs must be a list.",
            )
        )
        return

    for source_ref_index, source_ref in enumerate(source_refs):
        path = (
            f"logical_device.capabilities[{capability_index}]"
            f".source_refs[{source_ref_index}]"
        )
        if not isinstance(source_ref, dict):
            errors.append(
                _error(
                    "INVALID_NORMALIZATION_SNAPSHOT",
                    path,
                    "Snapshot source_ref must be an object.",
                )
            )
            continue

        source = source_ref.get("source")
        if source not in supported_sources:
            errors.append(
                _error(
                    "SNAPSHOT_SOURCE_OUT_OF_SCOPE",
                    f"{path}.source",
                    f"Normalization snapshot source is not declared by manifest: {source}",
                )
            )

        domain = source_ref.get("domain")
        if domain not in supported_domains:
            errors.append(
                _error(
                    "SNAPSHOT_DOMAIN_OUT_OF_SCOPE",
                    f"{path}.domain",
                    f"Normalization snapshot domain is not declared by manifest: {domain}",
                )
            )


def _validate_required_string(
    manifest: dict[str, Any],
    key: str,
    errors: list[dict[str, str]],
) -> None:
    value = manifest.get(key)
    if not isinstance(value, str) or not value:
        errors.append(_error("MISSING_REQUIRED_FIELD", key, f"Missing required field: {key}"))


def _validate_string_list(
    manifest: dict[str, Any],
    key: str,
    errors: list[dict[str, str]],
) -> list[str]:
    value = manifest.get(key)
    if not isinstance(value, list) or not value:
        errors.append(_error("INVALID_STRING_LIST", key, f"{key} must be a non-empty list."))
        return []

    strings = [item for item in value if isinstance(item, str) and item]
    if len(strings) != len(value):
        errors.append(_error("INVALID_STRING_LIST", key, f"{key} must contain only strings."))
    return strings


def _validate_contract_versions(
    value: Any,
    errors: list[dict[str, str]],
) -> None:
    if not isinstance(value, dict):
        errors.append(
            _error(
                "MISSING_REQUIRED_FIELD",
                "contract_versions",
                "Missing required field: contract_versions",
            )
        )
        return

    for version_name in sorted(REQUIRED_CONTRACT_VERSIONS):
        if not isinstance(value.get(version_name), str) or not value.get(version_name):
            errors.append(
                _error(
                    "MISSING_CONTRACT_VERSION",
                    f"contract_versions.{version_name}",
                    f"Missing required contract version: {version_name}",
                )
            )


def _validate_permissions(
    value: Any,
    errors: list[dict[str, str]],
) -> None:
    if not isinstance(value, dict):
        errors.append(
            _error(
                "MISSING_REQUIRED_FIELD",
                "permissions",
                "Missing required field: permissions",
            )
        )
        return

    if value.get("network") is not False:
        errors.append(
            _error(
                "NETWORK_PERMISSION_NOT_ALLOWED",
                "permissions.network",
                "Network permission must default to false.",
            )
        )

    if value.get("filesystem") not in {"readonly", "none"}:
        errors.append(
            _error(
                "FILESYSTEM_PERMISSION_NOT_ALLOWED",
                "permissions.filesystem",
                "Filesystem permission must be readonly or none.",
            )
        )

    secrets = value.get("secrets")
    if secrets != []:
        errors.append(
            _error(
                "SECRETS_PERMISSION_NOT_ALLOWED",
                "permissions.secrets",
                "Adapter manifests must not request secrets by default.",
            )
        )


def _error(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _prefix_errors(errors: list[dict[str, str]], prefix: str) -> list[dict[str, str]]:
    return [
        {
            **error,
            "path": f"{prefix}.{error['path']}",
        }
        for error in errors
    ]
