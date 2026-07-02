"""Tests for camera application use cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from custom_components.smartly_bridge.application.camera import (
    CameraConfigCommand,
    CameraConfigUseCase,
    CameraHLSUseCase,
    CameraListUseCase,
    CameraSnapshotUseCase,
    CameraStreamUseCase,
)
from custom_components.smartly_bridge.domain.models import CameraSnapshot, CameraStreamInfo


def _fixture(name: str) -> dict[str, Any]:
    """Load an API vNext fixture."""
    return json.loads(
        (Path(__file__).parent / "fixtures" / "api-vnext" / name).read_text()
    )


def _serializable_camera_body(body: dict[str, Any]) -> dict[str, Any]:
    """Convert camera domain objects into stable fixture data."""
    converted = dict(body)
    snapshot = converted.get("snapshot")
    if isinstance(snapshot, CameraSnapshot):
        snapshot_payload = {
            "entity_id": snapshot.entity_id,
            "content_type": snapshot.content_type,
            "timestamp": snapshot.timestamp,
            "etag": snapshot.etag,
            "image_size": len(snapshot.image_data),
        }
        converted["snapshot"] = snapshot_payload
        converted["data"] = {
            **converted.get("data", {}),
            "snapshot": snapshot_payload,
        }
    return converted


def _assert_vnext_only_top_level(body: dict[str, Any]) -> None:
    """Assert a response only exposes API vNext envelope fields at top-level."""
    assert set(body) <= {
        "schema_version",
        "data",
        "warnings",
        "errors",
        "request_id",
        "correlation_id",
    }


class FakeCameraGateway:
    """Fake camera port."""

    def __init__(self) -> None:
        self.registered: dict[str, dict[str, Any]] = {}
        self.unregistered: list[str] = []
        self.cleared_entity_id: str | None = None
        self.allowed_cameras = ["camera.front", "camera.back"]
        self.states = {
            "camera.front": {
                "entity_id": "camera.front",
                "name": "Front",
                "state": "idle",
                "is_streaming": False,
                "brand": "Reolink",
                "model": "RLC",
                "supported_features": 3,
            },
            "camera.back": {
                "entity_id": "camera.back",
                "name": "Back",
                "state": "streaming",
                "is_streaming": True,
                "brand": None,
                "model": None,
                "supported_features": 1,
            },
        }
        self.stream_info = CameraStreamInfo(
            entity_id="camera.front",
            name="Front",
            supports_snapshot=True,
            supports_mjpeg=True,
            supports_hls=True,
            supports_webrtc=False,
            is_streaming=False,
        )
        self.snapshot = CameraSnapshot(
            entity_id="camera.front",
            image_data=b"jpeg-data",
            content_type="image/jpeg",
            timestamp=123.45,
            etag='"snapshot-etag"',
        )
        self.not_modified = False
        self.snapshot_requested: tuple[str, bool, str | None] | None = None

    def list_allowed_camera_ids(self) -> list[str]:
        return self.allowed_cameras

    def get_camera_state(self, entity_id: str) -> dict[str, Any] | None:
        return self.states.get(entity_id)

    async def get_stream_info(self, entity_id: str) -> CameraStreamInfo | None:
        if entity_id == "camera.front":
            return self.stream_info
        return None

    def get_cache_stats(self) -> dict[str, Any]:
        return {"cached_snapshots": 0}

    def get_hls_stats(self) -> dict[str, Any]:
        return {"active_streams": 0}

    def register_camera(self, config: dict[str, Any]) -> None:
        self.registered[config["entity_id"]] = config

    def unregister_camera(self, entity_id: str) -> None:
        self.unregistered.append(entity_id)

    async def clear_cache(self, entity_id: str | None = None) -> int:
        self.cleared_entity_id = entity_id
        return 2

    async def get_snapshot(
        self,
        entity_id: str,
        force_refresh: bool = False,
        if_none_match: str | None = None,
    ) -> tuple[CameraSnapshot | None, bool]:
        self.snapshot_requested = (entity_id, force_refresh, if_none_match)
        if self.not_modified:
            return None, True
        if entity_id == "camera.front":
            return self.snapshot, False
        return None, False

    def list_registered_cameras(self) -> list[dict[str, Any]]:
        return [{"entity_id": "camera.front", "name": "Front"}]

    async def start_hls_stream(self, entity_id: str) -> dict[str, Any] | None:
        if entity_id == "camera.front":
            return {"playlist_url": "/api/hls/front.m3u8"}
        return None

    async def stop_hls_stream(self, entity_id: str) -> bool:
        return entity_id == "camera.front"


@pytest.mark.asyncio
async def test_camera_list_returns_only_allowed_camera_states() -> None:
    """Camera list use case filters through the gateway and adds stats."""
    result = await CameraListUseCase(FakeCameraGateway()).execute(include_capabilities=False)

    assert result.status == 200
    _assert_vnext_only_top_level(result.body)
    assert result.body["data"]["count"] == 2
    assert [camera["entity_id"] for camera in result.body["data"]["cameras"]] == [
        "camera.front",
        "camera.back",
    ]
    assert result.body["data"]["cache_stats"] == {"cached_snapshots": 0}
    assert result.body["data"]["hls_stats"] == {"active_streams": 0}


@pytest.mark.asyncio
async def test_camera_list_adds_capabilities_when_requested() -> None:
    """Capability lookups stay behind the camera gateway."""
    result = await CameraListUseCase(FakeCameraGateway()).execute(include_capabilities=True)

    _assert_vnext_only_top_level(result.body)
    front = result.body["data"]["cameras"][0]
    assert front["capabilities"] == {
        "snapshot": True,
        "mjpeg": True,
        "hls": True,
        "webrtc": False,
    }
    assert front["endpoints"]["hls"] == "/api/smartly/camera/camera.front/stream/hls"
    assert "capabilities" not in result.body["data"]["cameras"][1]


@pytest.mark.asyncio
async def test_camera_list_response_includes_vnext_envelope() -> None:
    """Camera list responses expose API vNext envelope fields."""
    result = await CameraListUseCase(FakeCameraGateway()).execute(include_capabilities=False)

    assert result.status == 200
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    _assert_vnext_only_top_level(result.body)
    assert result.body["data"] == {
        "cameras": result.body["data"]["cameras"],
        "count": 2,
        "cache_stats": {"cached_snapshots": 0},
        "hls_stats": {"active_streams": 0},
    }


@pytest.mark.asyncio
async def test_camera_list_response_matches_api_vnext_fixture() -> None:
    """Camera list full response remains stable for legacy and vNext clients."""
    result = await CameraListUseCase(FakeCameraGateway()).execute(include_capabilities=False)

    assert result.status == 200
    assert result.body == _fixture("camera-list.json")


@pytest.mark.asyncio
async def test_camera_config_registers_camera() -> None:
    """Register command is translated to a camera gateway config."""
    gateway = FakeCameraGateway()
    result = await CameraConfigUseCase(gateway).execute(
        CameraConfigCommand(
            action="register",
            entity_id="camera.new",
            data={"name": "New", "snapshot_url": "http://cam/snapshot"},
        )
    )

    assert result.status == 200
    _assert_vnext_only_top_level(result.body)
    assert result.body["data"]["success"] is True
    assert result.body["data"]["action"] == "registered"
    assert result.body["data"]["entity_id"] == "camera.new"
    assert gateway.registered["camera.new"]["snapshot_url"] == "http://cam/snapshot"


@pytest.mark.asyncio
async def test_camera_config_register_response_includes_vnext_envelope() -> None:
    """Camera register responses expose API vNext envelope fields."""
    result = await CameraConfigUseCase(FakeCameraGateway()).execute(
        CameraConfigCommand(
            action="register",
            entity_id="camera.new",
            data={"name": "New"},
        )
    )

    assert result.status == 200
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {
        "success": True,
        "action": "registered",
        "entity_id": "camera.new",
    }


@pytest.mark.asyncio
async def test_camera_config_register_response_matches_api_vnext_fixture() -> None:
    """Camera register full response remains stable for legacy and vNext clients."""
    result = await CameraConfigUseCase(FakeCameraGateway()).execute(
        CameraConfigCommand(
            action="register",
            entity_id="camera.new",
            data={"name": "New"},
        )
    )

    assert result.status == 200
    assert result.body == _fixture("camera-config-register.json")


@pytest.mark.asyncio
async def test_camera_config_rejects_register_without_entity_id() -> None:
    """Register command requires an entity id and exposes API vNext errors."""
    result = await CameraConfigUseCase(FakeCameraGateway()).execute(
        CameraConfigCommand(action="register", entity_id=None, data={})
    )

    assert result.status == 400
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "MISSING_ENTITY_ID",
            "message": "missing entity id",
            "target": "camera",
            "retryable": False,
        }
    ]


@pytest.mark.asyncio
async def test_camera_config_register_missing_entity_response_matches_api_vnext_fixture() -> None:
    """Camera register missing-entity response remains vNext-only."""
    result = await CameraConfigUseCase(FakeCameraGateway()).execute(
        CameraConfigCommand(action="register", entity_id=None, data={})
    )

    assert result.status == 400
    assert result.body == _fixture("camera-config-missing-entity.json")


@pytest.mark.asyncio
async def test_camera_config_unregister_response_includes_vnext_envelope() -> None:
    """Camera unregister responses expose API vNext envelope fields."""
    gateway = FakeCameraGateway()
    result = await CameraConfigUseCase(gateway).execute(
        CameraConfigCommand(action="unregister", entity_id="camera.old", data={})
    )

    assert result.status == 200
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {
        "success": True,
        "action": "unregistered",
        "entity_id": "camera.old",
    }
    assert gateway.unregistered == ["camera.old"]


@pytest.mark.asyncio
async def test_camera_config_unregister_response_matches_api_vnext_fixture() -> None:
    """Camera unregister full response remains stable for legacy and vNext clients."""
    result = await CameraConfigUseCase(FakeCameraGateway()).execute(
        CameraConfigCommand(action="unregister", entity_id="camera.old", data={})
    )

    assert result.status == 200
    assert result.body == _fixture("camera-config-unregister.json")


@pytest.mark.asyncio
async def test_camera_config_rejects_unregister_without_entity_id() -> None:
    """Unregister command requires an entity id and exposes API vNext errors."""
    gateway = FakeCameraGateway()
    result = await CameraConfigUseCase(gateway).execute(
        CameraConfigCommand(action="unregister", entity_id=None, data={})
    )

    assert result.status == 400
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "MISSING_ENTITY_ID",
            "message": "missing entity id",
            "target": "camera",
            "retryable": False,
        }
    ]
    assert gateway.unregistered == []


@pytest.mark.asyncio
async def test_camera_config_unregister_missing_entity_response_matches_api_vnext_fixture() -> None:
    """Camera unregister missing-entity response remains vNext-only."""
    gateway = FakeCameraGateway()
    result = await CameraConfigUseCase(gateway).execute(
        CameraConfigCommand(action="unregister", entity_id=None, data={})
    )

    assert result.status == 400
    assert result.body == _fixture("camera-config-missing-entity.json")
    assert gateway.unregistered == []


@pytest.mark.asyncio
async def test_camera_config_clear_cache_response_includes_vnext_envelope() -> None:
    """Camera clear-cache responses expose API vNext envelope fields."""
    gateway = FakeCameraGateway()
    result = await CameraConfigUseCase(gateway).execute(
        CameraConfigCommand(action="clear_cache", entity_id="camera.front", data={})
    )

    assert result.status == 200
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {
        "success": True,
        "action": "cache_cleared",
        "cleared_count": 2,
    }
    assert gateway.cleared_entity_id == "camera.front"


@pytest.mark.asyncio
async def test_camera_config_clear_cache_response_matches_api_vnext_fixture() -> None:
    """Camera clear-cache full response remains stable for legacy and vNext clients."""
    result = await CameraConfigUseCase(FakeCameraGateway()).execute(
        CameraConfigCommand(action="clear_cache", entity_id="camera.front", data={})
    )

    assert result.status == 200
    assert result.body == _fixture("camera-config-clear-cache.json")


@pytest.mark.asyncio
async def test_camera_config_list_response_includes_vnext_envelope() -> None:
    """Camera config-list responses expose API vNext envelope fields."""
    result = await CameraConfigUseCase(FakeCameraGateway()).execute(
        CameraConfigCommand(action="list", entity_id=None, data={})
    )

    assert result.status == 200
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {
        "cameras": [{"entity_id": "camera.front", "name": "Front"}],
        "count": 1,
    }


@pytest.mark.asyncio
async def test_camera_config_list_response_matches_api_vnext_fixture() -> None:
    """Camera config-list full response remains stable for legacy and vNext clients."""
    result = await CameraConfigUseCase(FakeCameraGateway()).execute(
        CameraConfigCommand(action="list", entity_id=None, data={})
    )

    assert result.status == 200
    assert result.body == _fixture("camera-config-list.json")


@pytest.mark.asyncio
async def test_camera_config_unknown_action_response_includes_vnext_envelope() -> None:
    """Camera config unknown actions expose API vNext error envelope fields."""
    result = await CameraConfigUseCase(FakeCameraGateway()).execute(
        CameraConfigCommand(action="unsupported", entity_id=None, data={})
    )

    assert result.status == 400
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "UNKNOWN_ACTION",
            "message": "unknown action",
            "target": "camera",
            "retryable": False,
        }
    ]


@pytest.mark.asyncio
async def test_camera_config_unknown_action_response_matches_api_vnext_fixture() -> None:
    """Camera config unknown-action response remains vNext-only."""
    result = await CameraConfigUseCase(FakeCameraGateway()).execute(
        CameraConfigCommand(action="unsupported", entity_id=None, data={})
    )

    assert result.status == 400
    assert result.body == _fixture("camera-config-unknown-action.json")


@pytest.mark.asyncio
async def test_camera_hls_start_returns_hls_not_supported_when_gateway_has_no_stream() -> None:
    """HLS start reports unsupported when the gateway cannot start a stream."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.back", "start")

    assert result.status == 400
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "HLS_NOT_SUPPORTED",
            "message": "hls not supported",
            "target": "camera",
            "retryable": False,
        }
    ]


