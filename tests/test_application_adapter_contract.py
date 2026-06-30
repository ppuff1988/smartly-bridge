"""Tests for adapter manifest contract validation."""

from __future__ import annotations

from custom_components.smartly_bridge.application.adapter_contract import (
    validate_adapter_manifest,
    validate_adapter_manifest_set,
)


def _valid_manifest() -> dict[str, object]:
    return {
        "id": "home_assistant.light",
        "name": "Home Assistant Light Adapter",
        "version": "0.1.0",
        "adapter_type": "protocol",
        "supported_sources": ["home_assistant"],
        "supported_domains": ["light"],
        "supported_capabilities": [
            "power",
            "brightness",
            "color_temperature",
            "rgb_color",
        ],
        "match_priority": 500,
        "contract_versions": {
            "device_abstraction": "2026.06",
            "capability": "2026.06",
        },
        "permissions": {
            "network": False,
            "filesystem": "readonly",
            "secrets": [],
        },
    }


def test_valid_adapter_manifest_passes_contract_validation() -> None:
    """Valid adapter manifests are accepted without framework dependencies."""
    result = validate_adapter_manifest(_valid_manifest())

    assert result.is_valid is True
    assert result.errors == []


def test_adapter_manifest_rejects_source_specific_capability_names() -> None:
    """Adapter manifests may only declare canonical capability names."""
    manifest = _valid_manifest()
    manifest["supported_capabilities"] = ["tapo_brightness"]

    result = validate_adapter_manifest(manifest)

    assert result.is_valid is False
    assert result.errors == [
        {
            "code": "UNSUPPORTED_CAPABILITY",
            "path": "supported_capabilities[0]",
            "message": "Unsupported canonical capability: tapo_brightness",
        }
    ]


def test_adapter_manifest_rejects_unsafe_permissions() -> None:
    """Adapter manifests must keep permissions minimized by default."""
    manifest = _valid_manifest()
    manifest["permissions"] = {
        "network": True,
        "filesystem": "write",
        "secrets": ["client_secret"],
    }

    result = validate_adapter_manifest(manifest)

    assert result.is_valid is False
    assert result.errors == [
        {
            "code": "NETWORK_PERMISSION_NOT_ALLOWED",
            "path": "permissions.network",
            "message": "Network permission must default to false.",
        },
        {
            "code": "FILESYSTEM_PERMISSION_NOT_ALLOWED",
            "path": "permissions.filesystem",
            "message": "Filesystem permission must be readonly or none.",
        },
        {
            "code": "SECRETS_PERMISSION_NOT_ALLOWED",
            "path": "permissions.secrets",
            "message": "Adapter manifests must not request secrets by default.",
        },
    ]


def test_adapter_manifest_rejects_missing_contract_versions() -> None:
    """Device abstraction and capability versions are required migration gates."""
    manifest = _valid_manifest()
    manifest["contract_versions"] = {"capability": "2026.06"}

    result = validate_adapter_manifest(manifest)

    assert result.is_valid is False
    assert result.errors == [
        {
            "code": "MISSING_CONTRACT_VERSION",
            "path": "contract_versions.device_abstraction",
            "message": "Missing required contract version: device_abstraction",
        }
    ]


def test_adapter_manifest_set_rejects_match_priority_collisions() -> None:
    """Overlapping adapter scopes must not share the same match priority."""
    first = _valid_manifest()
    second = _valid_manifest()
    second["id"] = "home_assistant.light.generic"
    second["name"] = "Home Assistant Generic Light Adapter"

    result = validate_adapter_manifest_set([first, second])

    assert result.is_valid is False
    assert result.errors == [
        {
            "code": "MATCH_PRIORITY_COLLISION",
            "path": "manifests[1].match_priority",
            "message": (
                "Match priority collides with home_assistant.light for "
                "source home_assistant and domain light."
            ),
        }
    ]


def test_adapter_manifest_set_allows_distinct_match_priority_scopes() -> None:
    """The same match priority is allowed when adapter scopes do not overlap."""
    first = _valid_manifest()
    second = _valid_manifest()
    second["id"] = "home_assistant.switch"
    second["name"] = "Home Assistant Switch Adapter"
    second["supported_domains"] = ["switch"]

    result = validate_adapter_manifest_set([first, second])

    assert result.is_valid is True
    assert result.errors == []
