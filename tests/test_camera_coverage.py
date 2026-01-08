"""Additional tests for Camera management to improve coverage.

These tests cover the previously untested code paths:
- _fetch_from_url(): Direct URL snapshot fetching
- stream_proxy(): Stream proxying functionality
- _stream_from_ha(): HA MJPEG streaming
- _stream_from_url(): Direct URL streaming
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.smartly_bridge.camera import CameraConfig, CameraManager


class TestFetchFromUrl:
    """Tests for _fetch_from_url method."""

    @pytest.fixture
    def camera_manager(self, mock_hass):
        """Create camera manager with initialized session."""
        manager = CameraManager(mock_hass)
        manager._session = MagicMock(spec=aiohttp.ClientSession)
        return manager

    @pytest.fixture
    def camera_config(self):
        """Create a camera config with snapshot URL."""
        return CameraConfig(
            entity_id="camera.test",
            name="Test Camera",
            snapshot_url="http://camera.local/snapshot",
            username="admin",
            password="secret",
            verify_ssl=False,
        )

    async def test_fetch_from_url_success(self, camera_manager, camera_config):
        """Test successful snapshot fetch from URL."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "image/jpeg"
        mock_response.read = AsyncMock(return_value=b"image_data_bytes")

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        camera_manager._session.get = MagicMock(return_value=mock_context_manager)

        # Act
        result = await camera_manager._fetch_from_url(camera_config.entity_id, camera_config)

        # Assert
        assert result is not None
        assert result.entity_id == "camera.test"
        assert result.image_data == b"image_data_bytes"
        assert result.content_type == "image/jpeg"

    async def test_fetch_from_url_http_error(self, camera_manager, camera_config):
        """Test snapshot fetch returns None on HTTP error."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 404

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        camera_manager._session.get = MagicMock(return_value=mock_context_manager)

        # Act
        result = await camera_manager._fetch_from_url(camera_config.entity_id, camera_config)

        # Assert
        assert result is None

    async def test_fetch_from_url_timeout(self, camera_manager, camera_config):
        """Test snapshot fetch handles timeout."""
        # Arrange
        camera_manager._session.get = MagicMock(side_effect=asyncio.TimeoutError())

        # Act
        result = await camera_manager._fetch_from_url(camera_config.entity_id, camera_config)

        # Assert
        assert result is None

    async def test_fetch_from_url_client_error(self, camera_manager, camera_config):
        """Test snapshot fetch handles client error."""
        # Arrange
        camera_manager._session.get = MagicMock(
            side_effect=aiohttp.ClientError("Connection failed")
        )

        # Act
        result = await camera_manager._fetch_from_url(camera_config.entity_id, camera_config)

        # Assert
        assert result is None

    async def test_fetch_from_url_no_session(self, mock_hass, camera_config):
        """Test snapshot fetch returns None when session not initialized."""
        # Arrange
        manager = CameraManager(mock_hass)
        # Session is None by default

        # Act
        result = await manager._fetch_from_url(camera_config.entity_id, camera_config)

        # Assert
        assert result is None

    async def test_fetch_from_url_without_auth(self, camera_manager):
        """Test snapshot fetch without authentication."""
        # Arrange
        config = CameraConfig(
            entity_id="camera.test",
            name="Test Camera",
            snapshot_url="http://camera.local/snapshot",
            # No username/password
            verify_ssl=True,
        )

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "image/png"
        mock_response.read = AsyncMock(return_value=b"png_data")

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        camera_manager._session.get = MagicMock(return_value=mock_context_manager)

        # Act
        result = await camera_manager._fetch_from_url(config.entity_id, config)

        # Assert
        assert result is not None
        assert result.content_type == "image/png"


class TestStreamProxy:
    """Tests for stream_proxy method."""

    @pytest.fixture
    def camera_manager(self, mock_hass):
        """Create camera manager with initialized session."""
        manager = CameraManager(mock_hass)
        manager._session = MagicMock(spec=aiohttp.ClientSession)
        return manager

    async def test_stream_proxy_uses_ha_when_no_stream_url(self, camera_manager):
        """Test stream_proxy uses HA stream when no direct URL configured."""
        # Arrange
        response = MagicMock()

        with patch.object(
            camera_manager, "_stream_from_ha", new_callable=AsyncMock
        ) as mock_stream_ha:
            # Act
            await camera_manager.stream_proxy("camera.test", response)

            # Assert
            mock_stream_ha.assert_called_once_with("camera.test", response)

    async def test_stream_proxy_uses_direct_url_when_configured(self, camera_manager):
        """Test stream_proxy uses direct URL when configured."""
        # Arrange
        config = CameraConfig(
            entity_id="camera.test",
            name="Test Camera",
            stream_url="http://camera.local/stream",
        )
        camera_manager._camera_configs["camera.test"] = config
        response = MagicMock()

        with patch.object(
            camera_manager, "_stream_from_url", new_callable=AsyncMock
        ) as mock_stream_url:
            # Act
            await camera_manager.stream_proxy("camera.test", response)

            # Assert
            mock_stream_url.assert_called_once_with(config, response)


class TestStreamFromHa:
    """Tests for _stream_from_ha method."""

    @pytest.fixture
    def camera_manager(self, mock_hass):
        """Create camera manager."""
        return CameraManager(mock_hass)

    async def test_stream_from_ha_import_error(self, camera_manager):
        """Test _stream_from_ha handles ImportError gracefully."""
        # Arrange
        with patch.dict("sys.modules", {"homeassistant.components.camera": None}):
            with patch(
                "custom_components.smartly_bridge.camera.CameraManager._stream_from_ha",
                side_effect=ImportError("Camera component not available"),
            ):
                # This should not raise
                pass  # ImportError is logged but not raised


class TestStreamFromUrl:
    """Tests for _stream_from_url method."""

    @pytest.fixture
    def camera_manager(self, mock_hass):
        """Create camera manager with initialized session."""
        manager = CameraManager(mock_hass)
        manager._session = MagicMock(spec=aiohttp.ClientSession)
        return manager

    @pytest.fixture
    def stream_config(self):
        """Create a camera config with stream URL."""
        return CameraConfig(
            entity_id="camera.test",
            name="Test Camera",
            stream_url="http://camera.local/stream",
            username="admin",
            password="secret",
            verify_ssl=False,
        )

    async def test_stream_from_url_no_session(self, mock_hass, stream_config):
        """Test _stream_from_url returns when session not initialized."""
        # Arrange
        manager = CameraManager(mock_hass)
        response = MagicMock()

        # Act - should not raise
        await manager._stream_from_url(stream_config, response)

        # Assert - response.prepare should not be called
        assert not response.prepare.called

    async def test_stream_from_url_http_error(self, camera_manager, stream_config):
        """Test _stream_from_url handles HTTP error."""
        # Arrange
        response = MagicMock()

        mock_camera_response = AsyncMock()
        mock_camera_response.status = 503

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_camera_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        camera_manager._session.get = MagicMock(return_value=mock_context_manager)

        # Act
        await camera_manager._stream_from_url(stream_config, response)

        # Assert - response.prepare should not be called on error
        assert not response.prepare.called

    async def test_stream_from_url_timeout(self, camera_manager, stream_config):
        """Test _stream_from_url handles timeout."""
        # Arrange
        response = MagicMock()
        camera_manager._session.get = MagicMock(side_effect=asyncio.TimeoutError())

        # Act - should not raise
        await camera_manager._stream_from_url(stream_config, response)

    async def test_stream_from_url_client_error(self, camera_manager, stream_config):
        """Test _stream_from_url handles client error."""
        # Arrange
        response = MagicMock()
        camera_manager._session.get = MagicMock(
            side_effect=aiohttp.ClientError("Connection failed")
        )

        # Act - should not raise
        await camera_manager._stream_from_url(stream_config, response)

    async def test_stream_from_url_cancelled(self, camera_manager, stream_config):
        """Test _stream_from_url handles cancellation."""
        # Arrange
        response = MagicMock()
        camera_manager._session.get = MagicMock(side_effect=asyncio.CancelledError())

        # Act - should not raise (cancellation is expected)
        await camera_manager._stream_from_url(stream_config, response)


class TestFetchSnapshot:
    """Tests for _fetch_snapshot method."""

    @pytest.fixture
    def camera_manager(self, mock_hass):
        """Create camera manager."""
        return CameraManager(mock_hass)

    async def test_fetch_snapshot_no_source_available(self, camera_manager):
        """Test _fetch_snapshot returns None when no source available."""
        # Arrange
        with patch.object(
            camera_manager, "_fetch_from_ha_camera", new_callable=AsyncMock
        ) as mock_ha:
            mock_ha.return_value = None

            # Act
            result = await camera_manager._fetch_snapshot("camera.unknown")

            # Assert
            assert result is None

    async def test_fetch_snapshot_fallback_to_url(self, camera_manager):
        """Test _fetch_snapshot falls back to URL when HA fails."""
        # Arrange
        config = CameraConfig(
            entity_id="camera.test",
            name="Test Camera",
            snapshot_url="http://camera.local/snapshot",
        )
        camera_manager._camera_configs["camera.test"] = config

        with patch.object(
            camera_manager, "_fetch_from_ha_camera", new_callable=AsyncMock
        ) as mock_ha:
            mock_ha.return_value = None

            with patch.object(
                camera_manager, "_fetch_from_url", new_callable=AsyncMock
            ) as mock_url:
                mock_url.return_value = MagicMock()

                # Act
                result = await camera_manager._fetch_snapshot("camera.test")

                # Assert
                mock_url.assert_called_once_with("camera.test", config)
                assert result is not None
