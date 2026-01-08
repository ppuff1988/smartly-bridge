"""Camera views for Smartly Bridge integration.

Provides HTTP API endpoints for camera operations including:
- Snapshot: Static image capture with caching
- MJPEG Stream: Real-time video streaming
- HLS Stream: Adaptive bitrate streaming for mobile/web
"""

import json
import logging

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from ..acl import get_allowed_entities, is_entity_allowed
from ..audit import log_control, log_deny
from ..auth import RateLimiter, verify_request
from ..const import (
    API_PATH_CAMERA_CONFIG,
    API_PATH_CAMERA_HLS_INFO,
    API_PATH_CAMERA_LIST,
    API_PATH_CAMERA_SNAPSHOT,
    API_PATH_CAMERA_STREAM,
    CONF_ALLOWED_CIDRS,
    CONF_CLIENT_SECRET,
    CONF_TRUST_PROXY,
    DEFAULT_TRUST_PROXY,
    DOMAIN,
    RATE_WINDOW,
)
from .base import BaseView

_LOGGER = logging.getLogger(__name__)


class SmartlyCameraSnapshotView(BaseView):
    """Handle GET /api/smartly/camera/{entity_id}/snapshot requests."""

    async def get(self) -> web.Response:
        """Handle camera snapshot request."""
        entity_id = self.request.match_info.get("entity_id", "")

        # Validate entity_id format
        if not entity_id or not entity_id.startswith("camera."):
            return web.json_response(
                {"error": "invalid_entity_id"},
                status=400,
            )

        # Get integration data
        data = self._get_integration_data()
        if data is None:
            return web.json_response(
                {"error": "integration_not_configured"},
                status=500,
            )

        client_secret = data.get(CONF_CLIENT_SECRET)
        allowed_cidrs = data.get(CONF_ALLOWED_CIDRS, "")
        trust_proxy_mode = data.get(CONF_TRUST_PROXY, DEFAULT_TRUST_PROXY)
        nonce_cache = self.hass.data[DOMAIN]["nonce_cache"]
        rate_limiter: RateLimiter = self.hass.data[DOMAIN]["rate_limiter"]

        # Verify authentication
        auth_result = await verify_request(
            self.request,
            client_secret,
            nonce_cache,
            allowed_cidrs,
            trust_proxy_mode,
        )

        if not auth_result.success:
            log_deny(
                _LOGGER,
                client_id=self.request.headers.get("X-Client-Id", "unknown"),
                entity_id=entity_id,
                service="camera_snapshot",
                reason=auth_result.error or "auth_failed",
            )
            return web.json_response(
                {"error": auth_result.error},
                status=401,
            )

        # Check rate limit
        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service="camera_snapshot",
                reason="rate_limited",
            )
            return web.json_response(
                {"error": "rate_limited"},
                status=429,
                headers={
                    "Retry-After": str(RATE_WINDOW),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Check if entity is allowed
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self.hass)
        if not is_entity_allowed(self.hass, entity_id, entity_registry):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service="camera_snapshot",
                reason="entity_not_allowed",
            )
            return web.json_response(
                {"error": "entity_not_allowed"},
                status=403,
            )

        # Get camera manager
        from ..camera import CameraManager

        camera_manager: CameraManager | None = self.hass.data[DOMAIN].get("camera_manager")
        if camera_manager is None:
            return web.json_response(
                {"error": "camera_manager_not_initialized"},
                status=500,
            )

        # Check for conditional request (ETag)
        if_none_match = self.request.headers.get("If-None-Match")
        force_refresh = self.request.query.get("refresh", "").lower() == "true"

        # Get snapshot
        snapshot, not_modified = await camera_manager.get_snapshot(
            entity_id,
            force_refresh=force_refresh,
            if_none_match=if_none_match,
        )

        if not_modified:
            return web.Response(status=304)

        if snapshot is None:
            return web.json_response(
                {"error": "snapshot_unavailable"},
                status=404,
            )

        log_control(
            _LOGGER,
            client_id=auth_result.client_id or "unknown",
            entity_id=entity_id,
            service="camera_snapshot",
            result="success",
        )

        return web.Response(
            body=snapshot.image_data,
            content_type=snapshot.content_type,
            headers={
                "ETag": snapshot.etag,
                "Cache-Control": "private, max-age=10",
                "X-Snapshot-Timestamp": str(snapshot.timestamp),
            },
        )


