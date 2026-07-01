"""Camera views for Smartly Bridge integration.

Provides HTTP API endpoints for camera operations including:
- Snapshot: Static image capture with caching
- MJPEG Stream: Real-time video streaming
- HLS Stream: Adaptive bitrate streaming for mobile/web
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from ..acl import get_allowed_entities, is_entity_allowed
from ..adapters.home_assistant import HomeAssistantCameraGateway
from ..application.camera import (
    CameraConfigCommand,
    CameraConfigUseCase,
    CameraHLSUseCase,
    CameraListUseCase,
    CameraSnapshotUseCase,
    CameraStreamUseCase,
    _camera_error_response,
)
from ..audit import log_control, log_deny
from ..auth import AuthResult, RateLimiter, verify_request
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


def _create_fallback_camera_gateway(hass: Any, camera_manager: Any) -> Any:
    """Create and store a legacy Home Assistant camera gateway fallback."""
    gateway = HomeAssistantCameraGateway(
        hass,
        camera_manager,
        allowed_entities_fn=get_allowed_entities,
    )
    hass.data[DOMAIN].setdefault("runtime_adapters", {})["camera_gateway"] = gateway
    return gateway


def _with_request_context(body: dict[str, Any], request: web.Request) -> dict[str, Any]:
    """Attach optional vNext request correlation fields from HTTP headers."""
    enriched = dict(body)
    request_id = request.headers.get("X-Request-Id")
    correlation_id = request.headers.get("X-Correlation-Id")
    if isinstance(request_id, str) and request_id:
        enriched["request_id"] = request_id
    if isinstance(correlation_id, str) and correlation_id:
        enriched["correlation_id"] = correlation_id
    return enriched


def _json_response(
    result_body: dict[str, Any],
    request: web.Request,
    *,
    status: int,
    headers: dict[str, str] | None = None,
) -> web.Response:
    """Return a camera JSON response with optional request context."""
    return web.json_response(
        _with_request_context(result_body, request),
        status=status,
        headers=headers,
    )


@dataclass(frozen=True)
class CameraRequestGuardResult:
    """Result of the camera HTTP shell authorization guard."""

    auth_result: AuthResult | None = None
    response: web.Response | None = None


@dataclass(frozen=True)
class CameraManagerGuardResult:
    """Result of resolving the camera runtime manager."""

    camera_manager: Any | None = None
    response: web.Response | None = None


@dataclass(frozen=True)
class CameraEntityIdValidationResult:
    """Result of validating a camera entity ID from the HTTP path."""

    entity_id: str = ""
    response: web.Response | None = None


@dataclass(frozen=True)
class CameraGatewayResolutionResult:
    """Result of resolving the camera application gateway port."""

    gateway: Any | None = None
    response: web.Response | None = None


@dataclass(frozen=True)
class CameraConfigCommandParseResult:
    """Result of adapting a config request body into an application command."""

    command: CameraConfigCommand | None = None
    response: web.Response | None = None


@dataclass(frozen=True)
class CameraSnapshotRequestOptions:
    """Request options adapted for the snapshot application use case."""

    force_refresh: bool = False
    if_none_match: str | None = None


@dataclass(frozen=True)
class CameraListRequestOptions:
    """Request options adapted for the camera list application use case."""

    include_capabilities: bool = False


@dataclass(frozen=True)
class CameraStreamLogContext:
    """Diagnostic request fields logged by the MJPEG stream shell."""

    entity_id: str
    method: str
    path: str
    query_string: str
    query_params: dict[str, Any]
    headers: dict[str, Any]
    remote: Any
    client_ip: str
    x_forwarded_for: str
    x_real_ip: str
    x_stream_token: str


@dataclass(frozen=True)
class CameraHLSAuditEvent:
    """Audit event emitted by the HLS HTTP shell."""

    service: str
    result: str


async def _authorize_camera_request(
    request: web.Request,
    hass: Any,
    *,
    entity_id: str,
    service: str,
    require_entity_allowed: bool = False,
) -> CameraRequestGuardResult:
    """Authorize a camera HTTP request and return auth context or a response."""
    integration_data = hass.data.get(DOMAIN)
    config_entry = integration_data.get("config_entry") if integration_data else None
    if config_entry is None:
        result = _camera_error_response(
            "integration_not_configured",
            status=500,
            target="camera.config",
        )
        return CameraRequestGuardResult(
            response=_json_response(
                result.body,
                request,
                status=result.status,
                headers=result.headers,
            )
        )

    client_secret = config_entry.data.get(CONF_CLIENT_SECRET)
    allowed_cidrs = config_entry.data.get(CONF_ALLOWED_CIDRS, "")
    trust_proxy_mode = config_entry.data.get(CONF_TRUST_PROXY, DEFAULT_TRUST_PROXY)
    nonce_cache = integration_data["nonce_cache"]
    rate_limiter: RateLimiter = integration_data["rate_limiter"]

    auth_result = await verify_request(
        request,
        client_secret,
        nonce_cache,
        allowed_cidrs,
        trust_proxy_mode,
    )

    if not auth_result.success:
        log_deny(
            _LOGGER,
            client_id=request.headers.get("X-Client-Id", "unknown"),
            entity_id=entity_id,
            service=service,
            reason=auth_result.error or "auth_failed",
        )
        result = _camera_error_response(
            auth_result.error or "auth_failed",
            status=401,
            target="camera.auth",
        )
        return CameraRequestGuardResult(
            auth_result=auth_result,
            response=_json_response(
                result.body,
                request,
                status=result.status,
                headers=result.headers,
            ),
        )

    if not await rate_limiter.check(auth_result.client_id or ""):
        log_deny(
            _LOGGER,
            client_id=auth_result.client_id or "unknown",
            entity_id=entity_id,
            service=service,
            reason="rate_limited",
        )
        result = _camera_error_response(
            "rate_limited",
            status=429,
            target="camera.rate_limit",
        )
        headers = {
            **result.headers,
            "Retry-After": str(RATE_WINDOW),
            "X-RateLimit-Remaining": "0",
        }
        return CameraRequestGuardResult(
            auth_result=auth_result,
            response=_json_response(
                result.body,
                request,
                status=result.status,
                headers=headers,
            ),
        )

    if require_entity_allowed:
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(hass)
        if not is_entity_allowed(hass, entity_id, entity_registry):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service=service,
                reason="entity_not_allowed",
            )
            result = _camera_error_response(
                "entity_not_allowed",
                status=403,
                target="camera.entity_id",
            )
            return CameraRequestGuardResult(
                auth_result=auth_result,
                response=_json_response(
                    result.body,
                    request,
                    status=result.status,
                    headers=result.headers,
                ),
            )

    return CameraRequestGuardResult(auth_result=auth_result)


def _require_camera_manager(
    request: web.Request,
    hass: Any,
) -> CameraManagerGuardResult:
    """Return the camera manager or a legacy-compatible manager error response."""
    camera_manager = hass.data.get(DOMAIN, {}).get("camera_manager")
    if camera_manager is None:
        result = _camera_error_response(
            "camera_manager_not_initialized",
            status=500,
            target="camera.manager",
        )
        return CameraManagerGuardResult(
            response=_json_response(
                result.body,
                request,
                status=result.status,
                headers=result.headers,
            )
        )

    return CameraManagerGuardResult(camera_manager=camera_manager)


def _validate_camera_entity_id(
    request: web.Request,
    entity_id: str,
) -> CameraEntityIdValidationResult:
    """Return a camera entity ID or a legacy-compatible invalid entity response."""
    if not entity_id or not entity_id.startswith("camera."):
        result = _camera_error_response(
            "invalid_entity_id",
            status=400,
            target="camera.entity_id",
        )
        return CameraEntityIdValidationResult(
            response=_json_response(
                result.body,
                request,
                status=result.status,
                headers=result.headers,
            )
        )

    return CameraEntityIdValidationResult(entity_id=entity_id)


def _camera_entity_id_from_request(request: web.Request) -> str:
    """Return the raw camera entity id from the HTTP path."""
    return request.match_info.get("entity_id", "")


def _resolve_camera_gateway(
    request: web.Request,
    hass: Any,
) -> CameraGatewayResolutionResult:
    """Return the setup-created camera gateway or a legacy fallback gateway."""
    runtime_adapters = hass.data.get(DOMAIN, {}).setdefault("runtime_adapters", {})
    gateway = runtime_adapters.get("camera_gateway")
    if gateway is not None:
        return CameraGatewayResolutionResult(gateway=gateway)

    manager_guard = _require_camera_manager(request, hass)
    if manager_guard.response is not None:
        return CameraGatewayResolutionResult(response=manager_guard.response)

    return CameraGatewayResolutionResult(
        gateway=_create_fallback_camera_gateway(hass, manager_guard.camera_manager)
    )


async def _parse_camera_config_command(
    request: web.Request,
) -> CameraConfigCommandParseResult:
    """Parse a camera config request into an application command."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        result = _camera_error_response(
            "invalid_json",
            status=400,
            target="camera.request",
        )
        return CameraConfigCommandParseResult(
            response=_json_response(
                result.body,
                request,
                status=result.status,
                headers=result.headers,
            )
        )

    action = body.get("action")
    if not action:
        result = _camera_error_response(
            "missing_action",
            status=400,
            target="camera.action",
        )
        return CameraConfigCommandParseResult(
            response=_json_response(
                result.body,
                request,
                status=result.status,
                headers=result.headers,
            )
        )

    return CameraConfigCommandParseResult(
        command=CameraConfigCommand(
            action=action,
            entity_id=body.get("entity_id"),
            data=body,
        )
    )


