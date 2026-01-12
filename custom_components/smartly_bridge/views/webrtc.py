"""WebRTC views for Smartly Bridge integration.

Provides HTTP API endpoints for WebRTC P2P video streaming:
- Token: Generate short-lived tokens for WebRTC connections
- Offer: Handle SDP offer/answer exchange
- ICE: Exchange ICE candidates for NAT traversal
- Hangup: Close WebRTC sessions

Authentication Flow:
1. Platform requests token via HMAC-authenticated endpoint
2. Token (5-min validity) is used for subsequent signaling
3. P2P connection established for direct video streaming
"""

import json
import logging
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from ..acl import is_entity_allowed
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
    DEFAULT_TRUST_PROXY,
    DOMAIN,
    RATE_WINDOW,
)
from ..webrtc import WebRTCTokenManager, get_default_ice_servers
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
            return web.json_response(
                {"error": "invalid_entity_id", "message": "Entity ID must start with 'camera.'"},
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
                service="webrtc_token",
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
                service="webrtc_token",
                reason="entity_not_allowed",
            )
            return web.json_response(
                {"error": "entity_not_allowed"},
                status=403,
            )

        # Check if camera exists
        state = self.hass.states.get(entity_id)
        if state is None:
            return web.json_response(
                {"error": "entity_not_found", "message": f"Camera {entity_id} not found"},
                status=404,
            )

        # Get WebRTC token manager
        webrtc_manager: WebRTCTokenManager | None = self.hass.data[DOMAIN].get("webrtc_manager")
        if webrtc_manager is None:
            return web.json_response(
                {"error": "webrtc_not_available", "message": "WebRTC manager not initialized"},
                status=500,
            )

        # Generate token
        token = await webrtc_manager.generate_token(
            entity_id=entity_id,
            client_id=auth_result.client_id or "unknown",
        )

        log_control(
            _LOGGER,
            client_id=auth_result.client_id or "unknown",
            entity_id=entity_id,
            service="webrtc_token",
            result="success",
        )

        # Return token and connection info
        return web.json_response(
            {
                "token": token.token,
                "expires_at": int(token.expires_at),
                "expires_in": token.remaining_seconds(),
                "entity_id": entity_id,
                "offer_endpoint": f"/api/smartly/camera/{entity_id}/webrtc/offer",
                "ice_endpoint": f"/api/smartly/camera/{entity_id}/webrtc/ice",
                "hangup_endpoint": f"/api/smartly/camera/{entity_id}/webrtc/hangup",
                "ice_servers": get_default_ice_servers(),
            }
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
            return web.json_response(
                {"error": "invalid_entity_id"},
                status=400,
            )

        # Parse request body
        try:
            body = await self.request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"error": "invalid_json", "message": "Request body must be valid JSON"},
                status=400,
            )

        token_str = body.get("token")
        sdp_offer = body.get("sdp")
        sdp_type = body.get("type", "offer")

        if not token_str:
            return web.json_response(
                {"error": "missing_token", "message": "Token is required"},
                status=400,
            )

        if not sdp_offer:
            return web.json_response(
                {"error": "missing_sdp", "message": "SDP offer is required"},
                status=400,
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

        # Consume token and create session
        session = await webrtc_manager.consume_token(token_str, entity_id)

        if session is None:
            log_deny(
                _LOGGER,
                client_id="unknown",
                entity_id=entity_id,
                service="webrtc_offer",
                reason="invalid_or_expired_token",
            )
            return web.json_response(
                {"error": "invalid_or_expired_token", "message": "Token is invalid or expired"},
                status=401,
            )

        # Update session state
        await webrtc_manager.update_session_state(
            token_str=session.token,
            state="connecting",
            remote_sdp=sdp_offer,
        )

        # Generate SDP answer
        # Note: In a full implementation, this would integrate with
        # Home Assistant's WebRTC/go2rtc or aiortc for actual WebRTC handling
        try:
            answer_sdp = await self._create_webrtc_answer(entity_id, sdp_offer, session)
        except NotImplementedError:
            # Return placeholder response for now
            # Real implementation would integrate with HA's stream component
            log_control(
                _LOGGER,
                client_id=session.client_id,
                entity_id=entity_id,
                service="webrtc_offer",
                result="pending_implementation",
            )
            return web.json_response(
                {
                    "type": "answer",
                    "sdp": "",  # Placeholder
                    "session_id": session.token[:16],
                    "status": "pending",
                    "message": "WebRTC SDP answer generation requires go2rtc integration",
                }
            )
        except Exception as ex:
            _LOGGER.error("Failed to create WebRTC answer for %s: %s", entity_id, ex)
            return web.json_response(
                {"error": "webrtc_failed", "message": str(ex)},
                status=500,
            )

        # Update session with answer
        await webrtc_manager.update_session_state(
            token_str=session.token,
            state="connected",
            local_sdp=answer_sdp,
        )

        log_control(
            _LOGGER,
            client_id=session.client_id,
            entity_id=entity_id,
            service="webrtc_offer",
            result="success",
        )

        return web.json_response(
            {
                "type": "answer",
                "sdp": answer_sdp,
                "session_id": session.token[:16],
            }
        )

    async def _create_webrtc_answer(
        self,
        entity_id: str,
        offer_sdp: str,
        session: Any,
    ) -> str:
        """Create WebRTC SDP answer.

        This method should integrate with Home Assistant's WebRTC
        infrastructure (go2rtc) to generate a proper SDP answer.

        Args:
            entity_id: Camera entity ID.
            offer_sdp: SDP offer from client.
            session: WebRTC session object.

        Returns:
            SDP answer string.

        Raises:
            NotImplementedError: When go2rtc integration is not available.
        """
        # Check if go2rtc/WebRTC is available in Home Assistant
        # This is where you'd integrate with HA's stream component
        #
        # Example integration points:
        # 1. homeassistant.components.camera.async_get_stream_source
        # 2. homeassistant.components.stream for stream management
        # 3. go2rtc integration for WebRTC handling
        #
        # For now, raise NotImplementedError to indicate pending implementation
        raise NotImplementedError(
            "WebRTC answer generation requires go2rtc integration. "
            "Please ensure go2rtc is configured in Home Assistant."
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

        # Find session by partial token
        session = webrtc_manager.get_session_by_partial_token(session_id)

        if session is None:
            return web.json_response(
                {"error": "session_not_found"},
                status=404,
            )

        if session.entity_id != entity_id:
            return web.json_response(
                {"error": "session_entity_mismatch"},
                status=403,
            )

        # Add ICE candidate to session
        if candidate:
            session.add_ice_candidate(candidate)
            _LOGGER.debug(
                "Added ICE candidate for session %s: %s",
                session_id,
                candidate.get("candidate", "")[:50],
            )

        # Return any server-side ICE candidates
        # In full implementation, these would come from go2rtc
        return web.json_response(
            {
                "status": "accepted",
                "candidates": [],  # Server-side candidates would go here
            }
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

        # Find and close session
        session = webrtc_manager.get_session_by_partial_token(session_id)

        if session is None:
            return web.json_response(
                {"error": "session_not_found"},
                status=404,
            )

        if entity_id and session.entity_id != entity_id:
            return web.json_response(
                {"error": "session_entity_mismatch"},
                status=403,
            )

        # Close the session
        await webrtc_manager.close_session(session.token)

        log_control(
            _LOGGER,
            client_id=session.client_id,
            entity_id=session.entity_id,
            service="webrtc_hangup",
            result="success",
        )

        return web.json_response({"status": "closed"})


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