class SmartlyCameraStreamView(BaseView):
    """Handle GET /api/smartly/camera/{entity_id}/stream requests."""

    async def get(self) -> web.StreamResponse:
        """Handle camera stream request."""
        entity_id = self.request.match_info.get("entity_id", "")

        # Log detailed request information
        _LOGGER.info(
            "Camera stream request received:\n"
            "  Entity ID: %s\n"
            "  Method: %s\n"
            "  Path: %s\n"
            "  Query String: %s\n"
            "  Query Params: %s\n"
            "  Headers: %s\n"
            "  Remote: %s\n"
            "  Client IP: %s\n"
            "  X-Forwarded-For: %s\n"
            "  X-Real-IP: %s\n"
            "  X-Stream-Token: %s",
            entity_id,
            self.request.method,
            self.request.path,
            self.request.query_string,
            dict(self.request.query),
            dict(self.request.headers),
            self.request.remote,
            self.request.headers.get("X-Client-IP", "N/A"),
            self.request.headers.get("X-Forwarded-For", "N/A"),
            self.request.headers.get("X-Real-IP", "N/A"),
            self.request.headers.get("X-Stream-Token", "N/A"),
        )

        # Validate entity_id format
        if not entity_id or not entity_id.startswith("camera."):
            return web.json_response(
                {"error": "invalid_entity_id"},
                status=400,
            )

        # Get integration data
        data = self._get_integration_data()
        if data is None:
            return web.json_response(
                {"error": "integration_not_configured"},
                status=500,
            )

        client_secret = data.get(CONF_CLIENT_SECRET)
        allowed_cidrs = data.get(CONF_ALLOWED_CIDRS, "")
        trust_proxy_mode = data.get(CONF_TRUST_PROXY, DEFAULT_TRUST_PROXY)
        nonce_cache = self.hass.data[DOMAIN]["nonce_cache"]
        rate_limiter: RateLimiter = self.hass.data[DOMAIN]["rate_limiter"]

        # Verify authentication
        auth_result = await verify_request(
            self.request,
            client_secret,
            nonce_cache,
            allowed_cidrs,
            trust_proxy_mode,
        )

        if not auth_result.success:
            log_deny(
                _LOGGER,
                client_id=self.request.headers.get("X-Client-Id", "unknown"),
                entity_id=entity_id,
                service="camera_stream",
                reason=auth_result.error or "auth_failed",
            )
            return web.json_response(
                {"error": auth_result.error},
                status=401,
            )

        # Check rate limit (less strict for streaming)
        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service="camera_stream",
                reason="rate_limited",
            )
            return web.json_response(
                {"error": "rate_limited"},
                status=429,
                headers={
                    "Retry-After": str(RATE_WINDOW),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Check if entity is allowed
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self.hass)
        if not is_entity_allowed(self.hass, entity_id, entity_registry):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service="camera_stream",
                reason="entity_not_allowed",
            )
            return web.json_response(
                {"error": "entity_not_allowed"},
                status=403,
            )

        # Get camera manager
        from ..camera import CameraManager

        camera_manager: CameraManager | None = self.hass.data[DOMAIN].get("camera_manager")
        if camera_manager is None:
            return web.json_response(
                {"error": "camera_manager_not_initialized"},
                status=500,
            )

        log_control(
            _LOGGER,
            client_id=auth_result.client_id or "unknown",
            entity_id=entity_id,
            service="camera_stream",
            result="started",
        )

        # Create stream response
        # IMPORTANT: For MJPEG streams, we must avoid chunked encoding
        # MJPEG uses multipart/x-mixed-replace format which is incompatible with
        # Transfer-Encoding: chunked. The chunked wrapper breaks the multipart
        # boundaries and causes parsing errors in clients (e.g., Go HTTP client).
        #
        # Solution: Use HTTP/1.0-style response (no chunked encoding)
        # by explicitly disabling compression and using Connection: close
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "multipart/x-mixed-replace;boundary=frame",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Connection": "close",  # Critical: prevents chunked encoding
            },
        )

        # Explicitly disable compression to avoid any encoding
        response.enable_compression(False)

        await response.prepare(self.request)

        # Stream the camera feed
        await camera_manager.stream_proxy(entity_id, self.request, response)

        return response