def _parse_camera_hls_action(request: web.Request) -> str:
    """Return the HLS action requested by the HTTP query."""
    return request.query.get("action", "start")


def _camera_hls_audit_event(action: str, status: int) -> CameraHLSAuditEvent | None:
    """Return the audit event for an HLS action result, if one should be logged."""
    if action == "stop":
        return CameraHLSAuditEvent(
            service="camera_hls_stop",
            result="success" if status == 200 else "not_found",
        )

    if action in ("start", "") and status == 200:
        return CameraHLSAuditEvent(service="camera_hls_start", result="success")

    return None


def _parse_camera_snapshot_options(request: web.Request) -> CameraSnapshotRequestOptions:
    """Return snapshot request options expected by the application use case."""
    return CameraSnapshotRequestOptions(
        force_refresh=request.query.get("refresh", "").lower() == "true",
        if_none_match=request.headers.get("If-None-Match"),
    )


def _parse_camera_list_options(request: web.Request) -> CameraListRequestOptions:
    """Return camera list request options expected by the application use case."""
    return CameraListRequestOptions(
        include_capabilities=request.query.get("capabilities", "").lower() == "true"
    )


def _build_camera_stream_log_context(
    request: web.Request,
    entity_id: str,
) -> CameraStreamLogContext:
    """Return legacy MJPEG stream request diagnostics for logging."""
    return CameraStreamLogContext(
        entity_id=entity_id,
        method=request.method,
        path=request.path,
        query_string=request.query_string,
        query_params=dict(request.query),
        headers=dict(request.headers),
        remote=request.remote,
        client_ip=request.headers.get("X-Client-IP", "N/A"),
        x_forwarded_for=request.headers.get("X-Forwarded-For", "N/A"),
        x_real_ip=request.headers.get("X-Real-IP", "N/A"),
        x_stream_token=request.headers.get("X-Stream-Token", "N/A"),
    )