@pytest.mark.asyncio
async def test_camera_hls_start_unsupported_response_matches_api_vnext_fixture() -> None:
    """Camera HLS start unsupported response remains stable for legacy clients."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.back", "start")

    assert result.status == 400
    assert result.body == _fixture("camera-hls-start-unsupported.json")


@pytest.mark.asyncio
async def test_camera_hls_start_response_includes_vnext_envelope() -> None:
    """HLS start responses expose API vNext envelope fields."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.front", "start")

    assert result.status == 200
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {"playlist_url": "/api/hls/front.m3u8"}


@pytest.mark.asyncio
async def test_camera_hls_start_response_matches_api_vnext_fixture() -> None:
    """Camera HLS start full response remains stable for legacy and vNext clients."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.front", "start")

    assert result.status == 200
    assert result.body == _fixture("camera-hls-start.json")


@pytest.mark.asyncio
async def test_camera_hls_info_response_includes_vnext_envelope() -> None:
    """HLS info responses expose API vNext envelope fields."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.front", "info")

    expected_data = {
        "entity_id": "camera.front",
        "name": "Front",
        "capabilities": {
            "snapshot": True,
            "mjpeg": True,
            "hls": True,
            "webrtc": False,
        },
        "endpoints": {
            "snapshot": "/api/smartly/camera/camera.front/snapshot",
            "mjpeg": "/api/smartly/camera/camera.front/stream",
            "hls": "/api/smartly/camera/camera.front/stream/hls",
        },
        "is_streaming": False,
    }
    assert result.status == 200
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == expected_data