class SmartlyCameraListView(BaseView):
    """Handle GET /api/smartly/camera/list requests."""

    async def get(self) -> web.Response:
        """Handle camera list request."""
        # Get integration data
        data = self._get_integration_data()
        if data is None:
            return web.json_response(
                {"error": "integration_not_configured"},
                status=500,
            )

        client_secret = data.get(CONF_CLIENT_SECRET)
        allowed_cidrs = data.get(CONF_ALLOWED_CIDRS, "")
        trust_proxy_mode = data.get(CONF_TRUST_PROXY, DEFAULT_TRUST_PROXY)
        nonce_cache = self.hass.data[DOMAIN]["nonce_cache"]
        rate_limiter: RateLimiter = self.hass.data[DOMAIN]["rate_limiter"]

        # Verify authentication
        auth_result = await verify_request(
            self.request,
            client_secret,
            nonce_cache,
            allowed_cidrs,
            trust_proxy_mode,
        )

        if not auth_result.success:
            log_deny(
                _LOGGER,
                client_id=self.request.headers.get("X-Client-Id", "unknown"),
                entity_id="",
                service="camera_list",
                reason=auth_result.error or "auth_failed",
            )
            return web.json_response(
                {"error": auth_result.error},
                status=401,
            )

        # Check rate limit
        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id="",
                service="camera_list",
                reason="rate_limited",
            )
            return web.json_response(
                {"error": "rate_limited"},
                status=429,
                headers={
                    "Retry-After": str(RATE_WINDOW),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Get allowed camera entities
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self.hass)
        allowed_entities = get_allowed_entities(self.hass, entity_registry)

        # Filter to only camera entities
        camera_entities = [e for e in allowed_entities if e.startswith("camera.")]

        # Get camera manager
        from ..camera import CameraManager

        camera_manager: CameraManager | None = self.hass.data[DOMAIN].get("camera_manager")

        # Check if detailed capabilities requested
        include_capabilities = self.request.query.get("capabilities", "").lower() == "true"

        # Build camera list with states and capabilities
        cameras = []
        for entity_id in camera_entities:
            state = self.hass.states.get(entity_id)
            if state:
                camera_info: dict = {
                    "entity_id": entity_id,
                    "name": state.attributes.get("friendly_name", entity_id),
                    "state": state.state,
                    "is_streaming": state.attributes.get("is_streaming", False),
                    "brand": state.attributes.get("brand"),
                    "model": state.attributes.get("model_name"),
                    "supported_features": state.attributes.get("supported_features", 0),
                }

                # Add streaming capabilities if requested
                if include_capabilities and camera_manager:
                    stream_info = await camera_manager.get_stream_info(entity_id)
                    if stream_info:
                        camera_info["capabilities"] = {
                            "snapshot": stream_info.supports_snapshot,
                            "mjpeg": stream_info.supports_mjpeg,
                            "hls": stream_info.supports_hls,
                            "webrtc": stream_info.supports_webrtc,
                        }
                        camera_info["endpoints"] = {
                            "snapshot": f"/api/smartly/camera/{entity_id}/snapshot",
                            "mjpeg": f"/api/smartly/camera/{entity_id}/stream",
                            "hls": (
                                f"/api/smartly/camera/{entity_id}/stream/hls"
                                if stream_info.supports_hls
                                else None
                            ),
                        }

                cameras.append(camera_info)

        cache_stats = camera_manager.get_cache_stats() if camera_manager else {}
        hls_stats = camera_manager.get_hls_stats() if camera_manager else {}

        return web.json_response(
            {
                "cameras": cameras,
                "count": len(cameras),
                "cache_stats": cache_stats,
                "hls_stats": hls_stats,
            },
            status=200,
        )


class SmartlyCameraConfigView(BaseView):
    """Handle POST /api/smartly/camera/config requests."""

    async def post(self) -> web.Response:
        """Handle camera configuration request."""
        # Get integration data
        data = self._get_integration_data()
        if data is None:
            return web.json_response(
                {"error": "integration_not_configured"},
                status=500,
            )

        client_secret = data.get(CONF_CLIENT_SECRET)
        allowed_cidrs = data.get(CONF_ALLOWED_CIDRS, "")
        trust_proxy_mode = data.get(CONF_TRUST_PROXY, DEFAULT_TRUST_PROXY)
        nonce_cache = self.hass.data[DOMAIN]["nonce_cache"]
        rate_limiter: RateLimiter = self.hass.data[DOMAIN]["rate_limiter"]

        # Verify authentication
        auth_result = await verify_request(
            self.request,
            client_secret,
            nonce_cache,
            allowed_cidrs,
            trust_proxy_mode,
        )

        if not auth_result.success:
            log_deny(
                _LOGGER,
                client_id=self.request.headers.get("X-Client-Id", "unknown"),
                entity_id="",
                service="camera_config",
                reason=auth_result.error or "auth_failed",
            )
            return web.json_response(
                {"error": auth_result.error},
                status=401,
            )

        # Check rate limit
        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id="",
                service="camera_config",
                reason="rate_limited",
            )
            return web.json_response(
                {"error": "rate_limited"},
                status=429,
                headers={
                    "Retry-After": str(RATE_WINDOW),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Parse request body
        try:
            body = await self.request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"error": "invalid_json"},
                status=400,
            )

        action = body.get("action")
        entity_id = body.get("entity_id")

        if not action:
            return web.json_response(
                {"error": "missing_action"},
                status=400,
            )

        # Get camera manager
        from ..camera import CameraConfig, CameraManager

        camera_manager: CameraManager | None = self.hass.data[DOMAIN].get("camera_manager")
        if camera_manager is None:
            return web.json_response(
                {"error": "camera_manager_not_initialized"},
                status=500,
            )

        # Handle different actions
        if action == "register":
            if not entity_id:
                return web.json_response(
                    {"error": "missing_entity_id"},
                    status=400,
                )

            config = CameraConfig(
                entity_id=entity_id,
                name=body.get("name", entity_id),
                snapshot_url=body.get("snapshot_url"),
                stream_url=body.get("stream_url"),
                username=body.get("username"),
                password=body.get("password"),
                verify_ssl=body.get("verify_ssl", True),
                extra_headers=body.get("extra_headers", {}),
            )
            camera_manager.register_camera(config)
            return web.json_response(
                {"success": True, "action": "registered", "entity_id": entity_id},
                status=200,
            )

        elif action == "unregister":
            if not entity_id:
                return web.json_response(
                    {"error": "missing_entity_id"},
                    status=400,
                )
            camera_manager.unregister_camera(entity_id)
            return web.json_response(
                {"success": True, "action": "unregistered", "entity_id": entity_id},
                status=200,
            )

        elif action == "clear_cache":
            count = await camera_manager.clear_cache(entity_id)
            return web.json_response(
                {"success": True, "action": "cache_cleared", "cleared_count": count},
                status=200,
            )

        elif action == "list":
            cameras = camera_manager.list_cameras()
            return web.json_response(
                {"cameras": cameras, "count": len(cameras)},
                status=200,
            )

        else:
            return web.json_response(
                {"error": "unknown_action"},
                status=400,
            )


