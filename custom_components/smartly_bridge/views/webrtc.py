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

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from ..acl import is_entity_allowed
from ..adapters.home_assistant import HomeAssistantWebRTCGateway
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
                legacy_fields={"message": "Entity ID must start with 'camera.'"},
            )
            return web.json_response(
                result.body,
                status=result.status,
                headers=result.headers,
            )

        # Get integration data
        data = self._get_integration_data()
        if data is None:
            result = _webrtc_error_response("integration_not_configured", status=500)
            return web.json_response(
                result.body,
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
            return web.json_response(
                result.body,
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
            return web.json_response(
                result.body,
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
            return web.json_response(
                result.body,
                status=result.status,
                headers=result.headers,
            )

        # Get WebRTC token manager
        webrtc_manager: WebRTCTokenManager | None = self.hass.data[DOMAIN].get("webrtc_manager")
        if webrtc_manager is None:
            result = _webrtc_error_response(
                "webrtc_not_available",
                status=500,
                legacy_fields={"message": "WebRTC manager not initialized"},
            )
            return web.json_response(
                result.body,
                status=result.status,
                headers=result.headers,
            )

        result = await WebRTCTokenUseCase(
            HomeAssistantWebRTCGateway(self.hass, webrtc_manager)
        ).execute(
            entity_id=entity_id,
            client_id=auth_result.client_id or "unknown",
            turn_config={
                "turn_url": data.get(CONF_TURN_URL, "").strip(),
                "turn_username": data.get(CONF_TURN_USERNAME, "").strip(),
                "turn_credential": data.get(CONF_TURN_CREDENTIAL, "").strip(),
            },
        )

        if result.status == 404:
            return web.json_response(result.body, status=result.status)

        log_control(
            _LOGGER,
            client_id=auth_result.client_id or "unknown",
            entity_id=entity_id,
            service="webrtc_token",
            result="success",
        )

        return web.json_response(result.body, status=result.status, headers=result.headers)


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
            return web.json_response(
                result.body,
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
                legacy_fields={"message": "Request body must be valid JSON"},
            )
            return web.json_response(
                result.body,
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
                legacy_fields={"message": "Token is required"},
            )
            return web.json_response(
                result.body,
                status=result.status,
                headers=result.headers,
            )

        if not sdp_offer:
            result = _webrtc_error_response(
                "missing_sdp",
                status=400,
                legacy_fields={"message": "SDP offer is required"},
            )
            return web.json_response(
                result.body,
                status=result.status,
                headers=result.headers,
            )

        if sdp_type != "offer":
            return web.json_response(
                {"error": "invalid_sdp_type", "message": "SDP type must be 'offer'"},
                status=400,
            )

        # Get WebRTC token manager
        webrtc_manager: WebRTCTokenManager | None = self.hass.data[DOMAIN].get("webrtc_manager")
        if webrtc_manager is None:
            return web.json_response(
                {"error": "webrtc_not_available"},
                status=500,
            )

        result = await WebRTCOfferUseCase(
            HomeAssistantWebRTCGateway(self.hass, webrtc_manager)
        ).execute(
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
            return web.json_response(result.body, status=result.status)

        if result.status == 500:
            _LOGGER.error("WebRTC offer failed for %s: %s", entity_id, result.body.get("message"))
            log_control(
                _LOGGER,
                client_id="unknown",
                entity_id=entity_id,
                service="webrtc_offer",
                result="go2rtc_error",
            )
            return web.json_response(result.body, status=result.status)

        _LOGGER.info(
            "WebRTC answer generated - entity_id: %s, session_id: %s, sdp_length: %d",
            entity_id,
            result.body["session_id"],
            len(result.body["sdp"]),
        )
        _LOGGER.debug(
            "WebRTC SDP answer content for %s:\n%s",
            entity_id,
            (
                result.body["sdp"][:500] + "..."
                if len(result.body["sdp"]) > 500
                else result.body["sdp"]
            ),
        )

        log_control(
            _LOGGER,
            client_id="unknown",
            entity_id=entity_id,
            service="webrtc_offer",
            result="success",
        )

        return web.json_response(result.body, status=result.status, headers=result.headers)


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
            return web.json_response(
                {"error": "invalid_entity_id"},
                status=400,
            )

        # Parse request body
        try:
            body = await self.request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"error": "invalid_json"},
                status=400,
            )

        session_id = body.get("session_id")
        candidate = body.get("candidate")

        if not session_id:
            return web.json_response(
                {"error": "missing_session_id"},
                status=400,
            )

        # Get WebRTC token manager
        webrtc_manager: WebRTCTokenManager | None = self.hass.data[DOMAIN].get("webrtc_manager")
        if webrtc_manager is None:
            return web.json_response(
                {"error": "webrtc_not_available"},
                status=500,
            )

        result = await WebRTCICEUseCase(
            HomeAssistantWebRTCGateway(self.hass, webrtc_manager)
        ).execute(
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

        return web.json_response(result.body, status=result.status, headers=result.headers)


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
            return web.json_response(
                {"error": "invalid_json"},
                status=400,
            )

        session_id = body.get("session_id")

        if not session_id:
            return web.json_response(
                {"error": "missing_session_id"},
                status=400,
            )

        # Get WebRTC token manager
        webrtc_manager: WebRTCTokenManager | None = self.hass.data[DOMAIN].get("webrtc_manager")
        if webrtc_manager is None:
            return web.json_response(
                {"error": "webrtc_not_available"},
                status=500,
            )

        result = await WebRTCHangupUseCase(
            HomeAssistantWebRTCGateway(self.hass, webrtc_manager)
        ).execute(entity_id=entity_id, session_id=session_id)

        if result.status != 200:
            return web.json_response(result.body, status=result.status, headers=result.headers)

        log_control(
            _LOGGER,
            client_id="unknown",
            entity_id=entity_id,
            service="webrtc_hangup",
            result="success",
        )

        return web.json_response(result.body, status=result.status, headers=result.headers)


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
