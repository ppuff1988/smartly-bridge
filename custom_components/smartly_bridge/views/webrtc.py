"""WebRTC views for Smartly Bridge integration.

Provides HTTP API endpoints for WebRTC P2P video streaming:
- Token: Generate short-lived tokens for WebRTC connections
- Offer: Handle SDP offer/answer exchange via go2rtc
- ICE: Exchange ICE candidates for NAT traversal
- Hangup: Close WebRTC sessions

Authentication Flow:
1. Platform requests token via HMAC-authenticated endpoint
2. Token (5-min validity) is used for subsequent signaling
3. P2P connection established for direct video streaming via go2rtc
"""

import json
import logging
from typing import Any, Callable

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from ..acl import is_entity_allowed
from ..application.webrtc import (
    WebRTCHangupUseCase,
    WebRTCICEUseCase,
    WebRTCOfferUseCase,
    WebRTCTokenUseCase,
    _webrtc_error_response,
)
from ..audit import log_control, log_deny
from ..auth import RateLimiter, verify_request
from ..const import (
    API_PATH_WEBRTC_HANGUP,
    API_PATH_WEBRTC_ICE,
    API_PATH_WEBRTC_OFFER,
    API_PATH_WEBRTC_TOKEN,
    CONF_ALLOWED_CIDRS,
    CONF_CLIENT_SECRET,
    CONF_TRUST_PROXY,
    CONF_TURN_CREDENTIAL,
    CONF_TURN_URL,
    CONF_TURN_USERNAME,
    DEFAULT_TRUST_PROXY,
    DOMAIN,
    RATE_WINDOW,
)
from ..webrtc import WebRTCTokenManager
from .base import BaseView

_LOGGER = logging.getLogger(__name__)


def _web_rtc_gateway(
    hass: Any,
    _webrtc_manager: WebRTCTokenManager,
) -> Any | None:
    """Return the setup-created WebRTC gateway."""
    runtime_adapters = hass.data[DOMAIN].setdefault("runtime_adapters", {})
    return runtime_adapters.get("webrtc_gateway")


def _webrtc_gateway(hass: Any, webrtc_manager: WebRTCTokenManager) -> Any | None:
    """Return the setup-created WebRTC gateway."""
    return _web_rtc_gateway(hass, webrtc_manager)


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
    """Return a WebRTC JSON response with optional request context."""
    return web.json_response(
        _with_request_context(result_body, request),
        status=status,
        headers=headers,
    )


def _webrtc_error_message(result: BridgeResponse) -> str:
    """Return the first API vNext WebRTC error message for diagnostics."""
    errors = result.body.get("errors")
    if isinstance(errors, list) and errors:
        first_error = errors[0]
        if isinstance(first_error, dict):
            message = first_error.get("message")
            if isinstance(message, str):
                return message
    return "unknown WebRTC error"


def _webrtc_token_use_case(gateway: Any) -> WebRTCTokenUseCase:
    """Build the WebRTC token application use case."""
    return WebRTCTokenUseCase(gateway)


async def _create_webrtc_token(
    gateway: Any,
    *,
    entity_id: str,
    client_id: str,
    turn_config: dict[str, str],
    use_case_factory: Callable[[Any], Any] = _webrtc_token_use_case,
) -> Any:
    """Execute the WebRTC token use case with parsed HTTP shell inputs."""
    return await use_case_factory(gateway).execute(
        entity_id=entity_id,
        client_id=client_id,
        turn_config=turn_config,
    )


def _webrtc_offer_use_case(gateway: Any) -> WebRTCOfferUseCase:
    """Build the WebRTC offer application use case."""
    return WebRTCOfferUseCase(gateway)


async def _create_webrtc_offer(
    gateway: Any,
    *,
    entity_id: str,
    token: str,
    sdp_offer: str,
    use_case_factory: Callable[[Any], Any] = _webrtc_offer_use_case,
) -> Any:
    """Execute the WebRTC offer use case with parsed HTTP shell inputs."""
    return await use_case_factory(gateway).execute(
        entity_id=entity_id,
        token=token,
        sdp_offer=sdp_offer,
    )


def _webrtc_ice_use_case(gateway: Any) -> WebRTCICEUseCase:
    """Build the WebRTC ICE application use case."""
    return WebRTCICEUseCase(gateway)


