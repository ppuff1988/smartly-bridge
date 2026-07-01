"""Tests for Camera Views."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.application.camera import SMARTLY_API_SCHEMA_VERSION
from custom_components.smartly_bridge.auth import AuthResult, NonceCache, RateLimiter
from custom_components.smartly_bridge.camera import CameraConfig, CameraManager, CameraSnapshot
from custom_components.smartly_bridge.const import DOMAIN
from custom_components.smartly_bridge.domain.models import (
    CameraSnapshot as DomainCameraSnapshot,
    CameraStreamInfo,
)
from custom_components.smartly_bridge.views.camera import (
    SmartlyCameraConfigView,
    SmartlyCameraHLSInfoView,
    SmartlyCameraListView,
    SmartlyCameraSnapshotView,
    SmartlyCameraStreamView,
)


def _api_vnext_fixture(name: str) -> dict:
    """Load an API vNext fixture by filename."""
    fixture_path = Path(__file__).parent / "fixtures" / "api-vnext" / name
    return json.loads(fixture_path.read_text())


class FakeRuntimeCameraGateway:
    """Camera gateway used to verify setup runtime wiring."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.registered: list[dict] = []

    def list_allowed_camera_ids(self) -> list[str]:
        self.calls.append("list_allowed_camera_ids")
        return ["camera.runtime"]

    def get_camera_state(self, entity_id: str) -> dict | None:
        self.calls.append("get_camera_state")
        if entity_id != "camera.runtime":
            return None
        return {
            "entity_id": entity_id,
            "name": "Runtime Camera",
            "state": "idle",
            "is_streaming": False,
            "brand": "Runtime",
            "model": "Gateway",
            "supported_features": 3,
        }

    async def get_stream_info(self, entity_id: str) -> CameraStreamInfo | None:
        self.calls.append("get_stream_info")
        if entity_id != "camera.runtime":
            return None
        return CameraStreamInfo(
            entity_id=entity_id,
            name="Runtime Camera",
            supports_snapshot=True,
            supports_mjpeg=True,
            supports_hls=True,
            supports_webrtc=False,
            is_streaming=False,
        )

    def get_cache_stats(self) -> dict:
        self.calls.append("get_cache_stats")
        return {"cached_snapshots": 1}

    def get_hls_stats(self) -> dict:
        self.calls.append("get_hls_stats")
        return {"active_streams": 1}

    def register_camera(self, config: dict) -> None:
        self.calls.append("register_camera")
        self.registered.append(config)

    def unregister_camera(self, entity_id: str) -> None:
        self.calls.append("unregister_camera")

    async def clear_cache(self, entity_id: str | None = None) -> int:
        self.calls.append("clear_cache")
        return 1

    def list_registered_cameras(self) -> list[dict]:
        self.calls.append("list_registered_cameras")
        return [{"entity_id": "camera.runtime", "name": "Runtime Camera"}]

    async def get_snapshot(
        self,
        entity_id: str,
        force_refresh: bool = False,
        if_none_match: str | None = None,
    ) -> tuple[DomainCameraSnapshot | None, bool]:
        self.calls.append("get_snapshot")
        return (
            DomainCameraSnapshot(
                entity_id=entity_id,
                image_data=b"runtime-image",
                content_type="image/jpeg",
                timestamp=123.45,
                etag="runtime-etag",
            ),
            False,
        )

    async def start_hls_stream(self, entity_id: str) -> dict | None:
        self.calls.append("start_hls_stream")
        return {"playlist_url": "/api/hls/runtime.m3u8", "entity_id": entity_id}

    async def stop_hls_stream(self, entity_id: str) -> bool:
        self.calls.append("stop_hls_stream")
        return entity_id == "camera.runtime"

    async def stream_proxy(self, entity_id, request, response) -> None:
        self.calls.append("stream_proxy")
        self.streamed = (entity_id, request, response)


