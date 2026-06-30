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
