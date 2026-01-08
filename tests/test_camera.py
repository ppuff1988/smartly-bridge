"""Tests for Camera management functionality."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.camera import CameraConfig, CameraManager, CameraSnapshot
from custom_components.smartly_bridge.const import CAMERA_CACHE_TTL, DOMAIN


class TestCameraSnapshot:
    """Tests for CameraSnapshot dataclass."""

    def test_snapshot_creation(self):
        """Test creating a camera snapshot."""
        snapshot = CameraSnapshot(
            entity_id="camera.test",
            image_data=b"test_image_data",
            content_type="image/jpeg",
            timestamp=time.time(),
            etag="abc123",
        )

        assert snapshot.entity_id == "camera.test"
        assert snapshot.image_data == b"test_image_data"
        assert snapshot.content_type == "image/jpeg"
        assert snapshot.etag == "abc123"

    def test_snapshot_not_expired(self):
        """Test snapshot is not expired when fresh."""
        snapshot = CameraSnapshot(
            entity_id="camera.test",
            image_data=b"test",
            content_type="image/jpeg",
            timestamp=time.time(),
            etag="abc",
        )

        assert not snapshot.is_expired()

    def test_snapshot_expired(self):
        """Test snapshot is expired after TTL."""
        # Create snapshot with old timestamp
        old_timestamp = time.time() - CAMERA_CACHE_TTL - 1
        snapshot = CameraSnapshot(
            entity_id="camera.test",
            image_data=b"test",
            content_type="image/jpeg",
            timestamp=old_timestamp,
            etag="abc",
        )

        assert snapshot.is_expired()

    def test_snapshot_custom_ttl(self):
        """Test snapshot expiration with custom TTL."""
        # Create snapshot 3 seconds old
        snapshot = CameraSnapshot(
            entity_id="camera.test",
            image_data=b"test",
            content_type="image/jpeg",
            timestamp=time.time() - 3,
            etag="abc",
        )

        # Not expired with 5 second TTL
        assert not snapshot.is_expired(ttl=5.0)

        # Expired with 2 second TTL
        assert snapshot.is_expired(ttl=2.0)


class TestCameraConfig:
    """Tests for CameraConfig dataclass."""

    def test_config_minimal(self):
        """Test creating camera config with minimal fields."""
        config = CameraConfig(
            entity_id="camera.test",
            name="Test Camera",
        )

        assert config.entity_id == "camera.test"
        assert config.name == "Test Camera"
        assert config.snapshot_url is None
        assert config.stream_url is None
        assert config.username is None
        assert config.password is None
        assert config.verify_ssl is True
        assert config.extra_headers == {}

    def test_config_full(self):
        """Test creating camera config with all fields."""
        config = CameraConfig(
            entity_id="camera.test",
            name="Test Camera",
            snapshot_url="http://camera.local/snapshot",
            stream_url="http://camera.local/stream",
            username="admin",
            password="secret",
            verify_ssl=False,
            extra_headers={"Authorization": "Bearer token"},
        )

        assert config.snapshot_url == "http://camera.local/snapshot"
        assert config.stream_url == "http://camera.local/stream"
        assert config.username == "admin"
        assert config.password == "secret"
        assert config.verify_ssl is False
        assert config.extra_headers == {"Authorization": "Bearer token"}


class TestCameraManager:
    """Tests for CameraManager class."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        return hass

    @pytest.fixture
    def camera_manager(self, mock_hass):
        """Create a CameraManager instance."""
        return CameraManager(mock_hass)

    @pytest.mark.asyncio
    async def test_start_stop(self, camera_manager):
        """Test starting and stopping camera manager."""
        await camera_manager.start()

        assert camera_manager._session is not None
        assert camera_manager._cleanup_task is not None

        await camera_manager.stop()

        assert camera_manager._session is None
        assert camera_manager._cleanup_task is None

    @pytest.mark.asyncio
    async def test_register_camera(self, camera_manager):
        """Test registering a camera."""
        await camera_manager.start()

        config = CameraConfig(
            entity_id="camera.test",
            name="Test Camera",
        )
        camera_manager.register_camera(config)

        assert "camera.test" in camera_manager._camera_configs
        assert camera_manager.get_camera_config("camera.test") == config

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_unregister_camera(self, camera_manager):
        """Test unregistering a camera."""
        await camera_manager.start()

        config = CameraConfig(entity_id="camera.test", name="Test Camera")
        camera_manager.register_camera(config)

        # Add a fake cached snapshot
        camera_manager._snapshot_cache["camera.test"] = CameraSnapshot(
            entity_id="camera.test",
            image_data=b"test",
            content_type="image/jpeg",
            timestamp=time.time(),
            etag="abc",
        )

        camera_manager.unregister_camera("camera.test")

        assert "camera.test" not in camera_manager._camera_configs
        assert "camera.test" not in camera_manager._snapshot_cache

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_list_cameras(self, camera_manager):
        """Test listing registered cameras."""
        await camera_manager.start()

        config1 = CameraConfig(
            entity_id="camera.front_door",
            name="Front Door",
            snapshot_url="http://cam1/snapshot",
            stream_url="http://cam1/stream",
        )
        config2 = CameraConfig(
            entity_id="camera.backyard",
            name="Backyard",
            snapshot_url="http://cam2/snapshot",
        )

        camera_manager.register_camera(config1)
        camera_manager.register_camera(config2)

        cameras = camera_manager.list_cameras()

        assert len(cameras) == 2
        assert any(c["entity_id"] == "camera.front_door" for c in cameras)
        assert any(c["entity_id"] == "camera.backyard" for c in cameras)

        front_door = next(c for c in cameras if c["entity_id"] == "camera.front_door")
        assert front_door["has_snapshot"] is True
        assert front_door["has_stream"] is True

        backyard = next(c for c in cameras if c["entity_id"] == "camera.backyard")
        assert backyard["has_snapshot"] is True
        assert backyard["has_stream"] is False

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_get_snapshot_from_cache(self, camera_manager):
        """Test getting snapshot from cache."""
        await camera_manager.start()

        # Pre-populate cache
        cached_snapshot = CameraSnapshot(
            entity_id="camera.test",
            image_data=b"cached_image",
            content_type="image/jpeg",
            timestamp=time.time(),
            etag="cached_etag",
        )
        camera_manager._snapshot_cache["camera.test"] = cached_snapshot

        # Get snapshot (should return cached)
        snapshot, not_modified = await camera_manager.get_snapshot("camera.test")

        assert snapshot is not None
        assert snapshot.image_data == b"cached_image"
        assert not_modified is False

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_get_snapshot_304_not_modified(self, camera_manager):
        """Test 304 Not Modified response when ETag matches."""
        await camera_manager.start()

        # Pre-populate cache
        cached_snapshot = CameraSnapshot(
            entity_id="camera.test",
            image_data=b"cached_image",
            content_type="image/jpeg",
            timestamp=time.time(),
            etag="my_etag",
        )
        camera_manager._snapshot_cache["camera.test"] = cached_snapshot

        # Request with matching ETag
        snapshot, not_modified = await camera_manager.get_snapshot(
            "camera.test",
            if_none_match="my_etag",
        )

        assert not_modified is True

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_get_snapshot_force_refresh(self, camera_manager):
        """Test force refresh bypasses cache."""
        await camera_manager.start()

        # Pre-populate cache
        cached_snapshot = CameraSnapshot(
            entity_id="camera.test",
            image_data=b"old_image",
            content_type="image/jpeg",
            timestamp=time.time(),
            etag="old_etag",
        )
        camera_manager._snapshot_cache["camera.test"] = cached_snapshot

        # Mock the fetch method to return new image
        with patch.object(
            camera_manager,
            "_fetch_snapshot",
            new_callable=AsyncMock,
        ) as mock_fetch:
            new_snapshot = CameraSnapshot(
                entity_id="camera.test",
                image_data=b"new_image",
                content_type="image/jpeg",
                timestamp=time.time(),
                etag="new_etag",
            )
            mock_fetch.return_value = new_snapshot

            snapshot, not_modified = await camera_manager.get_snapshot(
                "camera.test",
                force_refresh=True,
            )

            assert snapshot.image_data == b"new_image"
            assert not_modified is False
            mock_fetch.assert_called_once()

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_clear_cache_single(self, camera_manager):
        """Test clearing cache for a single camera."""
        await camera_manager.start()

        # Add multiple cached snapshots
        for i in range(3):
            camera_manager._snapshot_cache[f"camera.test_{i}"] = CameraSnapshot(
                entity_id=f"camera.test_{i}",
                image_data=b"test",
                content_type="image/jpeg",
                timestamp=time.time(),
                etag=f"etag_{i}",
            )

        # Clear one camera
        count = await camera_manager.clear_cache("camera.test_1")

        assert count == 1
        assert "camera.test_1" not in camera_manager._snapshot_cache
        assert "camera.test_0" in camera_manager._snapshot_cache
        assert "camera.test_2" in camera_manager._snapshot_cache

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_clear_cache_all(self, camera_manager):
        """Test clearing all cached snapshots."""
        await camera_manager.start()

        # Add multiple cached snapshots
        for i in range(3):
            camera_manager._snapshot_cache[f"camera.test_{i}"] = CameraSnapshot(
                entity_id=f"camera.test_{i}",
                image_data=b"test",
                content_type="image/jpeg",
                timestamp=time.time(),
                etag=f"etag_{i}",
            )

        # Clear all
        count = await camera_manager.clear_cache()

        assert count == 3
        assert len(camera_manager._snapshot_cache) == 0

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, camera_manager):
        """Test getting cache statistics."""
        await camera_manager.start()

        # Register cameras
        camera_manager.register_camera(CameraConfig(entity_id="camera.test", name="Test"))

        # Add cached snapshot
        camera_manager._snapshot_cache["camera.test"] = CameraSnapshot(
            entity_id="camera.test",
            image_data=b"x" * 1000,
            content_type="image/jpeg",
            timestamp=time.time() - 5,  # 5 seconds ago
            etag="abc",
        )

        stats = camera_manager.get_cache_stats()

        assert stats["cached_snapshots"] == 1
        assert stats["registered_cameras"] == 1
        assert len(stats["cache_entries"]) == 1

        entry = stats["cache_entries"][0]
        assert entry["entity_id"] == "camera.test"
        assert entry["size_bytes"] == 1000
        assert entry["content_type"] == "image/jpeg"
        assert entry["age_seconds"] >= 5

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_cleanup_expired_cache(self, camera_manager):
        """Test automatic cleanup of expired cache entries."""
        await camera_manager.start()

        # Add expired snapshot
        expired_snapshot = CameraSnapshot(
            entity_id="camera.expired",
            image_data=b"old",
            content_type="image/jpeg",
            timestamp=time.time() - CAMERA_CACHE_TTL - 10,  # Expired
            etag="old_etag",
        )
        camera_manager._snapshot_cache["camera.expired"] = expired_snapshot

        # Add fresh snapshot
        fresh_snapshot = CameraSnapshot(
            entity_id="camera.fresh",
            image_data=b"new",
            content_type="image/jpeg",
            timestamp=time.time(),
            etag="new_etag",
        )
        camera_manager._snapshot_cache["camera.fresh"] = fresh_snapshot

        # Trigger cleanup
        await camera_manager._cleanup_expired_cache()

        # Only fresh snapshot should remain
        assert "camera.expired" not in camera_manager._snapshot_cache
        assert "camera.fresh" in camera_manager._snapshot_cache

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_fetch_from_ha_camera(self, camera_manager):
        """Test fetching snapshot from Home Assistant camera entity."""
        await camera_manager.start()

        mock_image = MagicMock()
        mock_image.content = b"ha_camera_image"
        mock_image.content_type = "image/png"

        with patch(
            "homeassistant.components.camera.async_get_image",
            new_callable=AsyncMock,
        ) as mock_get_image:
            mock_get_image.return_value = mock_image

            snapshot = await camera_manager._fetch_from_ha_camera("camera.test")

            assert snapshot is not None
            assert snapshot.image_data == b"ha_camera_image"
            assert snapshot.content_type == "image/png"
            assert snapshot.entity_id == "camera.test"
            mock_get_image.assert_called_once_with(camera_manager.hass, "camera.test")

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_fetch_from_ha_camera_failure(self, camera_manager):
        """Test handling failure when fetching from HA camera."""
        await camera_manager.start()

        with patch(
            "homeassistant.components.camera.async_get_image",
            new_callable=AsyncMock,
        ) as mock_get_image:
            mock_get_image.side_effect = Exception("Camera unavailable")

            snapshot = await camera_manager._fetch_from_ha_camera("camera.test")

            assert snapshot is None

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_fetch_from_url_success(self, camera_manager):
        """Test fetching snapshot from direct URL."""
        await camera_manager.start()

        config = CameraConfig(
            entity_id="camera.test",
            name="Test Camera",
            snapshot_url="http://camera.local/snapshot",
            username="admin",
            password="secret",
        )

        # Mock aiohttp response using context manager pattern
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.content_type = "image/jpeg"
        mock_response.read = AsyncMock(return_value=b"image_data_from_url")

        # Create async context manager mock
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        camera_manager._session.get = MagicMock(return_value=mock_context)

        snapshot = await camera_manager._fetch_from_url("camera.test", config)

        assert snapshot is not None
        assert snapshot.image_data == b"image_data_from_url"
        assert snapshot.content_type == "image/jpeg"

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_fetch_from_url_http_error(self, camera_manager):
        """Test fetching snapshot from URL with HTTP error."""
        await camera_manager.start()

        config = CameraConfig(
            entity_id="camera.test",
            name="Test Camera",
            snapshot_url="http://camera.local/snapshot",
        )

        # Mock aiohttp response with error using context manager pattern
        mock_response = MagicMock()
        mock_response.status = 404

        # Create async context manager mock
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        camera_manager._session.get = MagicMock(return_value=mock_context)

        snapshot = await camera_manager._fetch_from_url("camera.test", config)

        assert snapshot is None

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_fetch_from_url_timeout(self, camera_manager):
        """Test fetching snapshot from URL with timeout."""
        await camera_manager.start()

        config = CameraConfig(
            entity_id="camera.test",
            name="Test Camera",
            snapshot_url="http://camera.local/snapshot",
        )

        # Mock timeout - use MagicMock that raises when entering context
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        camera_manager._session.get = MagicMock(return_value=mock_context)

        snapshot = await camera_manager._fetch_from_url("camera.test", config)

        assert snapshot is None

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_fetch_snapshot_fallback_to_url(self, camera_manager):
        """Test _fetch_snapshot falls back to URL when HA camera fails."""
        await camera_manager.start()

        config = CameraConfig(
            entity_id="camera.test",
            name="Test Camera",
            snapshot_url="http://camera.local/snapshot",
        )
        camera_manager.register_camera(config)

        # Mock HA camera to fail
        with patch.object(
            camera_manager, "_fetch_from_ha_camera", new_callable=AsyncMock
        ) as mock_ha:
            mock_ha.return_value = None

            # Mock URL fetch to succeed
            with patch.object(
                camera_manager, "_fetch_from_url", new_callable=AsyncMock
            ) as mock_url:
                mock_url.return_value = CameraSnapshot(
                    entity_id="camera.test",
                    image_data=b"url_image",
                    content_type="image/jpeg",
                    timestamp=time.time(),
                    etag="url_etag",
                )

                snapshot = await camera_manager._fetch_snapshot("camera.test")

                assert snapshot is not None
                assert snapshot.image_data == b"url_image"
                mock_ha.assert_called_once()
                mock_url.assert_called_once()

        await camera_manager.stop()

    @pytest.mark.asyncio
    async def test_fetch_snapshot_no_source(self, camera_manager):
        """Test _fetch_snapshot when no source is available."""
        await camera_manager.start()

        # Mock HA camera to fail
        with patch.object(
            camera_manager, "_fetch_from_ha_camera", new_callable=AsyncMock
        ) as mock_ha:
            mock_ha.return_value = None

            snapshot = await camera_manager._fetch_snapshot("camera.unknown")

            assert snapshot is None
            mock_ha.assert_called_once()

        await camera_manager.stop()