@pytest.mark.asyncio
async def test_camera_hls_info_response_matches_api_vnext_fixture() -> None:
    """Camera HLS info full response remains stable for legacy and vNext clients."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.front", "info")

    assert result.status == 200
    assert result.body == _fixture("camera-hls-info.json")


@pytest.mark.asyncio
async def test_camera_hls_info_not_found_response_includes_vnext_envelope() -> None:
    """HLS info not-found responses expose API vNext envelope fields."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.back", "info")

    assert result.status == 404
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "CAMERA_NOT_FOUND",
            "message": "camera not found",
            "target": "camera",
            "retryable": False,
        }
    ]


@pytest.mark.asyncio
async def test_camera_hls_info_not_found_response_matches_api_vnext_fixture() -> None:
    """Camera HLS info not-found response remains stable for legacy clients."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.back", "info")

    assert result.status == 404
    assert result.body == _fixture("camera-hls-info-not-found.json")


@pytest.mark.asyncio
async def test_camera_hls_stats_response_includes_vnext_envelope() -> None:
    """HLS stats responses expose API vNext envelope fields."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.front", "stats")

    assert result.status == 200
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {"active_streams": 0}


@pytest.mark.asyncio
async def test_camera_hls_stats_response_matches_api_vnext_fixture() -> None:
    """Camera HLS stats full response remains stable for legacy and vNext clients."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.front", "stats")

    assert result.status == 200
    assert result.body == _fixture("camera-hls-stats.json")


@pytest.mark.asyncio
async def test_camera_hls_stop_success_response_includes_vnext_envelope() -> None:
    """HLS stop success responses expose API vNext envelope fields."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.front", "stop")

    assert result.status == 200
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {"success": True, "action": "stopped"}