async def _add_webrtc_ice_candidate(
    gateway: Any,
    *,
    entity_id: str,
    session_id: str,
    candidate: dict[str, Any] | None,
    use_case_factory: Callable[[Any], Any] = _webrtc_ice_use_case,
) -> Any:
    """Execute the WebRTC ICE use case with parsed HTTP shell inputs."""
    return await use_case_factory(gateway).execute(
        entity_id=entity_id,
        session_id=session_id,
        candidate=candidate,
    )


def _webrtc_hangup_use_case(gateway: Any) -> WebRTCHangupUseCase:
    """Build the WebRTC hangup application use case."""
    return WebRTCHangupUseCase(gateway)


async def _close_webrtc_session(
    gateway: Any,
    *,
    entity_id: str,
    session_id: str,
    use_case_factory: Callable[[Any], Any] = _webrtc_hangup_use_case,
) -> Any:
    """Execute the WebRTC hangup use case with parsed HTTP shell inputs."""
    return await use_case_factory(gateway).execute(
        entity_id=entity_id,
        session_id=session_id,
    )


class SmartlyWebRTCTokenView(BaseView):
    """Handle POST /api/smartly/camera/{entity_id}/webrtc requests.

    Platform uses HMAC authentication to request a WebRTC token.
    The token can then be used for SDP exchange without HMAC.
    """

    async def post(self) -> web.Response:
        """Generate WebRTC token for camera stream.

        Request (HMAC authenticated):
            POST /api/smartly/camera/{entity_id}/webrtc
            Body: {} (empty or optional configuration)

        Response:
            {
                "token": "xxxxx...",
                "expires_at": 1234567890,
                "expires_in": 300,
                "offer_endpoint": "/api/smartly/camera/{entity_id}/webrtc/offer",
                "ice_endpoint": "/api/smartly/camera/{entity_id}/webrtc/ice",
                "hangup_endpoint": "/api/smartly/camera/{entity_id}/webrtc/hangup",
                "ice_servers": [...],
                "entity_id": "camera.front_door"
            }

        Returns:
            JSON response with token and connection info.
        """
        entity_id = self.request.match_info.get("entity_id", "")

        # Validate entity_id format
        if not entity_id or not entity_id.startswith("camera."):
            result = _webrtc_error_response(
                "invalid_entity_id",
                status=400,
            )
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        # Get integration data
        data = self._get_integration_data()
        if data is None:
            result = _webrtc_error_response("integration_not_configured", status=500)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        client_secret = data.get(CONF_CLIENT_SECRET)
        allowed_cidrs = data.get(CONF_ALLOWED_CIDRS, "")
        trust_proxy_mode = data.get(CONF_TRUST_PROXY, DEFAULT_TRUST_PROXY)
        nonce_cache = self.hass.data[DOMAIN]["nonce_cache"]
        rate_limiter: RateLimiter = self.hass.data[DOMAIN]["rate_limiter"]

        # Verify HMAC authentication
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
                service="webrtc_token",
                reason=auth_result.error or "auth_failed",
            )
            result = _webrtc_error_response(auth_result.error or "auth_failed", status=401)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        # Check rate limit
        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service="webrtc_token",
                reason="rate_limited",
            )
            result = _webrtc_error_response("rate_limited", status=429)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers={
                    **result.headers,
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
                service="webrtc_token",
                reason="entity_not_allowed",
            )
            result = _webrtc_error_response("entity_not_allowed", status=403)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        # Get WebRTC token manager
        webrtc_manager: WebRTCTokenManager | None = self.hass.data[DOMAIN].get("webrtc_manager")
        if webrtc_manager is None:
            result = _webrtc_error_response(
                "webrtc_not_available",
                status=500,
            )
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        gateway = _webrtc_gateway(self.hass, webrtc_manager)
        if gateway is None:
            result = _webrtc_error_response(
                "webrtc_not_available",
                status=500,
            )
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        result = await _create_webrtc_token(
            gateway,
            entity_id=entity_id,
            client_id=auth_result.client_id or "unknown",
            turn_config={
                "turn_url": data.get(CONF_TURN_URL, "").strip(),
                "turn_username": data.get(CONF_TURN_USERNAME, "").strip(),
                "turn_credential": data.get(CONF_TURN_CREDENTIAL, "").strip(),
            },
        )

        if result.status == 404:
            return _json_response(result.body, self.request, status=result.status)

        log_control(
            _LOGGER,
            client_id=auth_result.client_id or "unknown",
            entity_id=entity_id,
            service="webrtc_token",
            result="success",
        )

        return _json_response(
            result.body, self.request, status=result.status, headers=result.headers
        )


