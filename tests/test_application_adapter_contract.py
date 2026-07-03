"""Tests for adapter manifest contract validation."""

from __future__ import annotations

from custom_components.smartly_bridge.application.adapter_contract import (
    validate_adapter_command_mapping_snapshot,
    validate_adapter_event_mapping_snapshot,
    validate_adapter_health_snapshot,
    validate_adapter_manifest,
    validate_adapter_manifest_set,
    validate_adapter_normalization_snapshot,
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


def test_adapter_normalization_snapshot_passes_when_manifest_matches_device() -> None:
    """Adapter snapshots must only emit manifest-declared canonical capabilities."""
    result = validate_adapter_normalization_snapshot(
        _valid_manifest(),
        {
            "id": "ldev_light_kitchen",
            "capabilities": [
                {
                    "type": "power",
                    "source_refs": [
                        {
                            "source": "home_assistant",
                            "domain": "light",
                            "source_entity_id": "light.kitchen",
                        }
                    ],
                },
                {
                    "type": "brightness",
                    "source_refs": [
                        {
                            "source": "home_assistant",
                            "domain": "light",
                            "source_entity_id": "light.kitchen",
                        }
                    ],
                },
            ],
        },
    )

    assert result.is_valid is True
    assert result.errors == []


def test_adapter_normalization_snapshot_rejects_undeclared_capabilities() -> None:
    """Snapshot capabilities must be backed by the adapter manifest."""
    snapshot = {
        "id": "ldev_light_kitchen",
        "capabilities": [
            {
                "type": "temperature",
                "source_refs": [
                    {
                        "source": "home_assistant",
                        "domain": "light",
                        "source_entity_id": "light.kitchen",
                    }
                ],
            }
        ],
    }

    result = validate_adapter_normalization_snapshot(_valid_manifest(), snapshot)

    assert result.is_valid is False
    assert result.errors == [
        {
            "code": "UNDECLARED_SNAPSHOT_CAPABILITY",
            "path": "logical_device.capabilities[0].type",
            "message": ("Normalization snapshot emits undeclared capability: temperature"),
        }
    ]


def test_adapter_normalization_snapshot_rejects_out_of_scope_source_refs() -> None:
    """Snapshot source references must stay inside the manifest source/domain scope."""
    snapshot = {
        "id": "ldev_light_kitchen",
        "capabilities": [
            {
                "type": "power",
                "source_refs": [
                    {
                        "source": "zigbee2mqtt",
                        "domain": "switch",
                        "source_entity_id": "switch.kitchen",
                    }
                ],
            }
        ],
    }

    result = validate_adapter_normalization_snapshot(_valid_manifest(), snapshot)

    assert result.is_valid is False
    assert result.errors == [
        {
            "code": "SNAPSHOT_SOURCE_OUT_OF_SCOPE",
            "path": "logical_device.capabilities[0].source_refs[0].source",
            "message": ("Normalization snapshot source is not declared by manifest: zigbee2mqtt"),
        },
        {
            "code": "SNAPSHOT_DOMAIN_OUT_OF_SCOPE",
            "path": "logical_device.capabilities[0].source_refs[0].domain",
            "message": "Normalization snapshot domain is not declared by manifest: switch",
        },
    ]


def test_adapter_command_mapping_snapshot_passes_when_result_matches_manifest() -> None:
    """Adapter command snapshots must return manifest-scoped command results."""
    result = validate_adapter_command_mapping_snapshot(
        _valid_manifest(),
        {
            "command_id": "cmd_001",
            "status": "accepted",
            "adapter_id": "home_assistant.light",
            "source_request_id": "ha_context_id",
            "expected_state": {
                "power": {"value": True},
                "brightness": {"value": 80},
            },
        },
    )

    assert result.is_valid is True
    assert result.errors == []


def test_adapter_command_mapping_snapshot_rejects_undeclared_expected_state() -> None:
    """Expected state must only reference manifest-declared canonical capabilities."""
    result = validate_adapter_command_mapping_snapshot(
        _valid_manifest(),
        {
            "command_id": "cmd_001",
            "status": "accepted",
            "adapter_id": "home_assistant.light",
            "source_request_id": "ha_context_id",
            "expected_state": {
                "temperature": {"value": 24},
            },
        },
    )

    assert result.is_valid is False
    assert result.errors == [
        {
            "code": "UNDECLARED_COMMAND_EXPECTED_STATE",
            "path": "command_result.expected_state.temperature",
            "message": (
                "Command mapping snapshot expected_state uses undeclared " "capability: temperature"
            ),
        }
    ]


def test_adapter_command_mapping_snapshot_rejects_adapter_id_mismatch() -> None:
    """Command result adapter_id must identify the adapter that owns the manifest."""
    result = validate_adapter_command_mapping_snapshot(
        _valid_manifest(),
        {
            "command_id": "cmd_001",
            "status": "accepted",
            "adapter_id": "home_assistant.switch",
            "source_request_id": "ha_context_id",
            "expected_state": {
                "power": {"value": True},
            },
        },
    )

    assert result.is_valid is False
    assert result.errors == [
        {
            "code": "COMMAND_ADAPTER_ID_MISMATCH",
            "path": "command_result.adapter_id",
            "message": (
                "Command mapping snapshot adapter_id must match manifest id: "
                "home_assistant.light"
            ),
        }
    ]


def test_adapter_event_mapping_snapshot_passes_with_source_event_id() -> None:
    """Adapter event snapshots must expose canonical event data and a dedupe source."""
    manifest = _valid_manifest()
    manifest["supported_capabilities"] = ["button_event"]

    result = validate_adapter_event_mapping_snapshot(
        manifest,
        [
            {
                "event_id": "evt_001",
                "device_id": "ldev_button",
                "capability": "button_event",
                "event": "single_press",
                "payload": {"button": "left"},
                "source_event_id": "ha_event_001",
                "raw_ref": "raw_evt_001",
            }
        ],
    )

    assert result.is_valid is True
    assert result.errors == []


def test_adapter_event_mapping_snapshot_rejects_missing_dedupe_source() -> None:
    """Events without a source event id must provide a generated dedupe key."""
    manifest = _valid_manifest()
    manifest["supported_capabilities"] = ["button_event"]

    result = validate_adapter_event_mapping_snapshot(
        manifest,
        [
            {
                "event_id": "evt_001",
                "device_id": "ldev_button",
                "capability": "button_event",
                "event": "single_press",
                "payload": {"button": "left"},
                "raw_ref": "raw_evt_001",
            }
        ],
    )

    assert result.is_valid is False
    assert result.errors == [
        {
            "code": "MISSING_EVENT_DEDUPE_SOURCE",
            "path": "events[0]",
            "message": "Event snapshot must include source_event_id or dedupe_key.",
        }
    ]


def test_adapter_event_mapping_snapshot_rejects_duplicate_source_event_ids() -> None:
    """Replay windows must reject duplicate source event ids."""
    manifest = _valid_manifest()
    manifest["supported_capabilities"] = ["button_event"]

    result = validate_adapter_event_mapping_snapshot(
        manifest,
        [
            {
                "event_id": "evt_001",
                "device_id": "ldev_button",
                "capability": "button_event",
                "event": "single_press",
                "payload": {"button": "left"},
                "source_event_id": "ha_event_001",
            },
            {
                "event_id": "evt_002",
                "device_id": "ldev_button",
                "capability": "button_event",
                "event": "single_press",
                "payload": {"button": "left"},
                "source_event_id": "ha_event_001",
            },
        ],
    )

    assert result.is_valid is False
    assert result.errors == [
        {
            "code": "DUPLICATE_SOURCE_EVENT_ID",
            "path": "events[1].source_event_id",
            "message": ("Source event id duplicates events[0].source_event_id: ha_event_001"),
        }
    ]


def test_adapter_event_mapping_snapshot_rejects_duplicate_dedupe_keys() -> None:
    """Generated dedupe keys must also be unique within the replay window."""
    manifest = _valid_manifest()
    manifest["supported_capabilities"] = ["button_event"]

    result = validate_adapter_event_mapping_snapshot(
        manifest,
        [
            {
                "event_id": "evt_001",
                "device_id": "ldev_button",
                "capability": "button_event",
                "event": "single_press",
                "payload": {"button": "left"},
                "dedupe_key": "button:left:single:2026-06-30T00:00:00Z",
            },
            {
                "event_id": "evt_002",
                "device_id": "ldev_button",
                "capability": "button_event",
                "event": "single_press",
                "payload": {"button": "left"},
                "dedupe_key": "button:left:single:2026-06-30T00:00:00Z",
            },
        ],
    )

    assert result.is_valid is False
    assert result.errors == [
        {
            "code": "DUPLICATE_EVENT_DEDUPE_KEY",
            "path": "events[1].dedupe_key",
            "message": (
                "Event dedupe key duplicates events[0].dedupe_key: "
                "button:left:single:2026-06-30T00:00:00Z"
            ),
        }
    ]


def test_adapter_health_snapshot_accepts_degraded_declared_capabilities() -> None:
    """Degraded health snapshots can identify manifest-declared degraded capabilities."""
    result = validate_adapter_health_snapshot(
        _valid_manifest(),
        {
            "status": "degraded",
            "last_success_at": "2026-06-30T00:00:00Z",
            "last_error": "Color temperature source attribute unavailable",
            "source_latency_ms": 42,
            "capabilities_degraded": ["color_temperature"],
        },
    )

    assert result.is_valid is True
    assert result.errors == []


def test_adapter_health_snapshot_rejects_degraded_without_capabilities() -> None:
    """Degraded adapters must say which capability is degraded."""
    result = validate_adapter_health_snapshot(
        _valid_manifest(),
        {
            "status": "degraded",
            "last_success_at": "2026-06-30T00:00:00Z",
            "last_error": "partial outage",
            "source_latency_ms": 42,
            "capabilities_degraded": [],
        },
    )

    assert result.is_valid is False
    assert result.errors == [
        {
            "code": "MISSING_DEGRADED_CAPABILITIES",
            "path": "health.capabilities_degraded",
            "message": "Degraded adapter health must list degraded capabilities.",
        }
    ]


def test_adapter_health_snapshot_rejects_unavailable_without_error() -> None:
    """Unavailable adapters must expose a traceable last_error."""
    result = validate_adapter_health_snapshot(
        _valid_manifest(),
        {
            "status": "unavailable",
            "last_success_at": None,
            "last_error": None,
            "source_latency_ms": None,
            "capabilities_degraded": [],
        },
    )

    assert result.is_valid is False
    assert result.errors == [
        {
            "code": "MISSING_HEALTH_ERROR",
            "path": "health.last_error",
            "message": "Unavailable adapter health must include last_error.",
        }
    ]


def test_adapter_health_snapshot_rejects_undeclared_degraded_capabilities() -> None:
    """Adapter health may only degrade capabilities declared by the manifest."""
    result = validate_adapter_health_snapshot(
        _valid_manifest(),
        {
            "status": "degraded",
            "last_success_at": "2026-06-30T00:00:00Z",
            "last_error": "temperature sensor unavailable",
            "source_latency_ms": 42,
            "capabilities_degraded": ["temperature"],
        },
    )

    assert result.is_valid is False
    assert result.errors == [
        {
            "code": "UNDECLARED_DEGRADED_CAPABILITY",
            "path": "health.capabilities_degraded[0]",
            "message": "Adapter health degrades undeclared capability: temperature",
        }
    ]