class SmartlyCameraHLSInfoView(BaseView):
    """Handle GET /api/smartly/camera/{entity_id}/stream/hls requests.

    Returns HLS stream information and starts the stream if needed.
    """

    async def get(self) -> web.Response:
        """Handle HLS stream info/start request."""
        entity_id = self.request.match_info.get("entity_id", "")

        # Validate entity_id format
        if not entity_id or not entity_id.startswith("camera."):
            return web.json_response(
                {"error": "invalid_entity_id"},
                status=400,
            )

        # Get integration data
        data = self._get_integration_data()
        if data is None:
            return web.json_response(
                {"error": "integration_not_configured"},
                status=500,
            )

        client_secret = data.get(CONF_CLIENT_SECRET)
        allowed_cidrs = data.get(CONF_ALLOWED_CIDRS, "")
        trust_proxy_mode = data.get(CONF_TRUST_PROXY, DEFAULT_TRUST_PROXY)
        nonce_cache = self.hass.data[DOMAIN]["nonce_cache"]
        rate_limiter: RateLimiter = self.hass.data[DOMAIN]["rate_limiter"]

        # Verify authentication
        auth_result = await verify_request(
            self.request,
            client_secret,
            nonce_cache,
            allowed_cidrs,
            trust_proxy_mode,
        )

        if not auth_result.success:
            log_deny(
                _LOGGER,
                client_id=self.request.headers.get("X-Client-Id", "unknown"),
                entity_id=entity_id,
                service="camera_hls",
                reason=auth_result.error or "auth_failed",
            )
            return web.json_response(
                {"error": auth_result.error},
                status=401,
            )

        # Check rate limit
        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service="camera_hls",
                reason="rate_limited",
            )
            return web.json_response(
                {"error": "rate_limited"},
                status=429,
                headers={
                    "Retry-After": str(RATE_WINDOW),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Check if entity is allowed
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self.hass)
        if not is_entity_allowed(self.hass, entity_id, entity_registry):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service="camera_hls",
                reason="entity_not_allowed",
            )
            return web.json_response(
                {"error": "entity_not_allowed"},
                status=403,
            )

        # Get camera manager
        from ..camera import CameraManager

        camera_manager: CameraManager | None = self.hass.data[DOMAIN].get("camera_manager")
        if camera_manager is None:
            return web.json_response(
                {"error": "camera_manager_not_initialized"},
                status=500,
            )

        # Check query parameter for action
        action = self.request.query.get("action", "start")

        if action == "info":
            # Just get stream info without starting
            stream_info = await camera_manager.get_stream_info(entity_id)
            if stream_info is None:
                return web.json_response(
                    {"error": "camera_not_found"},
                    status=404,
                )
            return web.json_response(stream_info.to_dict(), status=200)

        elif action == "stop":
            # Stop HLS stream
            stopped = await camera_manager.stop_hls_stream(entity_id)
            log_control(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service="camera_hls_stop",
                result="success" if stopped else "not_found",
            )
            return web.json_response(
                {"success": stopped, "action": "stopped"},
                status=200 if stopped else 404,
            )

        elif action == "start" or action == "":
            # Start HLS stream (default action)
            hls_info = await camera_manager.start_hls_stream(entity_id)
            if hls_info is None:
                return web.json_response(
                    {"error": "hls_not_supported"},
                    status=400,
                )

            log_control(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service="camera_hls_start",
                result="success",
            )
            return web.json_response(hls_info, status=200)

        elif action == "stats":
            # Get HLS stats
            stats = camera_manager.get_hls_stats()
            return web.json_response(stats, status=200)

        else:
            return web.json_response(
                {"error": "unknown_action"},
                status=400,
            )