class TestSmartlyCameraSnapshotView:
    """Tests for SmartlyCameraSnapshotView."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                        "trust_proxy": "off",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": RateLimiter(60, 60),
                "camera_manager": None,
            }
        }
        return hass

    @pytest.fixture
    def mock_request(self, mock_hass):
        """Create mock request."""
        request = MagicMock()
        request.app = {"hass": mock_hass}
        request.headers = {"X-Client-Id": "test_client"}
        request.match_info = {"entity_id": "camera.test"}
        request.query = {}
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        request.read = AsyncMock(return_value=b"")
        return request

    @pytest.mark.asyncio
    async def test_invalid_entity_id(self, mock_request):
        """Test snapshot view rejects invalid entity_id."""
        mock_request.match_info = {"entity_id": "invalid_entity"}
        view = SmartlyCameraSnapshotView(mock_request)
        response = await view.get()
        assert response.status == 400
        data = json.loads(response.body)
        assert data == {
            "error": "invalid_entity_id",
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": "INVALID_ENTITY_ID",
                    "message": "invalid entity id",
                    "target": "camera.entity_id",
                    "retryable": False,
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_snapshot_invalid_entity_id_matches_api_vnext_fixture(
        self,
        mock_request,
    ):
        """Snapshot invalid entity response remains stable for legacy and vNext clients."""
        mock_request.match_info = {"entity_id": "invalid_entity"}

        response = await SmartlyCameraSnapshotView(mock_request).get()

        assert response.status == 400
        assert json.loads(response.body) == _api_vnext_fixture(
            "camera-snapshot-invalid-entity-id.json"
        )

    @pytest.mark.asyncio
    async def test_integration_not_configured(self, mock_request, mock_hass):
        """Test error when integration not configured."""
        mock_hass.data = {}
        view = SmartlyCameraSnapshotView(mock_request)
        response = await view.get()
        assert response.status == 500
        data = json.loads(response.body)
        assert data == {
            "error": "integration_not_configured",
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": "INTEGRATION_NOT_CONFIGURED",
                    "message": "integration not configured",
                    "target": "camera.config",
                    "retryable": False,
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_snapshot_integration_not_configured_matches_api_vnext_fixture(
        self,
        mock_request,
        mock_hass,
    ):
        """Snapshot integration error response remains stable for legacy and vNext clients."""
        mock_hass.data = {}

        response = await SmartlyCameraSnapshotView(mock_request).get()

        assert response.status == 500
        assert json.loads(response.body) == _api_vnext_fixture(
            "camera-snapshot-integration-not-configured.json"
        )

    @pytest.mark.asyncio
    async def test_auth_failure(self, mock_request, mock_hass):
        """Test authentication failure."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=False, error="invalid_signature")

            view = SmartlyCameraSnapshotView(mock_request)
            response = await view.get()

            assert response.status == 401
            data = json.loads(response.body)
            assert data == {
                "error": "invalid_signature",
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "INVALID_SIGNATURE",
                        "message": "invalid signature",
                        "target": "camera.auth",
                        "retryable": False,
                    }
                ],
            }

    @pytest.mark.asyncio
    async def test_rate_limited(self, mock_request, mock_hass):
        """Test rate limiting."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            # Mock rate limiter to return False
            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=False)

            view = SmartlyCameraSnapshotView(mock_request)
            response = await view.get()

            assert response.status == 429
            assert response.headers["Retry-After"] == "60"
            assert response.headers["X-RateLimit-Remaining"] == "0"
            data = json.loads(response.body)
            assert data == {
                "error": "rate_limited",
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "RATE_LIMITED",
                        "message": "rate limited",
                        "target": "camera.rate_limit",
                        "retryable": False,
                    }
                ],
            }

    @pytest.mark.asyncio
    async def test_entity_not_allowed(self, mock_request, mock_hass):
        """Test entity not in allowed list."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=False,
            ):
                view = SmartlyCameraSnapshotView(mock_request)
                response = await view.get()

                assert response.status == 403
                data = json.loads(response.body)
                assert data == {
                    "error": "entity_not_allowed",
                    "schema_version": SMARTLY_API_SCHEMA_VERSION,
                    "data": {"status": "rejected"},
                    "warnings": [],
                    "errors": [
                        {
                            "code": "ENTITY_NOT_ALLOWED",
                            "message": "entity not allowed",
                            "target": "camera.entity_id",
                            "retryable": False,
                        }
                    ],
                }

    @pytest.mark.asyncio
    async def test_camera_manager_not_initialized(self, mock_request, mock_hass):
        """Test error when camera manager not initialized."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=True,
            ):
                view = SmartlyCameraSnapshotView(mock_request)
                response = await view.get()

                assert response.status == 500
                data = json.loads(response.body)
                assert data == {
                    "error": "camera_manager_not_initialized",
                    "schema_version": SMARTLY_API_SCHEMA_VERSION,
                    "data": {"status": "rejected"},
                    "warnings": [],
                    "errors": [
                        {
                            "code": "CAMERA_MANAGER_NOT_INITIALIZED",
                            "message": "camera manager not initialized",
                            "target": "camera.manager",
                            "retryable": False,
                        }
                    ],
                }

    @pytest.mark.asyncio
    async def test_successful_snapshot_with_etag_match(self, mock_request, mock_hass):
        """Test successful snapshot with ETag match (304 Not Modified)."""
        camera_manager = CameraManager(mock_hass)
        mock_hass.data[DOMAIN]["camera_manager"] = camera_manager

        # Mock camera manager to return not modified
        camera_manager.get_snapshot = AsyncMock(return_value=(None, True))

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=True,
            ):
                mock_request.headers["If-None-Match"] = "etag123"

                view = SmartlyCameraSnapshotView(mock_request)
                response = await view.get()

                assert response.status == 304
                assert response.headers["X-Smartly-Response-Mode"] == "empty"

    @pytest.mark.asyncio
    async def test_successful_snapshot(self, mock_request, mock_hass):
        """Test successful snapshot retrieval."""
        import time

        camera_manager = CameraManager(mock_hass)
        mock_hass.data[DOMAIN]["camera_manager"] = camera_manager

        # Create mock snapshot
        snapshot = CameraSnapshot(
            entity_id="camera.test",
            image_data=b"test_image",
            content_type="image/jpeg",
            timestamp=time.time(),
            etag="etag123",
        )

        camera_manager.get_snapshot = AsyncMock(return_value=(snapshot, False))

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=True,
            ):
                view = SmartlyCameraSnapshotView(mock_request)
                response = await view.get()

                assert response.status == 200
                assert response.body == b"test_image"
                assert response.content_type == "image/jpeg"
                assert "etag123" in response.headers["ETag"]

    @pytest.mark.asyncio
    async def test_snapshot_uses_setup_runtime_gateway(self, mock_request, mock_hass):
        """Snapshot requests execute through the setup-created camera gateway."""
        gateway = FakeRuntimeCameraGateway()
        mock_hass.data[DOMAIN]["camera_manager"] = MagicMock()
        mock_hass.data[DOMAIN]["runtime_adapters"] = {"camera_gateway": gateway}

        with (
            patch(
                "custom_components.smartly_bridge.views.camera.verify_request",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=True,
            ),
            patch(
                "custom_components.smartly_bridge.views.camera.HomeAssistantCameraGateway",
            ) as gateway_cls,
        ):
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            response = await SmartlyCameraSnapshotView(mock_request).get()

        assert response.status == 200
        assert response.body == b"runtime-image"
        assert response.headers["ETag"] == "runtime-etag"
        assert gateway.calls == ["get_snapshot"]
        gateway_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_snapshot_unavailable(self, mock_request, mock_hass):
        """Test snapshot unavailable."""
        camera_manager = CameraManager(mock_hass)
        mock_hass.data[DOMAIN]["camera_manager"] = camera_manager

        camera_manager.get_snapshot = AsyncMock(return_value=(None, False))

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=True,
            ):
                view = SmartlyCameraSnapshotView(mock_request)
                response = await view.get()

                assert response.status == 404
                data = json.loads(response.body)
                assert data["error"] == "snapshot_unavailable"

    @pytest.mark.asyncio
    async def test_force_refresh_query(self, mock_request, mock_hass):
        """Test force refresh with query parameter."""
        import time

        camera_manager = CameraManager(mock_hass)
        mock_hass.data[DOMAIN]["camera_manager"] = camera_manager

        snapshot = CameraSnapshot(
            entity_id="camera.test",
            image_data=b"fresh_image",
            content_type="image/jpeg",
            timestamp=time.time(),
            etag="new_etag",
        )

        camera_manager.get_snapshot = AsyncMock(return_value=(snapshot, False))

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=True,
            ):
                mock_request.query = {"refresh": "true"}

                view = SmartlyCameraSnapshotView(mock_request)
                response = await view.get()

                assert response.status == 200
                # Verify force_refresh was called
                camera_manager.get_snapshot.assert_called_once_with(
                    "camera.test",
                    force_refresh=True,
                    if_none_match=None,
                )


class TestSmartlyCameraStreamView:
    """Tests for SmartlyCameraStreamView."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                        "trust_proxy": "off",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": RateLimiter(60, 60),
                "camera_manager": None,
            }
        }
        return hass

    @pytest.fixture
    def mock_request(self, mock_hass):
        """Create mock request."""
        request = MagicMock()
        request.app = {"hass": mock_hass}
        request.headers = {"X-Client-Id": "test_client"}
        request.match_info = {"entity_id": "camera.test"}
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        request.read = AsyncMock(return_value=b"")
        return request

    @pytest.mark.asyncio
    async def test_stream_invalid_entity_id(self, mock_request):
        """Test stream view rejects invalid entity_id."""
        mock_request.match_info = {"entity_id": "light.test"}
        view = SmartlyCameraStreamView(mock_request)
        response = await view.get()
        assert response.status == 400
        data = json.loads(response.body)
        assert data == {
            "error": "invalid_entity_id",
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": "INVALID_ENTITY_ID",
                    "message": "invalid entity id",
                    "target": "camera.entity_id",
                    "retryable": False,
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_stream_invalid_entity_id_matches_api_vnext_fixture(self, mock_request):
        """Stream invalid entity response remains stable for legacy and vNext clients."""
        mock_request.match_info = {"entity_id": "light.test"}
        response = await SmartlyCameraStreamView(mock_request).get()

        assert response.status == 400
        assert json.loads(response.body) == _api_vnext_fixture(
            "camera-stream-invalid-entity-id.json"
        )

    @pytest.mark.asyncio
    async def test_stream_auth_failure(self, mock_request):
        """Test stream authentication failure."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=False, error="invalid_signature")

            view = SmartlyCameraStreamView(mock_request)
            response = await view.get()

            assert response.status == 401
            data = json.loads(response.body)
            assert data == {
                "error": "invalid_signature",
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "INVALID_SIGNATURE",
                        "message": "invalid signature",
                        "target": "camera.auth",
                        "retryable": False,
                    }
                ],
            }

    @pytest.mark.asyncio
    async def test_stream_auth_failure_matches_api_vnext_fixture(self, mock_request):
        """Stream auth failure response remains stable for legacy and vNext clients."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=False, error="invalid_signature")

            response = await SmartlyCameraStreamView(mock_request).get()

            assert response.status == 401
            assert json.loads(response.body) == _api_vnext_fixture(
                "camera-stream-auth-failure.json"
            )

    @pytest.mark.asyncio
    async def test_stream_integration_not_configured(self, mock_request, mock_hass):
        """Test stream view returns API vNext envelope when integration is missing."""
        mock_hass.data = {}
        view = SmartlyCameraStreamView(mock_request)
        response = await view.get()

        assert response.status == 500
        data = json.loads(response.body)
        assert data == {
            "error": "integration_not_configured",
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": "INTEGRATION_NOT_CONFIGURED",
                    "message": "integration not configured",
                    "target": "camera.config",
                    "retryable": False,
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_stream_integration_not_configured_matches_api_vnext_fixture(
        self,
        mock_request,
        mock_hass,
    ):
        """Stream integration error response remains stable for legacy and vNext clients."""
        mock_hass.data = {}

        response = await SmartlyCameraStreamView(mock_request).get()

        assert response.status == 500
        assert json.loads(response.body) == _api_vnext_fixture(
            "camera-stream-integration-not-configured.json"
        )

    @pytest.mark.asyncio
    async def test_stream_rate_limited(self, mock_request, mock_hass):
        """Test stream rate limiting."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=False)

            view = SmartlyCameraStreamView(mock_request)
            response = await view.get()

            assert response.status == 429
            assert response.headers["Retry-After"] == "60"
            assert response.headers["X-RateLimit-Remaining"] == "0"
            data = json.loads(response.body)
            assert data == {
                "error": "rate_limited",
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "RATE_LIMITED",
                        "message": "rate limited",
                        "target": "camera.rate_limit",
                        "retryable": False,
                    }
                ],
            }

    @pytest.mark.asyncio
    async def test_stream_rate_limited_matches_api_vnext_fixture(
        self,
        mock_request,
        mock_hass,
    ):
        """Stream rate-limit response remains stable for legacy and vNext clients."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=False)

            response = await SmartlyCameraStreamView(mock_request).get()

            assert response.status == 429
            assert response.headers["Retry-After"] == "60"
            assert response.headers["X-RateLimit-Remaining"] == "0"
            assert json.loads(response.body) == _api_vnext_fixture(
                "camera-stream-rate-limited.json"
            )

    @pytest.mark.asyncio
    async def test_stream_entity_not_allowed(self, mock_request, mock_hass):
        """Test stream view returns API vNext envelope when entity is denied."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=False,
            ):
                view = SmartlyCameraStreamView(mock_request)
                response = await view.get()

                assert response.status == 403
                data = json.loads(response.body)
                assert data == {
                    "error": "entity_not_allowed",
                    "schema_version": SMARTLY_API_SCHEMA_VERSION,
                    "data": {"status": "rejected"},
                    "warnings": [],
                    "errors": [
                        {
                            "code": "ENTITY_NOT_ALLOWED",
                            "message": "entity not allowed",
                            "target": "camera.entity_id",
                            "retryable": False,
                        }
                    ],
                }

    @pytest.mark.asyncio
    async def test_stream_entity_not_allowed_matches_api_vnext_fixture(
        self,
        mock_request,
    ):
        """Stream ACL denial response remains stable for legacy and vNext clients."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=False,
            ):
                response = await SmartlyCameraStreamView(mock_request).get()

                assert response.status == 403
                assert json.loads(response.body) == _api_vnext_fixture(
                    "camera-stream-entity-not-allowed.json"
                )

    @pytest.mark.asyncio
    async def test_stream_camera_manager_not_initialized(self, mock_request, mock_hass):
        """Test stream view returns API vNext envelope when manager is missing."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=True,
            ):
                view = SmartlyCameraStreamView(mock_request)
                response = await view.get()

                assert response.status == 500
                data = json.loads(response.body)
                assert data == {
                    "error": "camera_manager_not_initialized",
                    "schema_version": SMARTLY_API_SCHEMA_VERSION,
                    "data": {"status": "rejected"},
                    "warnings": [],
                    "errors": [
                        {
                            "code": "CAMERA_MANAGER_NOT_INITIALIZED",
                            "message": "camera manager not initialized",
                            "target": "camera.manager",
                            "retryable": False,
                        }
                    ],
                }

    @pytest.mark.asyncio
    async def test_stream_camera_manager_not_initialized_matches_api_vnext_fixture(
        self,
        mock_request,
        mock_hass,
    ):
        """Stream manager missing response remains stable for legacy and vNext clients."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=True,
            ):
                response = await SmartlyCameraStreamView(mock_request).get()

                assert response.status == 500
                assert json.loads(response.body) == _api_vnext_fixture(
                    "camera-stream-manager-not-initialized.json"
                )

    @pytest.mark.asyncio
    async def test_stream_uses_setup_runtime_gateway(self, mock_request, mock_hass):
        """MJPEG stream requests execute through the setup-created camera gateway."""
        gateway = FakeRuntimeCameraGateway()
        camera_manager = MagicMock()
        camera_manager.stream_proxy = AsyncMock()
        mock_hass.data[DOMAIN]["camera_manager"] = camera_manager
        mock_hass.data[DOMAIN]["runtime_adapters"] = {"camera_gateway": gateway}
        stream_response = MagicMock()
        stream_response.prepare = AsyncMock()
        stream_response.enable_compression = MagicMock()

        with (
            patch(
                "custom_components.smartly_bridge.views.camera.verify_request",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=True,
            ),
            patch(
                "custom_components.smartly_bridge.views.camera.web.StreamResponse",
                return_value=stream_response,
            ),
        ):
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            response = await SmartlyCameraStreamView(mock_request).get()

        assert response is stream_response
        assert gateway.calls == ["stream_proxy"]
        assert gateway.streamed == ("camera.test", mock_request, stream_response)
        camera_manager.stream_proxy.assert_not_awaited()