async def _prepare_camera_stream_response(request: web.Request) -> web.StreamResponse:
    """Prepare the legacy MJPEG stream response metadata for proxy streaming."""
    stream_result = CameraStreamUseCase().execute()
    response = web.StreamResponse(status=stream_result.status, headers=stream_result.headers)
    response.enable_compression(False)
    await response.prepare(request)
    return response


def _adapt_camera_snapshot_response(result: Any, request: web.Request) -> web.Response:
    """Adapt a snapshot application response into a legacy-compatible HTTP response."""
    if result.status == 304:
        return web.Response(status=304, headers=result.headers)

    if result.status == 404:
        return _json_response(
            result.body,
            request,
            status=result.status,
        )

    snapshot = result.body["snapshot"]
    return web.Response(
        body=snapshot.image_data,
        content_type=snapshot.content_type,
        headers=result.headers,
    )


def _adapt_camera_json_response(result: Any, request: web.Request) -> web.Response:
    """Adapt a camera application response into a JSON HTTP response."""
    return _json_response(
        result.body,
        request,
        status=result.status,
        headers=result.headers,
    )


def _log_camera_control_event(
    logger: logging.Logger,
    auth_result: AuthResult,
    *,
    entity_id: str,
    service: str,
    result: str,
) -> None:
    """Emit a camera control audit event with the legacy client-id fallback."""
    log_control(
        logger,
        client_id=auth_result.client_id or "unknown",
        entity_id=entity_id,
        service=service,
        result=result,
    )