class SmartlyWebRTCOfferView(BaseView):
    """Handle POST /api/smartly/camera/{entity_id}/webrtc/offer requests.

    Uses short-lived token for authentication instead of HMAC.
    Handles SDP offer/answer exchange for WebRTC connection.
    """

    async def post(self) -> web.Response:
        """Handle WebRTC offer and return answer.

        Request:
            POST /api/smartly/camera/{entity_id}/webrtc/offer
            {
                "token": "xxxxx...",
                "sdp": "v=0\\r\\n...",
                "type": "offer"
            }

        Response:
            {
                "type": "answer",
                "sdp": "v=0\\r\\n...",
                "session_id": "xxxxxxxx"
            }

        Returns:
            JSON response with SDP answer.
        """
        entity_id = self.request.match_info.get("entity_id", "")

        # Validate entity_id format
        if not entity_id or not entity_id.startswith("camera."):
            result = _webrtc_error_response("invalid_entity_id", status=400)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        # Parse request body
        try:
            body = await self.request.json()
        except json.JSONDecodeError:
            result = _webrtc_error_response(
                "invalid_json",
                status=400,
            )
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        token_str = body.get("token")
        sdp_offer = body.get("sdp")
        sdp_type = body.get("type", "offer")

        if not token_str:
            result = _webrtc_error_response(
                "missing_token",
                status=400,
            )
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        if not sdp_offer:
            result = _webrtc_error_response(
                "missing_sdp",
                status=400,
            )
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        if sdp_type != "offer":
            result = _webrtc_error_response(
                "invalid_sdp_type",
                status=400,
            )
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        # Get WebRTC token manager
        webrtc_manager: WebRTCTokenManager | None = self.hass.data[DOMAIN].get("webrtc_manager")
        if webrtc_manager is None:
            result = _webrtc_error_response("webrtc_not_available", status=500)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        gateway = _webrtc_gateway(self.hass, webrtc_manager)
        if gateway is None:
            result = _webrtc_error_response("webrtc_not_available", status=500)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        result = await _create_webrtc_offer(
            gateway,
            entity_id=entity_id,
            token=token_str,
            sdp_offer=sdp_offer,
        )

        if result.status == 401:
            log_deny(
                _LOGGER,
                client_id="unknown",
                entity_id=entity_id,
                service="webrtc_offer",
                reason="invalid_or_expired_token",
            )
            return _json_response(result.body, self.request, status=result.status)

        if result.status == 500:
            _LOGGER.error("WebRTC offer failed for %s: %s", entity_id, _webrtc_error_message(result))
            log_control(
                _LOGGER,
                client_id="unknown",
                entity_id=entity_id,
                service="webrtc_offer",
                result="go2rtc_error",
            )
            return _json_response(result.body, self.request, status=result.status)

        answer = result.body["data"]
        _LOGGER.info(
            "WebRTC answer generated - entity_id: %s, session_id: %s, sdp_length: %d",
            entity_id,
            answer["session_id"],
            len(answer["sdp"]),
        )
        _LOGGER.debug(
            "WebRTC SDP answer content for %s:\n%s",
            entity_id,
            (
                answer["sdp"][:500] + "..."
                if len(answer["sdp"]) > 500
                else answer["sdp"]
            ),
        )

        log_control(
            _LOGGER,
            client_id="unknown",
            entity_id=entity_id,
            service="webrtc_offer",
            result="success",
        )

        return _json_response(
            result.body, self.request, status=result.status, headers=result.headers
        )


class SmartlyWebRTCICEView(BaseView):
    """Handle POST /api/smartly/camera/{entity_id}/webrtc/ice requests.

    Exchange ICE candidates for NAT traversal.
    """

    async def post(self) -> web.Response:
        """Handle ICE candidate exchange.

        Request:
            POST /api/smartly/camera/{entity_id}/webrtc/ice
            {
                "session_id": "xxxxxxxx",
                "candidate": {
                    "candidate": "candidate:...",
                    "sdpMid": "0",
                    "sdpMLineIndex": 0
                }
            }

        Response:
            {
                "status": "accepted",
                "candidates": [...]  // Server-side candidates if available
            }

        Returns:
            JSON response with acceptance status.
        """
        entity_id = self.request.match_info.get("entity_id", "")

        # Validate entity_id format
        if not entity_id or not entity_id.startswith("camera."):
            result = _webrtc_error_response("invalid_entity_id", status=400)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        # Parse request body
        try:
            body = await self.request.json()
        except json.JSONDecodeError:
            result = _webrtc_error_response("invalid_json", status=400)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        session_id = body.get("session_id")
        candidate = body.get("candidate")

        if not session_id:
            result = _webrtc_error_response("missing_session_id", status=400)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        # Get WebRTC token manager
        webrtc_manager: WebRTCTokenManager | None = self.hass.data[DOMAIN].get("webrtc_manager")
        if webrtc_manager is None:
            result = _webrtc_error_response("webrtc_not_available", status=500)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        gateway = _webrtc_gateway(self.hass, webrtc_manager)
        if gateway is None:
            result = _webrtc_error_response("webrtc_not_available", status=500)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        result = await _add_webrtc_ice_candidate(
            gateway,
            entity_id=entity_id,
            session_id=session_id,
            candidate=candidate,
        )

        if result.status == 200 and candidate:
            _LOGGER.debug(
                "Added ICE candidate for session %s: %s",
                session_id,
                candidate.get("candidate", "")[:50],
            )

        return _json_response(
            result.body, self.request, status=result.status, headers=result.headers
        )