# Wrapper classes for Home Assistant view registration


class SmartlyCameraSnapshotViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyCameraSnapshotView to work with HA's view registration."""

    url = API_PATH_CAMERA_SNAPSHOT
    name = "api:smartly:camera:snapshot"
    requires_auth = False  # We handle auth ourselves via HMAC

    async def get(self, request: web.Request, entity_id: str) -> web.Response:
        """Handle GET request."""
        view = SmartlyCameraSnapshotView(request)
        return await view.get()


class SmartlyCameraStreamViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyCameraStreamView to work with HA's view registration."""

    url = API_PATH_CAMERA_STREAM
    name = "api:smartly:camera:stream"
    requires_auth = False  # We handle auth ourselves via HMAC

    async def get(self, request: web.Request, entity_id: str) -> web.StreamResponse:
        """Handle GET request."""
        view = SmartlyCameraStreamView(request)
        return await view.get()


class SmartlyCameraListViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyCameraListView to work with HA's view registration."""

    url = API_PATH_CAMERA_LIST
    name = "api:smartly:camera:list"
    requires_auth = False  # We handle auth ourselves via HMAC

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request."""
        view = SmartlyCameraListView(request)
        return await view.get()


class SmartlyCameraConfigViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyCameraConfigView to work with HA's view registration."""

    url = API_PATH_CAMERA_CONFIG
    name = "api:smartly:camera:config"
    requires_auth = False  # We handle auth ourselves via HMAC

    async def post(self, request: web.Request) -> web.Response:
        """Handle POST request."""
        view = SmartlyCameraConfigView(request)
        return await view.post()


class SmartlyCameraHLSInfoViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyCameraHLSInfoView to work with HA's view registration."""

    url = API_PATH_CAMERA_HLS_INFO
    name = "api:smartly:camera:hls:info"
    requires_auth = False  # We handle auth ourselves via HMAC

    async def get(self, request: web.Request, entity_id: str) -> web.Response:
        """Handle GET request."""
        view = SmartlyCameraHLSInfoView(request)
        return await view.get()