class SmartlyCameraSnapshotView(BaseView):
    """Handle GET /api/smartly/camera/{entity_id}/snapshot requests."""

    async def get(self) -> web.Response:
        """Handle camera snapshot request."""
        validation = _validate_camera_entity_id(
            self.request,
            _camera_entity_id_from_request(self.request),
        )
        if validation.response is not None:
            return validation.response
        entity_id = validation.entity_id

        guard = await _authorize_camera_request(
            self.request,
            self.hass,
            entity_id=entity_id,
            service="camera_snapshot",
            require_entity_allowed=True,
        )
        if guard.response is not None:
            return guard.response
        auth_result = guard.auth_result
        assert auth_result is not None

        gateway_resolution = _resolve_camera_gateway(self.request, self.hass)
        if gateway_resolution.response is not None:
            return gateway_resolution.response
        camera_gateway = gateway_resolution.gateway

        options = _parse_camera_snapshot_options(self.request)
        result = await CameraSnapshotUseCase(camera_gateway).execute(
            entity_id,
            force_refresh=options.force_refresh,
            if_none_match=options.if_none_match,
        )

        if result.status in (304, 404):
            return _adapt_camera_snapshot_response(result, self.request)

        _log_camera_control_event(
            _LOGGER,
            auth_result,
            entity_id=entity_id,
            service="camera_snapshot",
            result="success",
        )

        return _adapt_camera_snapshot_response(result, self.request)