@pytest.mark.asyncio
async def test_camera_hls_stop_success_response_matches_api_vnext_fixture() -> None:
    """Camera HLS stop success full response remains stable for legacy and vNext clients."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.front", "stop")

    assert result.status == 200
    assert result.body == _fixture("camera-hls-stop.json")


@pytest.mark.asyncio
async def test_camera_hls_stop_not_found_response_includes_vnext_envelope() -> None:
    """HLS stop not-found responses expose API vNext envelope fields."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.back", "stop")

    assert result.status == 404
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {"success": False, "action": "stopped"}


@pytest.mark.asyncio
async def test_camera_hls_stop_not_found_response_matches_api_vnext_fixture() -> None:
    """Camera HLS stop 404 full response remains stable for legacy and vNext clients."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.back", "stop")

    assert result.status == 404
    assert result.body == _fixture("camera-hls-stop-not-found.json")


@pytest.mark.asyncio
async def test_camera_hls_unknown_action_response_includes_vnext_envelope() -> None:
    """HLS unknown-action responses expose API vNext envelope fields."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.front", "bad_action")

    assert result.status == 400
    _assert_vnext_only_top_level(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "UNKNOWN_ACTION",
            "message": "unknown action",
            "target": "camera",
            "retryable": False,
        }
    ]


