"""Camera application use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..domain.models import BridgeResponse
from .ports import CameraGatewayPort

SMARTLY_API_SCHEMA_VERSION = "2026.06"


@dataclass(frozen=True)
class CameraConfigCommand:
    """Camera configuration command requested by Platform."""

    action: str
    entity_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


class CameraListUseCase:
    """Return Platform-visible cameras."""

    def __init__(self, gateway: CameraGatewayPort) -> None:
        self._gateway = gateway

    async def execute(self, *, include_capabilities: bool = False) -> BridgeResponse:
        """Return allowed camera state metadata."""
        cameras: list[dict[str, Any]] = []
        for entity_id in self._gateway.list_allowed_camera_ids():
            camera_info = self._gateway.get_camera_state(entity_id)
            if camera_info is None:
                continue

            if include_capabilities:
                stream_info = await self._gateway.get_stream_info(entity_id)
                if stream_info is not None:
                    camera_info["capabilities"] = stream_info.capabilities_dict()
                    camera_info["endpoints"] = stream_info.endpoints_dict()

            cameras.append(camera_info)

        body = {
            "cameras": cameras,
            "count": len(cameras),
            "cache_stats": self._gateway.get_cache_stats(),
            "hls_stats": self._gateway.get_hls_stats(),
        }
        return BridgeResponse(
            {
                **body,
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": body,
                "warnings": [],
                "errors": [],
            },
            status=200,
        )


class CameraConfigUseCase:
    """Handle camera configuration commands."""

    def __init__(self, gateway: CameraGatewayPort) -> None:
        self._gateway = gateway

    async def execute(self, command: CameraConfigCommand) -> BridgeResponse:
        """Execute a camera configuration command."""
        if command.action == "register":
            if not command.entity_id:
                return BridgeResponse({"error": "missing_entity_id"}, status=400)

            config = {
                "entity_id": command.entity_id,
                "name": command.data.get("name", command.entity_id),
                "snapshot_url": command.data.get("snapshot_url"),
                "stream_url": command.data.get("stream_url"),
                "username": command.data.get("username"),
                "password": command.data.get("password"),
                "verify_ssl": command.data.get("verify_ssl", True),
                "extra_headers": command.data.get("extra_headers", {}),
            }
            self._gateway.register_camera(config)
            return _camera_success_response(
                {"success": True, "action": "registered", "entity_id": command.entity_id}
            )

        if command.action == "unregister":
            if not command.entity_id:
                return BridgeResponse({"error": "missing_entity_id"}, status=400)

            self._gateway.unregister_camera(command.entity_id)
            return _camera_success_response(
                {"success": True, "action": "unregistered", "entity_id": command.entity_id}
            )

        if command.action == "clear_cache":
            count = await self._gateway.clear_cache(command.entity_id)
            return _camera_success_response(
                {"success": True, "action": "cache_cleared", "cleared_count": count}
            )

        if command.action == "list":
            cameras = self._gateway.list_registered_cameras()
            return _camera_success_response({"cameras": cameras, "count": len(cameras)})

        return BridgeResponse({"error": "unknown_action"}, status=400)


def _camera_success_response(body: dict[str, Any], *, status: int = 200) -> BridgeResponse:
    """Return a legacy-compatible API vNext camera success response."""
    return BridgeResponse(
        {
            **body,
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": body,
            "warnings": [],
            "errors": [],
        },
        status=status,
    )


def _camera_error_response(
    error: str,
    *,
    status: int,
    message: str | None = None,
    target: str = "camera",
) -> BridgeResponse:
    """Return a legacy-compatible API vNext camera error response."""
    error_message = message or error.replace("_", " ")
    return BridgeResponse(
        {
            "error": error,
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": error.upper(),
                    "message": error_message,
                    "target": target,
                    "retryable": False,
                }
            ],
        },
        status=status,
    )


class CameraSnapshotUseCase:
    """Handle camera snapshot retrieval."""

    def __init__(self, gateway: CameraGatewayPort) -> None:
        self._gateway = gateway

    async def execute(
        self,
        entity_id: str,
        *,
        force_refresh: bool = False,
        if_none_match: str | None = None,
    ) -> BridgeResponse:
        """Return snapshot metadata or cache status."""
        snapshot, not_modified = await self._gateway.get_snapshot(
            entity_id,
            force_refresh=force_refresh,
            if_none_match=if_none_match,
        )

        if not_modified:
            return BridgeResponse({}, status=304)

        if snapshot is None:
            return BridgeResponse({"error": "snapshot_unavailable"}, status=404)

        return BridgeResponse(
            {"snapshot": snapshot},
            status=200,
            headers={
                "ETag": snapshot.etag,
                "Cache-Control": "private, max-age=10",
                "X-Snapshot-Timestamp": str(snapshot.timestamp),
            },
        )


class CameraStreamUseCase:
    """Prepare camera MJPEG stream response metadata."""

    def execute(self) -> BridgeResponse:
        """Return headers required for MJPEG streaming."""
        return BridgeResponse(
            {},
            status=200,
            headers={
                "Content-Type": "multipart/x-mixed-replace;boundary=frame",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Connection": "close",
            },
        )


class CameraHLSUseCase:
    """Handle HLS stream actions."""

    def __init__(self, gateway: CameraGatewayPort) -> None:
        self._gateway = gateway

    async def execute(self, entity_id: str, action: str) -> BridgeResponse:
        """Execute an HLS action."""
        if action == "info":
            stream_info = await self._gateway.get_stream_info(entity_id)
            if stream_info is None:
                return BridgeResponse({"error": "camera_not_found"}, status=404)
            return _camera_success_response(stream_info.to_dict())

        if action == "stop":
            stopped = await self._gateway.stop_hls_stream(entity_id)
            if stopped:
                return _camera_success_response({"success": True, "action": "stopped"})
            return _camera_success_response(
                {"success": stopped, "action": "stopped"},
                status=404,
            )

        if action in ("start", ""):
            hls_info = await self._gateway.start_hls_stream(entity_id)
            if hls_info is None:
                return _camera_error_response("hls_not_supported", status=400)
            return _camera_success_response(hls_info)

        if action == "stats":
            return _camera_success_response(self._gateway.get_hls_stats())

        return BridgeResponse({"error": "unknown_action"}, status=400)