class SmartlyWebRTCHangupView(BaseView):
    """Handle POST /api/smartly/camera/{entity_id}/webrtc/hangup requests.

    Close an active WebRTC session.
    """

    async def post(self) -> web.Response:
        """Close WebRTC session.

        Request:
            POST /api/smartly/camera/{entity_id}/webrtc/hangup
            {
                "session_id": "xxxxxxxx"
            }

        Response:
            {
                "status": "closed"
            }

        Returns:
            JSON response confirming session closure.
        """
        entity_id = self.request.match_info.get("entity_id", "")

        # Parse request body
        try:
            body = await self.request.json()
        except json.JSONDecodeError:
            result = _webrtc_error_response("invalid_json", status=400)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        session_id = body.get("session_id")

        if not session_id:
            result = _webrtc_error_response("missing_session_id", status=400)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        # Get WebRTC token manager
        webrtc_manager: WebRTCTokenManager | None = self.hass.data[DOMAIN].get("webrtc_manager")
        if webrtc_manager is None:
            result = _webrtc_error_response("webrtc_not_available", status=500)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        gateway = _webrtc_gateway(self.hass, webrtc_manager)
        if gateway is None:
            result = _webrtc_error_response("webrtc_not_available", status=500)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        result = await _close_webrtc_session(
            gateway,
            entity_id=entity_id,
            session_id=session_id,
        )

        if result.status != 200:
            return _json_response(
                result.body, self.request, status=result.status, headers=result.headers
            )

        log_control(
            _LOGGER,
            client_id="unknown",
            entity_id=entity_id,
            service="webrtc_hangup",
            result="success",
        )

        return _json_response(
            result.body, self.request, status=result.status, headers=result.headers
        )


# Wrapper classes for Home Assistant view registration


class SmartlyWebRTCTokenViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyWebRTCTokenView to work with HA's view registration."""

    url = API_PATH_WEBRTC_TOKEN
    name = "api:smartly:camera:webrtc:token"
    requires_auth = False  # We handle auth ourselves via HMAC

    async def post(self, request: web.Request, entity_id: str) -> web.Response:
        """Handle POST request."""
        view = SmartlyWebRTCTokenView(request)
        return await view.post()


class SmartlyWebRTCOfferViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyWebRTCOfferView to work with HA's view registration."""

    url = API_PATH_WEBRTC_OFFER
    name = "api:smartly:camera:webrtc:offer"
    requires_auth = False  # We use token-based auth

    async def post(self, request: web.Request, entity_id: str) -> web.Response:
        """Handle POST request."""
        view = SmartlyWebRTCOfferView(request)
        return await view.post()


class SmartlyWebRTCICEViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyWebRTCICEView to work with HA's view registration."""

    url = API_PATH_WEBRTC_ICE
    name = "api:smartly:camera:webrtc:ice"
    requires_auth = False  # We use session-based auth

    async def post(self, request: web.Request, entity_id: str) -> web.Response:
        """Handle POST request."""
        view = SmartlyWebRTCICEView(request)
        return await view.post()


class SmartlyWebRTCHangupViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyWebRTCHangupView to work with HA's view registration."""

    url = API_PATH_WEBRTC_HANGUP
    name = "api:smartly:camera:webrtc:hangup"
    requires_auth = False  # We use session-based auth

    async def post(self, request: web.Request, entity_id: str) -> web.Response:
        """Handle POST request."""
        view = SmartlyWebRTCHangupView(request)
        return await view.post()
