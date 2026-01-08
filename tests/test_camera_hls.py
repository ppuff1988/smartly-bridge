"""Tests for HLS streaming functionality in Camera management."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.camera import (
    CameraManager,
    CameraStreamInfo,
    HLSStreamSession,
    StreamCapability,
)
from custom_components.smartly_bridge.const import (
    DOMAIN,
    HLS_IDLE_TIMEOUT,
    STREAM_TYPE_HLS,
    STREAM_TYPE_MJPEG,
)


class TestStreamCapability:
    """Tests for StreamCapability enum."""

    def test_stream_capability_values(self):
        """Test stream capability enum values."""
        assert StreamCapability.SNAPSHOT.value == "snapshot"
        assert StreamCapability.MJPEG.value == "mjpeg"
        assert StreamCapability.HLS.value == "hls"
        assert StreamCapability.WEBRTC.value == "webrtc"


class TestCameraStreamInfo:
    """Tests for CameraStreamInfo dataclass."""

    def test_stream_info_minimal(self):
        """Test creating stream info with minimal fields."""
        info = CameraStreamInfo(
            entity_id="camera.test",
            name="Test Camera",
        )

        assert info.entity_id == "camera.test"
        assert info.name == "Test Camera"
        assert info.supports_snapshot is False
        assert info.supports_mjpeg is False
        assert info.supports_hls is False
        assert info.supports_webrtc is False
        assert info.hls_url is None
        assert info.mjpeg_url is None
        assert info.is_streaming is False

    def test_stream_info_full(self):
        """Test creating stream info with all capabilities."""
        info = CameraStreamInfo(
            entity_id="camera.front_door",
            name="Front Door Camera",
            supports_snapshot=True,
            supports_mjpeg=True,
            supports_hls=True,
            supports_webrtc=False,
            hls_url="/api/smartly/camera/camera.front_door/stream/hls",
            mjpeg_url="/api/smartly/camera/camera.front_door/stream",
            stream_source="rtsp://camera.local/stream",
            is_streaming=True,
        )

        assert info.supports_snapshot is True
        assert info.supports_hls is True
        assert info.is_streaming is True

    def test_stream_info_to_dict(self):
        """Test converting stream info to dictionary."""
        info = CameraStreamInfo(
            entity_id="camera.test",
            name="Test Camera",
            supports_snapshot=True,
            supports_mjpeg=True,
            supports_hls=True,
            supports_webrtc=False,
            is_streaming=False,
        )

        result = info.to_dict()

        assert result["entity_id"] == "camera.test"
        assert result["name"] == "Test Camera"
        assert result["capabilities"]["snapshot"] is True
        assert result["capabilities"]["mjpeg"] is True
        assert result["capabilities"]["hls"] is True
        assert result["capabilities"]["webrtc"] is False
        assert result["endpoints"]["snapshot"] == "/api/smartly/camera/camera.test/snapshot"
        assert result["endpoints"]["mjpeg"] == "/api/smartly/camera/camera.test/stream"
        assert result["endpoints"]["hls"] == "/api/smartly/camera/camera.test/stream/hls"
        assert result["is_streaming"] is False

    def test_stream_info_to_dict_no_hls(self):
        """Test to_dict when HLS is not supported."""
        info = CameraStreamInfo(
            entity_id="camera.test",
            name="Test Camera",
            supports_snapshot=True,
            supports_mjpeg=True,
            supports_hls=False,
        )

        result = info.to_dict()

        assert result["endpoints"]["hls"] is None
        assert result["endpoints"]["snapshot"] is not None
        assert result["endpoints"]["mjpeg"] is not None


class TestHLSStreamSession:
    """Tests for HLSStreamSession dataclass."""

    def test_session_creation(self):
        """Test creating an HLS stream session."""
        mock_stream = MagicMock()
        now = time.time()

        session = HLSStreamSession(
            entity_id="camera.test",
            stream=mock_stream,
            token="abc123token",
            created_at=now,
            last_access=now,
        )

        assert session.entity_id == "camera.test"
        assert session.stream == mock_stream
        assert session.token == "abc123token"
        assert session.created_at == now

    def test_session_not_idle(self):
        """Test session is not idle when recently accessed."""
        session = HLSStreamSession(
            entity_id="camera.test",
            stream=MagicMock(),
            token="abc123",
            created_at=time.time(),
            last_access=time.time(),
        )

        assert not session.is_idle()

    def test_session_is_idle(self):
        """Test session is idle after timeout."""
        old_time = time.time() - HLS_IDLE_TIMEOUT - 10
        session = HLSStreamSession(
            entity_id="camera.test",
            stream=MagicMock(),
            token="abc123",
            created_at=old_time,
            last_access=old_time,
        )

        assert session.is_idle()

    def test_session_touch(self):
        """Test touching session updates last access time."""
        old_time = time.time() - HLS_IDLE_TIMEOUT - 50  # Past idle timeout
        session = HLSStreamSession(
            entity_id="camera.test",
            stream=MagicMock(),
            token="abc123",
            created_at=old_time,
            last_access=old_time,
        )

        # Session should be idle
        assert session.is_idle()

        # Touch updates last access
        session.touch()

        # Session should no longer be idle
        assert not session.is_idle()

    def test_session_custom_timeout(self):
        """Test session idle check with custom timeout."""
        session = HLSStreamSession(
            entity_id="camera.test",
            stream=MagicMock(),
            token="abc123",
            created_at=time.time(),
            last_access=time.time() - 30,
        )

        # Not idle with 60 second timeout
        assert not session.is_idle(timeout=60.0)

        # Idle with 10 second timeout
        assert session.is_idle(timeout=10.0)


class TestCameraManagerHLS:
    """Tests for CameraManager HLS functionality."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {DOMAIN: {}}
        hass.states = MagicMock()
        hass.config = MagicMock()
        hass.config.components = {"stream", "camera"}
        return hass

    @pytest.fixture
    def camera_manager(self, mock_hass):
        """Create a camera manager for testing."""
        return CameraManager(mock_hass)

    @pytest.mark.asyncio
    async def test_get_stream_info_camera_not_found(self, camera_manager):
        """Test get_stream_info returns None for non-existent camera."""
        camera_manager.hass.states.get.return_value = None

        result = await camera_manager.get_stream_info("camera.nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_stream_info_success(self, camera_manager):
        """Test get_stream_info returns correct info."""
        # Mock camera state
        mock_state = MagicMock()
        mock_state.attributes = {"friendly_name": "Front Door Camera"}
        camera_manager.hass.states.get.return_value = mock_state

        # Mock stream support check
        with patch.object(camera_manager, "_check_stream_support", return_value=True):
            result = await camera_manager.get_stream_info("camera.front_door")

        assert result is not None
        assert result.entity_id == "camera.front_door"
        assert result.name == "Front Door Camera"
        assert result.supports_snapshot is True
        assert result.supports_mjpeg is True
        assert result.supports_hls is True

    @pytest.mark.asyncio
    async def test_check_stream_support_no_component(self, camera_manager):
        """Test stream support check when stream component not loaded."""
        camera_manager.hass.config.components = {"camera"}  # No stream component

        result = await camera_manager._check_stream_support("camera.test")

        assert result is False

    @pytest.mark.asyncio
    async def test_check_stream_support_with_source(self, camera_manager):
        """Test stream support check when camera has stream source."""
        with patch(
            "custom_components.smartly_bridge.camera.CameraManager._check_stream_support"
        ) as mock_check:
            mock_check.return_value = True

            # Re-create manager to use patched method
            await camera_manager._check_stream_support("camera.test")

    @pytest.mark.asyncio
    async def test_start_hls_stream_no_source(self, camera_manager):
        """Test starting HLS stream when no stream source available."""
        # Mock the camera component with no stream source
        mock_camera_component = MagicMock()
        mock_camera_component.async_get_stream_source = AsyncMock(return_value=None)

        # Mock the stream component
        mock_stream_component = MagicMock()
        mock_stream_component.create_stream = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "homeassistant.components.camera": mock_camera_component,
                "homeassistant.components.stream": mock_stream_component,
            },
        ):
            result = await camera_manager.start_hls_stream("camera.test")

        assert result is None

    @pytest.mark.asyncio
    async def test_start_hls_stream_existing_session(self, camera_manager):
        """Test starting HLS stream when session already exists."""
        # Create existing session
        mock_stream = MagicMock()
        existing_session = HLSStreamSession(
            entity_id="camera.test",
            stream=mock_stream,
            token="existing_token",
            created_at=time.time() - 60,
            last_access=time.time() - 30,
        )
        camera_manager._hls_sessions["camera.test"] = existing_session

        result = await camera_manager.start_hls_stream("camera.test")

        assert result is not None
        assert result["token"] == "existing_token"
        # Session should be touched
        assert not existing_session.is_idle()

    @pytest.mark.asyncio
    async def test_stop_hls_stream_success(self, camera_manager):
        """Test stopping an HLS stream."""
        # Create session
        mock_stream = MagicMock()
        mock_stream.stop = AsyncMock()
        session = HLSStreamSession(
            entity_id="camera.test",
            stream=mock_stream,
            token="test_token",
            created_at=time.time(),
            last_access=time.time(),
        )
        camera_manager._hls_sessions["camera.test"] = session

        result = await camera_manager.stop_hls_stream("camera.test")

        assert result is True
        assert "camera.test" not in camera_manager._hls_sessions
        mock_stream.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_hls_stream_not_found(self, camera_manager):
        """Test stopping non-existent HLS stream."""
        result = await camera_manager.stop_hls_stream("camera.nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_hls_session(self, camera_manager):
        """Test getting an HLS session."""
        # Create session
        session = HLSStreamSession(
            entity_id="camera.test",
            stream=MagicMock(),
            token="test_token",
            created_at=time.time(),
            last_access=time.time() - 100,  # Old access time
        )
        camera_manager._hls_sessions["camera.test"] = session

        result = await camera_manager.get_hls_session("camera.test")

        assert result is not None
        assert result.token == "test_token"
        # Session should be touched (last_access updated)
        assert not session.is_idle()

    @pytest.mark.asyncio
    async def test_get_hls_session_not_found(self, camera_manager):
        """Test getting non-existent HLS session."""
        result = await camera_manager.get_hls_session("camera.nonexistent")

        assert result is None

    def test_get_hls_stats_empty(self, camera_manager):
        """Test HLS stats with no active streams."""
        stats = camera_manager.get_hls_stats()

        assert stats["active_streams"] == 0
        assert stats["streams"] == []

    def test_get_hls_stats_with_sessions(self, camera_manager):
        """Test HLS stats with active streams."""
        now = time.time()
        session1 = HLSStreamSession(
            entity_id="camera.front",
            stream=MagicMock(),
            token="token1",
            created_at=now - 120,
            last_access=now - 30,
        )
        session2 = HLSStreamSession(
            entity_id="camera.back",
            stream=MagicMock(),
            token="token2",
            created_at=now - 60,
            last_access=now - 10,
        )
        camera_manager._hls_sessions["camera.front"] = session1
        camera_manager._hls_sessions["camera.back"] = session2

        stats = camera_manager.get_hls_stats()

        assert stats["active_streams"] == 2
        assert len(stats["streams"]) == 2

        # Check stream info
        tokens = [s["token"] for s in stats["streams"]]
        assert "token1" in tokens
        assert "token2" in tokens

    @pytest.mark.asyncio
    async def test_cleanup_idle_hls_sessions(self, camera_manager):
        """Test cleaning up idle HLS sessions."""
        now = time.time()

        # Create one idle and one active session
        idle_stream = MagicMock()
        idle_stream.stop = AsyncMock()
        idle_session = HLSStreamSession(
            entity_id="camera.idle",
            stream=idle_stream,
            token="idle_token",
            created_at=now - 400,
            last_access=now - 350,  # Idle for 350 seconds
        )

        active_stream = MagicMock()
        active_stream.stop = AsyncMock()
        active_session = HLSStreamSession(
            entity_id="camera.active",
            stream=active_stream,
            token="active_token",
            created_at=now - 60,
            last_access=now - 10,  # Recently accessed
        )

        camera_manager._hls_sessions["camera.idle"] = idle_session
        camera_manager._hls_sessions["camera.active"] = active_session

        cleaned = await camera_manager.cleanup_idle_hls_sessions()

        assert cleaned == 1
        assert "camera.idle" not in camera_manager._hls_sessions
        assert "camera.active" in camera_manager._hls_sessions
        idle_stream.stop.assert_called_once()
        active_stream.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_cleans_all_hls_sessions(self, camera_manager):
        """Test that stopping the camera manager cleans up all HLS sessions."""
        # Start the manager
        await camera_manager.start()

        # Create sessions
        stream1 = MagicMock()
        stream1.stop = AsyncMock()
        stream2 = MagicMock()
        stream2.stop = AsyncMock()

        camera_manager._hls_sessions["camera.one"] = HLSStreamSession(
            entity_id="camera.one",
            stream=stream1,
            token="token1",
            created_at=time.time(),
            last_access=time.time(),
        )
        camera_manager._hls_sessions["camera.two"] = HLSStreamSession(
            entity_id="camera.two",
            stream=stream2,
            token="token2",
            created_at=time.time(),
            last_access=time.time(),
        )

        # Stop the manager
        await camera_manager.stop()

        # All sessions should be cleaned up
        assert len(camera_manager._hls_sessions) == 0
        stream1.stop.assert_called_once()
        stream2.stop.assert_called_once()

    def test_build_hls_response(self, camera_manager):
        """Test building HLS response dictionary."""
        session = HLSStreamSession(
            entity_id="camera.test",
            stream=MagicMock(),
            token="test_token_12345",
            created_at=time.time(),
            last_access=time.time(),
        )

        result = camera_manager._build_hls_response(session)

        assert result["entity_id"] == "camera.test"
        assert result["stream_type"] == STREAM_TYPE_HLS
        assert result["token"] == "test_token_12345"
        assert "/api/hls/test_token_12345/master_playlist.m3u8" in result["hls_url"]
        assert "/api/hls/test_token_12345/playlist.m3u8" in result["playlist"]
        assert "/api/hls/test_token_12345/init.mp4" in result["init"]
        assert result["is_active"] is True

    @pytest.mark.asyncio
    async def test_get_camera_with_capabilities(self, camera_manager):
        """Test getting camera with full capabilities."""
        # Mock camera state
        mock_state = MagicMock()
        mock_state.attributes = {"friendly_name": "Test Camera"}
        camera_manager.hass.states.get.return_value = mock_state

        with patch.object(camera_manager, "_check_stream_support", return_value=True):
            result = await camera_manager.get_camera_with_capabilities("camera.test")

        assert result is not None
        assert result["entity_id"] == "camera.test"
        assert "capabilities" in result
        assert "endpoints" in result

    @pytest.mark.asyncio
    async def test_list_cameras_with_capabilities(self, camera_manager):
        """Test listing cameras with capabilities."""
        # Mock camera states
        mock_state1 = MagicMock()
        mock_state1.attributes = {"friendly_name": "Camera 1"}
        mock_state2 = MagicMock()
        mock_state2.attributes = {"friendly_name": "Camera 2"}

        def get_state(entity_id):
            if entity_id == "camera.one":
                return mock_state1
            elif entity_id == "camera.two":
                return mock_state2
            return None

        camera_manager.hass.states.get = get_state

        with patch.object(camera_manager, "_check_stream_support", return_value=True):
            result = await camera_manager.list_cameras_with_capabilities(
                ["camera.one", "camera.two"]
            )

        assert len(result) == 2
        names = [c["name"] for c in result]
        assert "Camera 1" in names
        assert "Camera 2" in names


class TestStreamTypeConstants:
    """Tests for stream type constants."""

    def test_stream_type_mjpeg(self):
        """Test MJPEG stream type constant."""
        assert STREAM_TYPE_MJPEG == "mjpeg"

    def test_stream_type_hls(self):
        """Test HLS stream type constant."""
        assert STREAM_TYPE_HLS == "hls"
