"""WebRTC application use cases."""

from __future__ import annotations

from typing import Any

from ..domain.models import BridgeResponse
from .ports import WebRTCGatewayPort

SMARTLY_API_SCHEMA_VERSION = "2026.06"


class WebRTCTokenUseCase:
    """Generate a WebRTC token response."""

    def __init__(self, gateway: WebRTCGatewayPort) -> None:
        self._gateway = gateway

    async def execute(
        self,
        *,
        entity_id: str,
        client_id: str,
        turn_config: dict[str, str],
    ) -> BridgeResponse:
        """Generate token and connection metadata."""
        if not self._gateway.camera_exists(entity_id):
            return BridgeResponse(
                {"error": "entity_not_found", "message": f"Camera {entity_id} not found"},
                status=404,
            )

        token = await self._gateway.generate_token(entity_id, client_id)
        ice_servers = self._gateway.get_ice_servers(
            turn_url=turn_config.get("turn_url"),
            turn_username=turn_config.get("turn_username"),
            turn_credential=turn_config.get("turn_credential"),
        )
        return BridgeResponse(
            {
                "token": token.token,
                "expires_at": int(token.expires_at),
                "expires_in": token.remaining_seconds(),
                "entity_id": entity_id,
                "offer_endpoint": f"/api/smartly/camera/{entity_id}/webrtc/offer",
                "ice_endpoint": f"/api/smartly/camera/{entity_id}/webrtc/ice",
                "hangup_endpoint": f"/api/smartly/camera/{entity_id}/webrtc/hangup",
                "ice_servers": ice_servers,
            },
            status=200,
        )


class WebRTCICEUseCase:
    """Handle ICE candidate exchange."""

    def __init__(self, gateway: WebRTCGatewayPort) -> None:
        self._gateway = gateway

    async def execute(
        self,
        *,
        entity_id: str,
        session_id: str,
        candidate: dict[str, Any] | None,
    ) -> BridgeResponse:
        """Add an ICE candidate to a session."""
        session = self._gateway.get_session_by_partial_token(session_id)
        if session is None:
            return _webrtc_error_response("session_not_found", status=404)

        if session.entity_id != entity_id:
            return _webrtc_error_response("session_entity_mismatch", status=403)

        if candidate:
            session.add_ice_candidate(candidate)

        return BridgeResponse({"status": "accepted", "candidates": []}, status=200)


class WebRTCOfferUseCase:
    """Handle SDP offer exchange for a WebRTC session."""

    def __init__(self, gateway: WebRTCGatewayPort) -> None:
        self._gateway = gateway

    async def execute(
        self,
        *,
        entity_id: str,
        token: str,
        sdp_offer: str,
    ) -> BridgeResponse:
        """Consume a token, create an SDP answer, and update session state."""
        session = await self._gateway.consume_token(token, entity_id)
        if session is None:
            return BridgeResponse(
                {"error": "invalid_or_expired_token", "message": "Token is invalid or expired"},
                status=401,
            )

        await self._gateway.update_session_state(
            token=session.token,
            state="connecting",
            remote_sdp=sdp_offer,
        )

        try:
            answer_sdp = await self._gateway.create_webrtc_answer(
                entity_id,
                sdp_offer,
                session,
            )
        except Exception as err:
            return BridgeResponse(
                {
                    "error": "webrtc_failed",
                    "message": str(err),
                    "session_id": session.token[:16],
                },
                status=500,
            )

        await self._gateway.update_session_state(
            token=session.token,
            state="connected",
            local_sdp=answer_sdp,
        )

        return BridgeResponse(
            {
                "type": "answer",
                "sdp": answer_sdp,
                "session_id": session.token[:16],
            },
            status=200,
        )


class WebRTCHangupUseCase:
    """Close a WebRTC session."""

    def __init__(self, gateway: WebRTCGatewayPort) -> None:
        self._gateway = gateway

    async def execute(self, *, entity_id: str, session_id: str) -> BridgeResponse:
        """Close a matching WebRTC session."""
        session = self._gateway.get_session_by_partial_token(session_id)
        if session is None:
            return _webrtc_error_response("session_not_found", status=404)

        if entity_id and session.entity_id != entity_id:
            return BridgeResponse({"error": "session_entity_mismatch"}, status=403)

        await self._gateway.close_session(session.token)
        return BridgeResponse({"status": "closed"}, status=200)


def _webrtc_error_response(error: str, *, status: int) -> BridgeResponse:
    """Return a legacy-compatible API vNext WebRTC error response."""
    return BridgeResponse(
        {
            "error": error,
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": error.upper(),
                    "message": error.replace("_", " "),
                    "target": "webrtc",
                    "retryable": False,
                }
            ],
        },
        status=status,
    )