@pytest.mark.asyncio
async def test_camera_hls_unknown_action_response_matches_api_vnext_fixture() -> None:
    """Camera HLS unknown-action response remains stable for legacy clients."""
    result = await CameraHLSUseCase(FakeCameraGateway()).execute("camera.front", "bad_action")

    assert result.status == 400
    assert result.body == _fixture("camera-hls-unknown-action.json")


@pytest.mark.asyncio
async def test_camera_snapshot_use_case_returns_snapshot_payload_and_headers() -> None:
    """Snapshot use case translates a camera snapshot into an application response."""
    gateway = FakeCameraGateway()

    result = await CameraSnapshotUseCase(gateway).execute(
        "camera.front",
        force_refresh=True,
        if_none_match='"old-etag"',
    )

    assert result.status == 200
    legacy_body = {
        key: value
        for key, value in result.body.items()
        if key not in {"schema_version", "data", "warnings", "errors"}
    }
    assert legacy_body == {"snapshot": gateway.snapshot}
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == legacy_body
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.headers == {
        "ETag": '"snapshot-etag"',
        "Cache-Control": "private, max-age=10",
        "X-Snapshot-Timestamp": "123.45",
    }
    assert gateway.snapshot_requested == ("camera.front", True, '"old-etag"')


@pytest.mark.asyncio
async def test_camera_snapshot_response_matches_api_vnext_fixture() -> None:
    """Camera snapshot full response remains stable for legacy and vNext clients."""
    result = await CameraSnapshotUseCase(FakeCameraGateway()).execute(
        "camera.front",
        force_refresh=True,
        if_none_match='"old-etag"',
    )

    assert result.status == 200
    assert _serializable_camera_body(result.body) == _fixture("camera-snapshot.json")


@pytest.mark.asyncio
async def test_camera_snapshot_use_case_returns_not_modified() -> None:
    """Snapshot use case reports conditional cache hits without a payload."""
    gateway = FakeCameraGateway()
    gateway.not_modified = True

    result = await CameraSnapshotUseCase(gateway).execute(
        "camera.front",
        force_refresh=False,
        if_none_match='"snapshot-etag"',
    )

    assert result.status == 304
    assert result.body == {}
    assert result.headers == {"X-Smartly-Response-Mode": "empty"}


@pytest.mark.asyncio
async def test_camera_snapshot_use_case_returns_unavailable_for_missing_snapshot() -> None:
    """Snapshot use case reports unavailable snapshots with API vNext errors."""
    result = await CameraSnapshotUseCase(FakeCameraGateway()).execute(
        "camera.missing",
        force_refresh=False,
        if_none_match=None,
    )

    assert result.status == 404
    assert result.body["error"] == "snapshot_unavailable"
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "SNAPSHOT_UNAVAILABLE",
            "message": "snapshot unavailable",
            "target": "camera",
            "retryable": False,
        }
    ]


@pytest.mark.asyncio
async def test_camera_snapshot_unavailable_matches_api_vnext_fixture() -> None:
    """Camera snapshot unavailable response remains stable for legacy and vNext clients."""
    result = await CameraSnapshotUseCase(FakeCameraGateway()).execute(
        "camera.missing",
        force_refresh=False,
        if_none_match=None,
    )

    assert result.status == 404
    assert result.body == _fixture("camera-snapshot-unavailable.json")


def test_camera_stream_use_case_returns_mjpeg_headers() -> None:
    """Stream use case owns the MJPEG response header contract."""
    result = CameraStreamUseCase().execute()

    assert result.status == 200
    assert result.body == {}
    assert result.headers == {
        "Content-Type": "multipart/x-mixed-replace;boundary=frame",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Connection": "close",
        "X-Smartly-Response-Mode": "stream",
    }