class TestSmartlyCameraListView:
    """Tests for SmartlyCameraListView."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        camera_manager = CameraManager(hass)

        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                        "trust_proxy": "off",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": RateLimiter(60, 60),
                "camera_manager": camera_manager,
            }
        }
        return hass

    @pytest.fixture
    def mock_request(self, mock_hass):
        """Create mock request."""
        request = MagicMock()
        request.app = {"hass": mock_hass}
        request.headers = {"X-Client-Id": "test_client"}
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        request.read = AsyncMock(return_value=b"")
        return request

    @pytest.mark.asyncio
    async def test_list_integration_not_configured(self, mock_request, mock_hass):
        """Test list view returns API vNext envelope when integration is missing."""
        mock_hass.data = {}
        view = SmartlyCameraListView(mock_request)
        response = await view.get()
        assert response.status == 500
        data = json.loads(response.body)
        assert data == {
            "error": "integration_not_configured",
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": "INTEGRATION_NOT_CONFIGURED",
                    "message": "integration not configured",
                    "target": "camera.config",
                    "retryable": False,
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_list_auth_failure(self, mock_request):
        """Test list view returns API vNext envelope on authentication failure."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=False, error="invalid_signature")

            view = SmartlyCameraListView(mock_request)
            response = await view.get()

            assert response.status == 401
            data = json.loads(response.body)
            assert data == {
                "error": "invalid_signature",
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "INVALID_SIGNATURE",
                        "message": "invalid signature",
                        "target": "camera.auth",
                        "retryable": False,
                    }
                ],
            }

    @pytest.mark.asyncio
    async def test_list_rate_limited(self, mock_request, mock_hass):
        """Test list view returns API vNext envelope when rate limited."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=False)

            view = SmartlyCameraListView(mock_request)
            response = await view.get()

            assert response.status == 429
            assert response.headers["Retry-After"] == "60"
            assert response.headers["X-RateLimit-Remaining"] == "0"
            data = json.loads(response.body)
            assert data == {
                "error": "rate_limited",
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "RATE_LIMITED",
                        "message": "rate limited",
                        "target": "camera.rate_limit",
                        "retryable": False,
                    }
                ],
            }

    @pytest.mark.asyncio
    async def test_list_success_with_cameras(self, mock_request, mock_hass):
        """Test successful camera list retrieval."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.camera.get_allowed_entities",
                return_value=["camera.front_door", "camera.backyard", "light.kitchen"],
            ):
                # Mock camera states
                mock_state1 = MagicMock()
                mock_state1.state = "idle"
                mock_state1.attributes = {
                    "friendly_name": "Front Door",
                    "is_streaming": False,
                    "brand": "Reolink",
                    "model_name": "RLC-410",
                    "supported_features": 3,
                }

                mock_state2 = MagicMock()
                mock_state2.state = "streaming"
                mock_state2.attributes = {
                    "friendly_name": "Backyard",
                    "is_streaming": True,
                    "brand": None,
                    "model_name": None,
                    "supported_features": 1,
                }

                def get_state(entity_id):
                    if entity_id == "camera.front_door":
                        return mock_state1
                    elif entity_id == "camera.backyard":
                        return mock_state2
                    return None

                mock_hass.states.get = get_state

                view = SmartlyCameraListView(mock_request)
                response = await view.get()

                assert response.status == 200
                data = json.loads(response.body)
                assert data["count"] == 2
                assert len(data["cameras"]) == 2

                # Verify camera data
                camera_ids = [c["entity_id"] for c in data["cameras"]]
                assert "camera.front_door" in camera_ids
                assert "camera.backyard" in camera_ids

    @pytest.mark.asyncio
    async def test_list_uses_setup_runtime_gateway(self, mock_request, mock_hass):
        """Camera list requests execute through the setup-created camera gateway."""
        gateway = FakeRuntimeCameraGateway()
        mock_hass.data[DOMAIN]["runtime_adapters"] = {"camera_gateway": gateway}

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            response = await SmartlyCameraListView(mock_request).get()

        assert response.status == 200
        data = json.loads(response.body)
        assert data["count"] == 1
        assert data["cameras"][0]["entity_id"] == "camera.runtime"
        assert gateway.calls == [
            "list_allowed_camera_ids",
            "get_camera_state",
            "get_cache_stats",
            "get_hls_stats",
        ]

    @pytest.mark.asyncio
    async def test_list_response_includes_request_context_headers(
        self, mock_request, mock_hass
    ):
        """Camera list responses echo optional request correlation headers."""
        gateway = FakeRuntimeCameraGateway()
        mock_hass.data[DOMAIN]["runtime_adapters"] = {"camera_gateway": gateway}
        mock_request.headers = {
            "X-Client-Id": "test_client",
            "X-Request-Id": "req-camera-001",
            "X-Correlation-Id": "corr-camera-001",
        }

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            response = await SmartlyCameraListView(mock_request).get()

        assert response.status == 200
        data = json.loads(response.body)
        assert data["request_id"] == "req-camera-001"
        assert data["correlation_id"] == "corr-camera-001"
        assert data["count"] == 1
        assert data["cameras"][0]["entity_id"] == "camera.runtime"


