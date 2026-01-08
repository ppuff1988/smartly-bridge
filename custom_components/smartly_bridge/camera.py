"""IP Camera management for Smartly Bridge.

Provides snapshot caching and streaming proxy functionality for IP cameras.
Supports both MJPEG and HLS streaming formats.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import aiohttp
from aiohttp import ClientTimeout, web

from .const import (
    CAMERA_CACHE_TTL,
    CAMERA_CLEANUP_INTERVAL,
    CAMERA_SNAPSHOT_TIMEOUT,
    CAMERA_STREAM_CHUNK_SIZE,
    CAMERA_STREAM_TIMEOUT,
    HLS_IDLE_TIMEOUT,
    HLS_STREAM_START_TIMEOUT,
    STREAM_TYPE_HLS,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class StreamCapability(Enum):
    """Supported stream capabilities."""

    SNAPSHOT = "snapshot"
    MJPEG = "mjpeg"
    HLS = "hls"
    WEBRTC = "webrtc"  # Future support


@dataclass
class CameraSnapshot:
    """Cached camera snapshot."""

    entity_id: str
    image_data: bytes
    content_type: str
    timestamp: float
    etag: str

    def is_expired(self, ttl: float = CAMERA_CACHE_TTL) -> bool:
        """Check if snapshot cache has expired."""
        return time.time() - self.timestamp > ttl


@dataclass
class CameraConfig:
    """Configuration for an IP camera."""

    entity_id: str
    name: str
    snapshot_url: str | None = None
    stream_url: str | None = None
    username: str | None = None
    password: str | None = None
    verify_ssl: bool = True
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class CameraStreamInfo:
    """Information about camera streaming capabilities."""

    entity_id: str
    name: str
    supports_snapshot: bool = False
    supports_mjpeg: bool = False
    supports_hls: bool = False
    supports_webrtc: bool = False  # Future support
    hls_url: str | None = None
    mjpeg_url: str | None = None
    stream_source: str | None = None
    is_streaming: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "capabilities": {
                "snapshot": self.supports_snapshot,
                "mjpeg": self.supports_mjpeg,
                "hls": self.supports_hls,
                "webrtc": self.supports_webrtc,
            },
            "endpoints": {
                "snapshot": (
                    f"/api/smartly/camera/{self.entity_id}/snapshot"
                    if self.supports_snapshot
                    else None
                ),
                "mjpeg": (
                    f"/api/smartly/camera/{self.entity_id}/stream" if self.supports_mjpeg else None
                ),
                "hls": (
                    f"/api/smartly/camera/{self.entity_id}/stream/hls"
                    if self.supports_hls
                    else None
                ),
            },
            "is_streaming": self.is_streaming,
        }


@dataclass
class HLSStreamSession:
    """Active HLS stream session."""

    entity_id: str
    stream: Any  # homeassistant.components.stream.Stream
    token: str
    created_at: float
    last_access: float

    def is_idle(self, timeout: float = HLS_IDLE_TIMEOUT) -> bool:
        """Check if stream session has been idle too long."""
        return time.time() - self.last_access > timeout

    def touch(self) -> None:
        """Update last access time."""
        self.last_access = time.time()


class CameraManager:
    """Manager for IP camera operations.

    Handles snapshot caching and streaming proxy for IP cameras
    exposed through the Smartly Bridge integration.
    Supports both MJPEG and HLS streaming formats.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the camera manager."""
        self.hass = hass
        self._snapshot_cache: dict[str, CameraSnapshot] = {}
        self._session: aiohttp.ClientSession | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._camera_configs: dict[str, CameraConfig] = {}
        self._hls_sessions: dict[str, HLSStreamSession] = {}
        self._hls_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the camera manager."""
        if self._session is None:
            timeout = ClientTimeout(total=CAMERA_SNAPSHOT_TIMEOUT)
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=2)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            )
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        _LOGGER.info("Camera manager started")

    async def stop(self) -> None:
        """Stop the camera manager."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        if self._session is not None:
            await self._session.close()
            self._session = None

        # Stop all HLS streams
        async with self._hls_lock:
            for session in self._hls_sessions.values():
                try:
                    await session.stream.stop()
                except Exception as ex:
                    _LOGGER.debug("Error stopping HLS stream: %s", ex)
            self._hls_sessions.clear()

        self._snapshot_cache.clear()
        self._camera_configs.clear()
        _LOGGER.info("Camera manager stopped")

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired cache entries.

        Runs in a background task, cleaning up expired snapshots
        at regular intervals defined by CAMERA_CLEANUP_INTERVAL.
        """
        while True:
            await asyncio.sleep(CAMERA_CLEANUP_INTERVAL)
            await self._cleanup_expired_cache()

    async def _cleanup_expired_cache(self) -> None:
        """Remove expired cache entries.

        Iterates through the snapshot cache and removes any entries
        that have exceeded their TTL (Time-To-Live).
        """
        async with self._lock:
            expired = [
                entity_id
                for entity_id, snapshot in self._snapshot_cache.items()
                if snapshot.is_expired()
            ]
            for entity_id in expired:
                del self._snapshot_cache[entity_id]
                _LOGGER.debug("Expired cache for camera: %s", entity_id)

    def register_camera(self, config: CameraConfig) -> None:
        """Register a camera configuration.

        Args:
            config: The camera configuration containing entity_id, URLs, and credentials.
        """
        self._camera_configs[config.entity_id] = config
        _LOGGER.info("Registered camera: %s", config.entity_id)

    def unregister_camera(self, entity_id: str) -> None:
        """Unregister a camera configuration.

        Removes the camera from the configuration registry and clears any cached snapshots.

        Args:
            entity_id: The camera entity ID to unregister (e.g., 'camera.front_door').
        """
        self._camera_configs.pop(entity_id, None)
        self._snapshot_cache.pop(entity_id, None)
        _LOGGER.info("Unregistered camera: %s", entity_id)

    def get_camera_config(self, entity_id: str) -> CameraConfig | None:
        """Get camera configuration by entity_id.

        Args:
            entity_id: The camera entity ID to look up.

        Returns:
            The camera configuration if found, None otherwise.
        """
        return self._camera_configs.get(entity_id)

    def list_cameras(self) -> list[dict[str, Any]]:
        """List all registered cameras.

        Returns:
            A list of dictionaries containing camera information:
                - entity_id: The camera entity ID
                - name: The camera display name
                - has_snapshot: Whether snapshot URL is configured
                - has_stream: Whether stream URL is configured
        """
        return [
            {
                "entity_id": config.entity_id,
                "name": config.name,
                "has_snapshot": config.snapshot_url is not None,
                "has_stream": config.stream_url is not None,
            }
            for config in self._camera_configs.values()
        ]

    async def get_snapshot(
        self,
        entity_id: str,
        force_refresh: bool = False,
        if_none_match: str | None = None,
    ) -> tuple[CameraSnapshot | None, bool]:
        """Get camera snapshot with caching support.

        Args:
            entity_id: The camera entity ID
            force_refresh: Force refresh from camera, ignore cache
            if_none_match: ETag from client for conditional request

        Returns:
            Tuple of (snapshot, not_modified) where not_modified is True
            if the client's cached version is still valid.
        """
        async with self._lock:
            # Check cache first (unless force refresh)
            if not force_refresh and entity_id in self._snapshot_cache:
                cached = self._snapshot_cache[entity_id]
                if not cached.is_expired():
                    # Check if client's cache is still valid
                    if if_none_match and if_none_match == cached.etag:
                        return cached, True  # 304 Not Modified
                    return cached, False

        # Fetch new snapshot
        snapshot = await self._fetch_snapshot(entity_id)
        if snapshot:
            async with self._lock:
                self._snapshot_cache[entity_id] = snapshot
        return snapshot, False

    async def _fetch_snapshot(self, entity_id: str) -> CameraSnapshot | None:
        """Fetch snapshot from camera source."""
        # First try to get from Home Assistant camera entity
        snapshot = await self._fetch_from_ha_camera(entity_id)
        if snapshot:
            return snapshot

        # Fall back to direct URL if configured
        config = self._camera_configs.get(entity_id)
        if config and config.snapshot_url:
            return await self._fetch_from_url(entity_id, config)

        _LOGGER.warning("No snapshot source available for camera: %s", entity_id)
        return None

    async def _fetch_from_ha_camera(self, entity_id: str) -> CameraSnapshot | None:
        """Fetch snapshot from Home Assistant camera entity."""
        try:
            # Use Home Assistant's camera component to get snapshot
            from homeassistant.components.camera import async_get_image

            image = await async_get_image(self.hass, entity_id)
            if image and image.content:
                etag = hashlib.md5(image.content).hexdigest()  # noqa: S324
                return CameraSnapshot(
                    entity_id=entity_id,
                    image_data=image.content,
                    content_type=image.content_type,
                    timestamp=time.time(),
                    etag=etag,
                )
        except ImportError:
            _LOGGER.debug("Camera component not available")
        except Exception as ex:
            _LOGGER.debug("Failed to get snapshot from HA camera %s: %s", entity_id, ex)
        return None

    async def _fetch_from_url(
        self,
        entity_id: str,
        config: CameraConfig,
    ) -> CameraSnapshot | None:
        """Fetch snapshot from direct URL."""
        if self._session is None:
            _LOGGER.error("Camera manager session not initialized")
            return None

        try:
            # Build auth if configured
            auth = None
            if config.username and config.password:
                auth = aiohttp.BasicAuth(config.username, config.password)

            ssl = None if config.verify_ssl else False

            async with self._session.get(
                config.snapshot_url,
                auth=auth,
                ssl=ssl,
                headers=config.extra_headers,
            ) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to fetch snapshot from %s: HTTP %d",
                        config.snapshot_url,
                        response.status,
                    )
                    return None

                image_data = await response.read()
                content_type = response.content_type or "image/jpeg"
                etag = hashlib.md5(image_data).hexdigest()  # noqa: S324

                return CameraSnapshot(
                    entity_id=entity_id,
                    image_data=image_data,
                    content_type=content_type,
                    timestamp=time.time(),
                    etag=etag,
                )
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout fetching snapshot from %s", config.snapshot_url)
        except aiohttp.ClientError as ex:
            _LOGGER.error("Error fetching snapshot from %s: %s", config.snapshot_url, ex)
        return None

    async def stream_proxy(
        self,
        entity_id: str,
        response: web.StreamResponse,
    ) -> None:
        """Proxy camera stream to client.

        This method streams MJPEG or other video content from the camera
        to the client through an aiohttp StreamResponse.

        Args:
            entity_id: The camera entity ID
            response: The aiohttp StreamResponse to write to
        """
        config = self._camera_configs.get(entity_id)

        # Try Home Assistant stream first
        if not config or not config.stream_url:
            await self._stream_from_ha(entity_id, response)
            return

        # Use direct stream URL if configured
        await self._stream_from_url(config, response)

    async def _stream_from_ha(
        self,
        entity_id: str,
        response: web.StreamResponse,
    ) -> None:
        """Stream from Home Assistant camera entity."""
        try:
            from homeassistant.components.camera import async_get_mjpeg_stream

            # Set up MJPEG response headers
            response.content_type = "multipart/x-mixed-replace;boundary=frame"
            if response._req is not None:  # noqa: SLF001
                await response.prepare(response._req)  # noqa: SLF001

            # Get MJPEG stream from HA camera
            # Note: BaseRequest is compatible with Request for this use case
            stream = await async_get_mjpeg_stream(
                self.hass,
                response._req,  # type: ignore[arg-type]  # noqa: SLF001
                entity_id,
            )
            if stream is None:
                _LOGGER.error("Failed to get MJPEG stream for camera: %s", entity_id)
                return

            # Proxy the stream
            async for chunk in stream.iter_chunked(  # type: ignore[attr-defined]
                CAMERA_STREAM_CHUNK_SIZE
            ):
                await response.write(chunk)

        except ImportError:
            _LOGGER.error("Camera streaming component not available")
        except asyncio.CancelledError:
            _LOGGER.debug("Stream cancelled for camera: %s", entity_id)
        except Exception as ex:
            _LOGGER.error("Error streaming from HA camera %s: %s", entity_id, ex)

    async def _stream_from_url(
        self,
        config: CameraConfig,
        response: web.StreamResponse,
    ) -> None:
        """Stream from direct URL."""
        if self._session is None:
            _LOGGER.error("Camera manager session not initialized")
            return

        try:
            # Ensure stream URL is configured
            if not config.stream_url:
                _LOGGER.error("No stream URL configured for camera: %s", config.entity_id)
                return

            # Build auth if configured
            auth = None
            if config.username and config.password:
                auth = aiohttp.BasicAuth(config.username, config.password)

            ssl: bool = not config.verify_ssl
            timeout = ClientTimeout(total=CAMERA_STREAM_TIMEOUT)

            async with self._session.get(
                config.stream_url,
                auth=auth,
                ssl=ssl,
                headers=config.extra_headers,
                timeout=timeout,
            ) as camera_response:
                if camera_response.status != 200:
                    _LOGGER.error(
                        "Failed to connect to stream %s: HTTP %d",
                        config.stream_url,
                        camera_response.status,
                    )
                    return

                # Set up response headers
                response.content_type = camera_response.content_type
                if response._req is not None:  # noqa: SLF001
                    await response.prepare(response._req)  # noqa: SLF001

                # Proxy the stream
                async for chunk in camera_response.content.iter_chunked(CAMERA_STREAM_CHUNK_SIZE):
                    await response.write(chunk)

        except asyncio.TimeoutError:
            _LOGGER.debug("Stream timeout for camera: %s", config.entity_id)
        except asyncio.CancelledError:
            _LOGGER.debug("Stream cancelled for camera: %s", config.entity_id)
        except aiohttp.ClientError as ex:
            _LOGGER.error("Error streaming from %s: %s", config.stream_url, ex)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "cached_snapshots": len(self._snapshot_cache),
            "registered_cameras": len(self._camera_configs),
            "cache_entries": [
                {
                    "entity_id": entity_id,
                    "age_seconds": round(time.time() - snapshot.timestamp, 1),
                    "size_bytes": len(snapshot.image_data),
                    "content_type": snapshot.content_type,
                }
                for entity_id, snapshot in self._snapshot_cache.items()
            ],
        }

    async def clear_cache(self, entity_id: str | None = None) -> int:
        """Clear snapshot cache.

        Args:
            entity_id: Specific camera to clear, or None to clear all

        Returns:
            Number of cache entries cleared
        """
        async with self._lock:
            if entity_id:
                if entity_id in self._snapshot_cache:
                    del self._snapshot_cache[entity_id]
                    return 1
                return 0
            else:
                count = len(self._snapshot_cache)
                self._snapshot_cache.clear()
                return count

    # ========== HLS Streaming Methods ==========

    async def get_stream_info(self, entity_id: str) -> CameraStreamInfo | None:
        """Get streaming capabilities for a camera.

        Args:
            entity_id: The camera entity ID

        Returns:
            CameraStreamInfo with capabilities, or None if camera not found
        """
        state = self.hass.states.get(entity_id)
        if not state:
            return None

        name = state.attributes.get("friendly_name", entity_id)
        config = self._camera_configs.get(entity_id)

        # Check if camera supports streaming via HA
        supports_stream = await self._check_stream_support(entity_id)

        # Check for active HLS session
        hls_session = self._hls_sessions.get(entity_id)
        is_streaming = hls_session is not None

        return CameraStreamInfo(
            entity_id=entity_id,
            name=name,
            supports_snapshot=True,  # All cameras support snapshot
            supports_mjpeg=True,  # All cameras support MJPEG via HA
            supports_hls=supports_stream,
            supports_webrtc=False,  # Future support
            hls_url=f"/api/smartly/camera/{entity_id}/stream/hls" if supports_stream else None,
            mjpeg_url=f"/api/smartly/camera/{entity_id}/stream",
            stream_source=config.stream_url if config else None,
            is_streaming=is_streaming,
        )

    async def _check_stream_support(self, entity_id: str) -> bool:
        """Check if camera supports HLS streaming.

        Args:
            entity_id: The camera entity ID

        Returns:
            True if HLS streaming is supported
        """
        try:
            # Check if stream component is available
            if "stream" not in self.hass.config.components:
                _LOGGER.debug("Stream component not loaded")
                return False

            # Check if camera has stream source
            from homeassistant.components.camera import async_get_stream_source

            stream_source = await async_get_stream_source(self.hass, entity_id)
            return stream_source is not None
        except ImportError:
            _LOGGER.debug("Camera stream support not available")
            return False
        except Exception as ex:
            _LOGGER.debug("Error checking stream support for %s: %s", entity_id, ex)
            return False

    async def start_hls_stream(self, entity_id: str) -> dict[str, Any] | None:
        """Start HLS stream for a camera.

        Args:
            entity_id: The camera entity ID

        Returns:
            Dictionary with stream info including HLS URL, or None on failure
        """
        async with self._hls_lock:
            # Check for existing session
            if entity_id in self._hls_sessions:
                session = self._hls_sessions[entity_id]
                session.touch()
                return self._build_hls_response(session)

            try:
                # Get stream source from camera
                from homeassistant.components.camera import async_get_stream_source
                from homeassistant.components.stream import create_stream
                from homeassistant.components.stream.const import HLS_PROVIDER

                stream_source = await async_get_stream_source(self.hass, entity_id)
                if not stream_source:
                    _LOGGER.error("No stream source for camera: %s", entity_id)
                    return None

                # Create stream with default settings
                # Import dynamic stream settings - location varies by HA version
                dynamic_settings: Any = None
                try:
                    # HA 2024.x+ location
                    from homeassistant.components.camera.prefs import DynamicStreamSettings

                    dynamic_settings = DynamicStreamSettings()
                except ImportError:
                    # Older HA versions or different module structure
                    _LOGGER.debug("DynamicStreamSettings not found, using None")

                stream = create_stream(
                    self.hass,
                    stream_source,
                    {},
                    dynamic_settings,  # type: ignore[arg-type]
                )

                # Add HLS provider
                stream.add_provider(HLS_PROVIDER)

                # Start stream
                await stream.start()

                # Wait for stream to be ready
                hls_provider = stream.outputs().get(HLS_PROVIDER)
                if hls_provider:
                    # Wait for first segment with timeout
                    try:
                        await asyncio.wait_for(
                            hls_provider.recv(),
                            timeout=HLS_STREAM_START_TIMEOUT,
                        )
                    except asyncio.TimeoutError:
                        _LOGGER.warning("Timeout waiting for HLS stream to start: %s", entity_id)
                        # Continue anyway, stream might still work

                # Get stream token
                token = stream.access_token
                if not token:
                    _LOGGER.error("Failed to get stream token for: %s", entity_id)
                    await stream.stop()
                    return None

                # Create session
                now = time.time()
                session = HLSStreamSession(
                    entity_id=entity_id,
                    stream=stream,
                    token=token,
                    created_at=now,
                    last_access=now,
                )
                self._hls_sessions[entity_id] = session

                _LOGGER.info("Started HLS stream for camera: %s", entity_id)
                return self._build_hls_response(session)

            except ImportError as ex:
                _LOGGER.error("Stream component not available: %s", ex)
                return None
            except Exception as ex:
                _LOGGER.error("Failed to start HLS stream for %s: %s", entity_id, ex)
                return None

    def _build_hls_response(self, session: HLSStreamSession) -> dict[str, Any]:
        """Build HLS stream response dictionary.

        Args:
            session: The HLS stream session

        Returns:
            Dictionary with HLS stream information
        """
        base_url = f"/api/hls/{session.token}"
        return {
            "entity_id": session.entity_id,
            "stream_type": STREAM_TYPE_HLS,
            "hls_url": f"{base_url}/master_playlist.m3u8",
            "master_playlist": f"{base_url}/master_playlist.m3u8",
            "playlist": f"{base_url}/playlist.m3u8",
            "init": f"{base_url}/init.mp4",
            "token": session.token,
            "created_at": session.created_at,
            "is_active": True,
        }

    async def stop_hls_stream(self, entity_id: str) -> bool:
        """Stop HLS stream for a camera.

        Args:
            entity_id: The camera entity ID

        Returns:
            True if stream was stopped, False if not found
        """
        async with self._hls_lock:
            session = self._hls_sessions.pop(entity_id, None)
            if session:
                try:
                    await session.stream.stop()
                    _LOGGER.info("Stopped HLS stream for camera: %s", entity_id)
                    return True
                except Exception as ex:
                    _LOGGER.error("Error stopping HLS stream: %s", ex)
                    return True  # Still consider it stopped
            return False

    async def get_hls_session(self, entity_id: str) -> HLSStreamSession | None:
        """Get active HLS session for a camera.

        Args:
            entity_id: The camera entity ID

        Returns:
            HLSStreamSession if active, None otherwise
        """
        session = self._hls_sessions.get(entity_id)
        if session:
            session.touch()
        return session

    def get_hls_stats(self) -> dict[str, Any]:
        """Get HLS streaming statistics.

        Returns:
            Dictionary with HLS session statistics
        """
        now = time.time()
        return {
            "active_streams": len(self._hls_sessions),
            "streams": [
                {
                    "entity_id": session.entity_id,
                    "token": session.token,
                    "age_seconds": round(now - session.created_at, 1),
                    "idle_seconds": round(now - session.last_access, 1),
                }
                for session in self._hls_sessions.values()
            ],
        }

    async def cleanup_idle_hls_sessions(self) -> int:
        """Clean up idle HLS sessions.

        Returns:
            Number of sessions cleaned up
        """
        cleaned = 0
        async with self._hls_lock:
            idle_sessions = [
                entity_id for entity_id, session in self._hls_sessions.items() if session.is_idle()
            ]
            for entity_id in idle_sessions:
                session = self._hls_sessions.pop(entity_id)
                try:
                    await session.stream.stop()
                    _LOGGER.info("Cleaned up idle HLS stream: %s", entity_id)
                    cleaned += 1
                except Exception as ex:
                    _LOGGER.debug("Error cleaning up HLS stream: %s", ex)
                    cleaned += 1
        return cleaned

    async def get_camera_with_capabilities(self, entity_id: str) -> dict[str, Any] | None:
        """Get camera info with full capabilities.

        Args:
            entity_id: The camera entity ID

        Returns:
            Dictionary with camera info and capabilities
        """
        stream_info = await self.get_stream_info(entity_id)
        if not stream_info:
            return None
        return stream_info.to_dict()

    async def list_cameras_with_capabilities(self, entity_ids: list[str]) -> list[dict[str, Any]]:
        """List cameras with their streaming capabilities.

        Args:
            entity_ids: List of camera entity IDs

        Returns:
            List of camera info dictionaries with capabilities
        """
        cameras = []
        for entity_id in entity_ids:
            info = await self.get_camera_with_capabilities(entity_id)
            if info:
                cameras.append(info)
        return cameras