class TestCameraHTTPEndpoints:
    """Tests for Camera HTTP API endpoints."""

    @pytest.fixture
    def mock_auth_success(self):
        """Create mock for successful authentication."""
        from custom_components.smartly_bridge.auth import AuthResult

        return AuthResult(success=True, client_id="test_client")

    @pytest.fixture
    def mock_auth_failure(self):
        """Create mock for failed authentication."""
        from custom_components.smartly_bridge.auth import AuthResult

        return AuthResult(success=False, error="invalid_signature")

    @pytest.mark.asyncio
    async def test_snapshot_endpoint_invalid_entity_id(self):
        """Test snapshot endpoint rejects invalid entity_id."""
        from custom_components.smartly_bridge.views.camera import SmartlyCameraSnapshotView

        # Create mock request with invalid entity_id
        request = MagicMock()
        request.match_info = {"entity_id": "invalid_entity"}
        request.app = {"hass": MagicMock()}

        view = SmartlyCameraSnapshotView(request)
        response = await view.get()

        assert response.status == 400
        assert b"invalid_entity_id" in response.body

    @pytest.mark.asyncio
    async def test_camera_list_success(self):
        """Test camera list endpoint returns cameras."""
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.camera import CameraManager
        from custom_components.smartly_bridge.views.camera import SmartlyCameraListView

        # Setup mocks
        mock_hass = MagicMock()
        camera_manager = CameraManager(mock_hass)

        mock_hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": RateLimiter(60, 60),
                "camera_manager": camera_manager,
            }
        }

        # Mock entity registry with camera entity
        mock_entry = MagicMock()
        mock_entry.labels = {"smartly"}

        mock_entity_registry = MagicMock()
        mock_entity_registry.entities = {
            "camera.front_door": mock_entry,
        }
        mock_entity_registry.async_get = lambda eid: mock_entity_registry.entities.get(eid)

        # Mock state
        mock_state = MagicMock()
        mock_state.state = "idle"
        mock_state.attributes = {
            "friendly_name": "Front Door Camera",
            "is_streaming": False,
            "brand": "Generic",
            "model_name": "IPCam",
            "supported_features": 3,
        }
        mock_hass.states.get = MagicMock(return_value=mock_state)

        request = MagicMock()
        request.headers = {}
        request.method = "GET"
        request.path = "/api/smartly/camera/list"
        request.app = {"hass": mock_hass}
        request.read = AsyncMock(return_value=b"")
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)

        # Mock successful auth
        with patch(
            "custom_components.smartly_bridge.views.camera.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            from custom_components.smartly_bridge.auth import AuthResult

            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.camera.get_allowed_entities",
                return_value=["camera.front_door"],
            ):
                view = SmartlyCameraListView(request)
                response = await view.get()

                assert response.status == 200