class TestSmartlyCameraConfigView:
    """Tests for SmartlyCameraConfigView."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        camera_manager = CameraManager(hass)

        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                        "trust_proxy": "off",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": RateLimiter(60, 60),
                "camera_manager": camera_manager,
            }
        }
        return hass

    @pytest.fixture
    def mock_request(self, mock_hass):
        """Create mock request."""
        request = MagicMock()
        request.app = {"hass": mock_hass}
        request.headers = {"X-Client-Id": "test_client"}
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        return request

    @pytest.mark.asyncio
    async def test_config_integration_not_configured(self, mock_request, mock_hass):
        """Test config view returns API vNext envelope when integration is missing."""
        mock_hass.data = {}
        view = SmartlyCameraConfigView(mock_request)
        response = await view.post()

        assert response.status == 500
        data = json.loads(response.body)
        assert data == {
            "error": "integration_not_configured",
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": "INTEGRATION_NOT_CONFIGURED",
                    "message": "integration not configured",
                    "target": "camera.config",
                    "retryable": False,
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_config_auth_failure(self, mock_request):
        """Test config view returns API vNext envelope on authentication failure."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=False, error="invalid_signature")

            view = SmartlyCameraConfigView(mock_request)
            response = await view.post()

            assert response.status == 401
            data = json.loads(response.body)
            assert data == {
                "error": "invalid_signature",
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "INVALID_SIGNATURE",
                        "message": "invalid signature",
                        "target": "camera.auth",
                        "retryable": False,
                    }
                ],
            }

    @pytest.mark.asyncio
    async def test_config_rate_limited(self, mock_request, mock_hass):
        """Test config view returns API vNext envelope when rate limited."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=False)

            view = SmartlyCameraConfigView(mock_request)
            response = await view.post()

            assert response.status == 429
            assert response.headers["Retry-After"] == "60"
            assert response.headers["X-RateLimit-Remaining"] == "0"
            data = json.loads(response.body)
            assert data == {
                "error": "rate_limited",
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "RATE_LIMITED",
                        "message": "rate limited",
                        "target": "camera.rate_limit",
                        "retryable": False,
                    }
                ],
            }

    @pytest.mark.asyncio
    async def test_config_invalid_json(self, mock_request):
        """Test config view returns API vNext envelope on invalid JSON."""
        mock_request.json = AsyncMock(side_effect=json.JSONDecodeError("test", "", 0))
        mock_request.read = AsyncMock(return_value=b"invalid json")

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            view = SmartlyCameraConfigView(mock_request)
            response = await view.post()

            assert response.status == 400
            data = json.loads(response.body)
            assert data == {
                "error": "invalid_json",
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "INVALID_JSON",
                        "message": "invalid json",
                        "target": "camera.request",
                        "retryable": False,
                    }
                ],
            }

    @pytest.mark.asyncio
    async def test_config_missing_action(self, mock_request):
        """Test config view returns API vNext envelope with missing action."""
        mock_request.json = AsyncMock(return_value={})

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            view = SmartlyCameraConfigView(mock_request)
            response = await view.post()

            assert response.status == 400
            data = json.loads(response.body)
            assert data == {
                "error": "missing_action",
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "MISSING_ACTION",
                        "message": "missing action",
                        "target": "camera.action",
                        "retryable": False,
                    }
                ],
            }

    @pytest.mark.asyncio
    async def test_config_camera_manager_not_initialized(self, mock_request, mock_hass):
        """Test config view returns API vNext envelope without camera manager."""
        mock_hass.data[DOMAIN]["camera_manager"] = None
        mock_request.json = AsyncMock(return_value={"action": "list"})

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            view = SmartlyCameraConfigView(mock_request)
            response = await view.post()

            assert response.status == 500
            data = json.loads(response.body)
            assert data == {
                "error": "camera_manager_not_initialized",
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "CAMERA_MANAGER_NOT_INITIALIZED",
                        "message": "camera manager not initialized",
                        "target": "camera.manager",
                        "retryable": False,
                    }
                ],
            }

    @pytest.mark.asyncio
    async def test_config_register_camera(self, mock_request, mock_hass):
        """Test registering a camera."""
        mock_request.json = AsyncMock(
            return_value={
                "action": "register",
                "entity_id": "camera.new",
                "name": "New Camera",
                "snapshot_url": "http://camera.local/snapshot",
                "stream_url": "http://camera.local/stream",
            }
        )

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            view = SmartlyCameraConfigView(mock_request)
            response = await view.post()

            assert response.status == 200
            data = json.loads(response.body)
            assert data["success"] is True
            assert data["action"] == "registered"
            assert data["entity_id"] == "camera.new"

    @pytest.mark.asyncio
    async def test_config_register_uses_setup_runtime_gateway(self, mock_request, mock_hass):
        """Camera config requests execute through the setup-created camera gateway."""
        gateway = FakeRuntimeCameraGateway()
        mock_hass.data[DOMAIN]["runtime_adapters"] = {"camera_gateway": gateway}
        mock_request.json = AsyncMock(
            return_value={
                "action": "register",
                "entity_id": "camera.runtime",
                "name": "Runtime Camera",
            }
        )

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            response = await SmartlyCameraConfigView(mock_request).post()

        assert response.status == 200
        data = json.loads(response.body)
        assert data["action"] == "registered"
        assert gateway.calls == ["register_camera"]
        assert gateway.registered[0]["entity_id"] == "camera.runtime"

    @pytest.mark.asyncio
    async def test_config_register_missing_entity_id(self, mock_request):
        """Test register with missing entity_id."""
        mock_request.json = AsyncMock(return_value={"action": "register"})

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            view = SmartlyCameraConfigView(mock_request)
            response = await view.post()

            assert response.status == 400
            data = json.loads(response.body)
            assert data["error"] == "missing_entity_id"

    @pytest.mark.asyncio
    async def test_config_unregister_camera(self, mock_request, mock_hass):
        """Test unregistering a camera."""
        # First register a camera
        camera_manager = mock_hass.data[DOMAIN]["camera_manager"]
        config = CameraConfig(entity_id="camera.old", name="Old Camera")
        camera_manager.register_camera(config)

        mock_request.json = AsyncMock(
            return_value={
                "action": "unregister",
                "entity_id": "camera.old",
            }
        )

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            view = SmartlyCameraConfigView(mock_request)
            response = await view.post()

            assert response.status == 200
            data = json.loads(response.body)
            assert data["success"] is True
            assert data["action"] == "unregistered"

    @pytest.mark.asyncio
    async def test_config_clear_cache(self, mock_request, mock_hass):
        """Test clearing camera cache."""
        mock_request.json = AsyncMock(
            return_value={
                "action": "clear_cache",
                "entity_id": "camera.test",
            }
        )

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            view = SmartlyCameraConfigView(mock_request)
            response = await view.post()

            assert response.status == 200
            data = json.loads(response.body)
            assert data["success"] is True
            assert data["action"] == "cache_cleared"

    @pytest.mark.asyncio
    async def test_config_list_cameras(self, mock_request, mock_hass):
        """Test listing cameras via config endpoint."""
        # Register a camera
        camera_manager = mock_hass.data[DOMAIN]["camera_manager"]
        config = CameraConfig(entity_id="camera.test", name="Test Camera")
        camera_manager.register_camera(config)

        mock_request.json = AsyncMock(return_value={"action": "list"})

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            view = SmartlyCameraConfigView(mock_request)
            response = await view.post()

            assert response.status == 200
            data = json.loads(response.body)
            assert data["count"] == 1
            assert len(data["cameras"]) == 1

    @pytest.mark.asyncio
    async def test_config_unknown_action(self, mock_request):
        """Test config view with unknown action."""
        mock_request.json = AsyncMock(return_value={"action": "unknown_action"})

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            view = SmartlyCameraConfigView(mock_request)
            response = await view.post()

            assert response.status == 400
            data = json.loads(response.body)
            assert data["error"] == "unknown_action"


class TestSmartlyCameraHLSInfoView:
    """Tests for SmartlyCameraHLSInfoView."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        return hass

    @pytest.fixture
    def mock_request(self, mock_hass):
        """Create mock request."""
        request = MagicMock()
        request.app = {"hass": mock_hass}
        request.headers = {"X-Client-Id": "test_client"}
        request.match_info = {"entity_id": "invalid_entity"}
        request.query = {}
        return request

    @pytest.mark.asyncio
    async def test_hls_invalid_entity_id(self, mock_request):
        """Test HLS view returns API vNext envelope for invalid entity_id."""
        view = SmartlyCameraHLSInfoView(mock_request)
        response = await view.get()

        assert response.status == 400
        data = json.loads(response.body)
        assert data == {
            "error": "invalid_entity_id",
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": "INVALID_ENTITY_ID",
                    "message": "invalid entity id",
                    "target": "camera.entity_id",
                    "retryable": False,
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_hls_integration_not_configured(self, mock_request):
        """Test HLS view returns API vNext envelope when integration is missing."""
        mock_request.match_info = {"entity_id": "camera.test"}

        view = SmartlyCameraHLSInfoView(mock_request)
        response = await view.get()

        assert response.status == 500
        data = json.loads(response.body)
        assert data == {
            "error": "integration_not_configured",
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": "INTEGRATION_NOT_CONFIGURED",
                    "message": "integration not configured",
                    "target": "camera.config",
                    "retryable": False,
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_hls_auth_failure(self, mock_request, mock_hass):
        """Test HLS view returns API vNext envelope on authentication failure."""
        mock_request.match_info = {"entity_id": "camera.test"}
        mock_hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                        "trust_proxy": "off",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": RateLimiter(60, 60),
            }
        }

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=False, error="invalid_signature")

            view = SmartlyCameraHLSInfoView(mock_request)
            response = await view.get()

            assert response.status == 401
            data = json.loads(response.body)
            assert data == {
                "error": "invalid_signature",
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "INVALID_SIGNATURE",
                        "message": "invalid signature",
                        "target": "camera.auth",
                        "retryable": False,
                    }
                ],
            }

    @pytest.mark.asyncio
    async def test_hls_rate_limited(self, mock_request, mock_hass):
        """Test HLS view returns API vNext envelope when rate limited."""
        mock_request.match_info = {"entity_id": "camera.test"}
        rate_limiter = RateLimiter(60, 60)
        rate_limiter.check = AsyncMock(return_value=False)
        mock_hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                        "trust_proxy": "off",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": rate_limiter,
            }
        }

        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            view = SmartlyCameraHLSInfoView(mock_request)
            response = await view.get()

            assert response.status == 429
            assert response.headers["Retry-After"] == "60"
            assert response.headers["X-RateLimit-Remaining"] == "0"
            data = json.loads(response.body)
            assert data == {
                "error": "rate_limited",
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "RATE_LIMITED",
                        "message": "rate limited",
                        "target": "camera.rate_limit",
                        "retryable": False,
                    }
                ],
            }

    @pytest.mark.asyncio
    async def test_hls_entity_not_allowed(self, mock_request, mock_hass):
        """Test HLS view returns API vNext envelope when entity is denied."""
        mock_request.match_info = {"entity_id": "camera.test"}
        rate_limiter = RateLimiter(60, 60)
        rate_limiter.check = AsyncMock(return_value=True)
        mock_hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                        "trust_proxy": "off",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": rate_limiter,
            }
        }

        with (
            patch(
                "custom_components.smartly_bridge.views.camera.verify_request",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=False,
            ),
        ):
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            view = SmartlyCameraHLSInfoView(mock_request)
            response = await view.get()

            assert response.status == 403
            data = json.loads(response.body)
            assert data == _api_vnext_fixture("camera-hls-view-entity-not-allowed.json")

    @pytest.mark.asyncio
    async def test_hls_camera_manager_not_initialized(self, mock_request, mock_hass):
        """Test HLS view returns API vNext envelope without camera manager."""
        mock_request.match_info = {"entity_id": "camera.test"}
        rate_limiter = RateLimiter(60, 60)
        rate_limiter.check = AsyncMock(return_value=True)
        mock_hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                        "trust_proxy": "off",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": rate_limiter,
                "camera_manager": None,
            }
        }

        with (
            patch(
                "custom_components.smartly_bridge.views.camera.verify_request",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=True,
            ),
        ):
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            view = SmartlyCameraHLSInfoView(mock_request)
            response = await view.get()

            assert response.status == 500
            data = json.loads(response.body)
            assert data == _api_vnext_fixture("camera-hls-view-manager-not-initialized.json")

    @pytest.mark.asyncio
    async def test_hls_start_uses_setup_runtime_gateway(self, mock_request, mock_hass):
        """HLS requests execute through the setup-created camera gateway."""
        gateway = FakeRuntimeCameraGateway()
        mock_request.match_info = {"entity_id": "camera.runtime"}
        mock_request.query = {}
        rate_limiter = RateLimiter(60, 60)
        rate_limiter.check = AsyncMock(return_value=True)
        mock_hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                        "trust_proxy": "off",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": rate_limiter,
                "camera_manager": MagicMock(),
                "runtime_adapters": {"camera_gateway": gateway},
            }
        }

        with (
            patch(
                "custom_components.smartly_bridge.views.camera.verify_request",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "custom_components.smartly_bridge.views.camera.is_entity_allowed",
                return_value=True,
            ),
        ):
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            response = await SmartlyCameraHLSInfoView(mock_request).get()

        assert response.status == 200
        data = json.loads(response.body)
        assert data["playlist_url"] == "/api/hls/runtime.m3u8"
        assert data["entity_id"] == "camera.runtime"
        assert gateway.calls == ["start_hls_stream"]