class SmartlyCameraStreamView(BaseView):
    """Handle GET /api/smartly/camera/{entity_id}/stream requests."""

    async def get(self) -> web.StreamResponse:
        """Handle camera stream request."""
        raw_entity_id = _camera_entity_id_from_request(self.request)

        log_context = _build_camera_stream_log_context(self.request, raw_entity_id)
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
            log_context.entity_id,
            log_context.method,
            log_context.path,
            log_context.query_string,
            log_context.query_params,
            log_context.headers,
            log_context.remote,
            log_context.client_ip,
            log_context.x_forwarded_for,
            log_context.x_real_ip,
            log_context.x_stream_token,
        )

        validation = _validate_camera_entity_id(self.request, raw_entity_id)
        if validation.response is not None:
            return validation.response
        entity_id = validation.entity_id

        guard = await _authorize_camera_request(
            self.request,
            self.hass,
            entity_id=entity_id,
            service="camera_stream",
            require_entity_allowed=True,
        )
        if guard.response is not None:
            return guard.response
        auth_result = guard.auth_result
        assert auth_result is not None

        gateway_resolution = _resolve_camera_gateway(self.request, self.hass)
        if gateway_resolution.response is not None:
            return gateway_resolution.response
        camera_gateway = gateway_resolution.gateway

        _log_camera_control_event(
            _LOGGER,
            auth_result,
            entity_id=entity_id,
            service="camera_stream",
            result="started",
        )

        # MJPEG uses multipart/x-mixed-replace boundaries, which break when
        # chunked encoding wraps the stream. The Connection header prepared by
        # the stream response adapter keeps this response in the non-chunked path.
        response = await _prepare_camera_stream_response(self.request)
        # Stream the camera feed through the setup-created gateway while
        # preserving the existing CameraManager-backed proxy implementation.
        await camera_gateway.stream_proxy(
            entity_id,
            self.request,
            response,
        )

        return response


class SmartlyCameraListView(BaseView):
    """Handle GET /api/smartly/camera/list requests."""

    async def get(self) -> web.Response:
        """Handle camera list request."""
        guard = await _authorize_camera_request(
            self.request,
            self.hass,
            entity_id="",
            service="camera_list",
        )
        if guard.response is not None:
            return guard.response

        gateway_resolution = _resolve_camera_gateway(self.request, self.hass)
        if gateway_resolution.response is not None:
            return gateway_resolution.response

        options = _parse_camera_list_options(self.request)
        result = await CameraListUseCase(gateway_resolution.gateway).execute(
            include_capabilities=options.include_capabilities
        )
        return _adapt_camera_json_response(result, self.request)


class SmartlyCameraConfigView(BaseView):
    """Handle POST /api/smartly/camera/config requests."""

    async def post(self) -> web.Response:
        """Handle camera configuration request."""
        guard = await _authorize_camera_request(
            self.request,
            self.hass,
            entity_id="",
            service="camera_config",
        )
        if guard.response is not None:
            return guard.response

        command_result = await _parse_camera_config_command(self.request)
        if command_result.response is not None:
            return command_result.response
        command = command_result.command
        assert command is not None

        gateway_resolution = _resolve_camera_gateway(self.request, self.hass)
        if gateway_resolution.response is not None:
            return gateway_resolution.response

        result = await CameraConfigUseCase(gateway_resolution.gateway).execute(command)
        return _adapt_camera_json_response(result, self.request)


class SmartlyCameraHLSInfoView(BaseView):
    """Handle GET /api/smartly/camera/{entity_id}/stream/hls requests.

    Returns HLS stream information and starts the stream if needed.
    """

    async def get(self) -> web.Response:
        """Handle HLS stream info/start request."""
        validation = _validate_camera_entity_id(
            self.request,
            _camera_entity_id_from_request(self.request),
        )
        if validation.response is not None:
            return validation.response
        entity_id = validation.entity_id

        guard = await _authorize_camera_request(
            self.request,
            self.hass,
            entity_id=entity_id,
            service="camera_hls",
            require_entity_allowed=True,
        )
        if guard.response is not None:
            return guard.response
        auth_result = guard.auth_result
        assert auth_result is not None

        gateway_resolution = _resolve_camera_gateway(self.request, self.hass)
        if gateway_resolution.response is not None:
            return gateway_resolution.response

        action = _parse_camera_hls_action(self.request)
        result = await CameraHLSUseCase(gateway_resolution.gateway).execute(
            entity_id,
            action,
        )

        audit_event = _camera_hls_audit_event(action, result.status)
        if audit_event is not None:
            _log_camera_control_event(
                _LOGGER,
                auth_result,
                entity_id=entity_id,
                service=audit_event.service,
                result=audit_event.result,
            )

        return _adapt_camera_json_response(result, self.request)


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
