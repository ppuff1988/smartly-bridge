"""Tests for Camera Views."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web

from custom_components.smartly_bridge.auth import AuthResult, NonceCache, RateLimiter
from custom_components.smartly_bridge.camera import CameraConfig, CameraManager, CameraSnapshot
from custom_components.smartly_bridge.const import DOMAIN
from custom_components.smartly_bridge.views.camera import (
    SmartlyCameraConfigView,
    SmartlyCameraListView,
    SmartlyCameraSnapshotView,
    SmartlyCameraStreamView,
)


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
        assert data["error"] == "invalid_entity_id"

    @pytest.mark.asyncio
    async def test_integration_not_configured(self, mock_request, mock_hass):
        """Test error when integration not configured."""
        mock_hass.data = {}
        view = SmartlyCameraSnapshotView(mock_request)
        response = await view.get()
        assert response.status == 500
        data = json.loads(response.body)
        assert data["error"] == "integration_not_configured"

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
            assert data["error"] == "invalid_signature"

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
            data = json.loads(response.body)
            assert data["error"] == "rate_limited"

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
                assert data["error"] == "entity_not_allowed"

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
                assert data["error"] == "camera_manager_not_initialized"

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
        """Test list error when integration not configured."""
        mock_hass.data = {}
        view = SmartlyCameraListView(mock_request)
        response = await view.get()
        assert response.status == 500

    @pytest.mark.asyncio
    async def test_list_auth_failure(self, mock_request):
        """Test list authentication failure."""
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=False, error="invalid_signature")

            view = SmartlyCameraListView(mock_request)
            response = await view.get()

            assert response.status == 401

    @pytest.mark.asyncio
    async def test_list_rate_limited(self, mock_request, mock_hass):
        """Test list rate limiting."""
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
    async def test_config_invalid_json(self, mock_request):
        """Test config view with invalid JSON."""
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
            assert data["error"] == "invalid_json"

    @pytest.mark.asyncio
    async def test_config_missing_action(self, mock_request):
        """Test config view with missing action."""
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
            assert data["error"] == "missing_action"

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
