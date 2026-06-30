"""Tests for WebRTC application use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

import pytest

from custom_components.smartly_bridge.application.webrtc import (
    WebRTCHangupUseCase,
    WebRTCICEUseCase,
    WebRTCOfferUseCase,
    WebRTCTokenUseCase,
)


def _fixture(name: str) -> dict[str, Any]:
    """Load an API vNext fixture."""
    return json.loads(
        (Path(__file__).parent / "fixtures" / "api-vnext" / name).read_text()
    )


@dataclass
class FakeToken:
    """Fake WebRTC token."""

    token: str
    expires_at: float = 1000
    expires_in: int = 300

    def remaining_seconds(self) -> int:
        return self.expires_in


@dataclass
class FakeSession:
    """Fake WebRTC session."""

    token: str
    entity_id: str
    client_id: str = "client-1"
    ice_candidates: list[dict[str, Any]] = field(default_factory=list)

    def add_ice_candidate(self, candidate: dict[str, Any]) -> None:
        self.ice_candidates.append(candidate)


class FakeWebRTCGateway:
    """Fake WebRTC port."""

    def __init__(self) -> None:
        self.session = FakeSession("abcdef1234567890-full", "camera.front")
        self.closed: list[str] = []
        self.consumed: list[tuple[str, str]] = []
        self.state_updates: list[dict[str, str | None]] = []
        self.answer_sdp = "answer-sdp"
        self.answer_error: RuntimeError | None = None

    def camera_exists(self, entity_id: str) -> bool:
        return entity_id == "camera.front"

    async def generate_token(self, entity_id: str, client_id: str) -> FakeToken:
        return FakeToken("token-123", expires_at=2000, expires_in=250)

    def get_ice_servers(
        self,
        turn_url: str | None = None,
        turn_username: str | None = None,
        turn_credential: str | None = None,
    ) -> list[dict[str, Any]]:
        servers = [{"urls": "stun:stun.example.com:19302"}]
        if turn_url and turn_username and turn_credential:
            servers.append(
                {"urls": turn_url, "username": turn_username, "credential": turn_credential}
            )
        return servers

    def get_session_by_partial_token(self, session_id: str) -> FakeSession | None:
        if self.session.token.startswith(session_id):
            return self.session
        return None

    async def consume_token(self, token: str, entity_id: str) -> FakeSession | None:
        self.consumed.append((token, entity_id))
        if token == "valid-token" and entity_id == self.session.entity_id:
            return self.session
        return None

    async def update_session_state(
        self,
        token: str,
        state: str,
        local_sdp: str | None = None,
        remote_sdp: str | None = None,
    ) -> None:
        self.state_updates.append(
            {
                "token": token,
                "state": state,
                "local_sdp": local_sdp,
                "remote_sdp": remote_sdp,
            }
        )

    async def create_webrtc_answer(
        self,
        entity_id: str,
        offer_sdp: str,
        session: FakeSession,
    ) -> str:
        if self.answer_error:
            raise self.answer_error
        return self.answer_sdp

    async def close_session(self, token: str) -> bool:
        self.closed.append(token)
        return True


@pytest.mark.asyncio
async def test_webrtc_token_use_case_returns_connection_info() -> None:
    """Token use case builds the Platform response from a gateway token."""
    result = await WebRTCTokenUseCase(FakeWebRTCGateway()).execute(
        entity_id="camera.front",
        client_id="client-1",
        turn_config={
            "turn_url": "turn:turn.example.com:3478",
            "turn_username": "user",
            "turn_credential": "secret",
        },
    )

    assert result.status == 200
    assert result.body["token"] == "token-123"
    assert result.body["expires_at"] == 2000
    assert result.body["expires_in"] == 250
    assert result.body["offer_endpoint"] == "/api/smartly/camera/camera.front/webrtc/offer"
    assert result.body["ice_servers"][1]["urls"] == "turn:turn.example.com:3478"
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {
        "token": "token-123",
        "expires_at": 2000,
        "expires_in": 250,
        "entity_id": "camera.front",
        "offer_endpoint": "/api/smartly/camera/camera.front/webrtc/offer",
        "ice_endpoint": "/api/smartly/camera/camera.front/webrtc/ice",
        "hangup_endpoint": "/api/smartly/camera/camera.front/webrtc/hangup",
        "ice_servers": [
            {"urls": "stun:stun.example.com:19302"},
            {
                "urls": "turn:turn.example.com:3478",
                "username": "user",
                "credential": "secret",
            },
        ],
    }


@pytest.mark.asyncio
async def test_webrtc_token_response_matches_api_vnext_fixture() -> None:
    """WebRTC token full response remains stable for legacy and vNext clients."""
    result = await WebRTCTokenUseCase(FakeWebRTCGateway()).execute(
        entity_id="camera.front",
        client_id="client-1",
        turn_config={
            "turn_url": "turn:turn.example.com:3478",
            "turn_username": "user",
            "turn_credential": "secret",
        },
    )

    assert result.status == 200
    assert result.body == _fixture("webrtc-token.json")


@pytest.mark.asyncio
async def test_webrtc_token_use_case_rejects_missing_camera() -> None:
    """Token use case reports not found before asking for a token."""
    result = await WebRTCTokenUseCase(FakeWebRTCGateway()).execute(
        entity_id="camera.missing",
        client_id="client-1",
        turn_config={},
    )

    assert result.status == 404
    assert result.body["error"] == "entity_not_found"
    assert result.body["message"] == "Camera camera.missing not found"
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "ENTITY_NOT_FOUND",
            "message": "entity not found",
            "target": "webrtc",
            "retryable": False,
        }
    ]


@pytest.mark.asyncio
async def test_webrtc_token_camera_missing_response_matches_api_vnext_fixture() -> None:
    """WebRTC token missing-camera response remains stable for legacy clients."""
    result = await WebRTCTokenUseCase(FakeWebRTCGateway()).execute(
        entity_id="camera.missing",
        client_id="client-1",
        turn_config={},
    )

    assert result.status == 404
    assert result.body == _fixture("webrtc-token-camera-missing.json")


@pytest.mark.asyncio
async def test_webrtc_ice_use_case_adds_candidate() -> None:
    """ICE use case validates the session and appends the candidate."""
    gateway = FakeWebRTCGateway()
    candidate = {"candidate": "candidate:1", "sdpMid": "0"}

    result = await WebRTCICEUseCase(gateway).execute(
        entity_id="camera.front",
        session_id="abcdef1234567890",
        candidate=candidate,
    )

    assert result.status == 200
    assert result.body["status"] == "accepted"
    assert result.body["candidates"] == []
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {"status": "accepted", "candidates": []}
    assert gateway.session.ice_candidates == [candidate]


@pytest.mark.asyncio
async def test_webrtc_ice_use_case_returns_vnext_error_for_missing_session() -> None:
    """ICE use case reports missing sessions with API vNext errors."""
    gateway = FakeWebRTCGateway()

    result = await WebRTCICEUseCase(gateway).execute(
        entity_id="camera.front",
        session_id="missing-session",
        candidate={"candidate": "candidate:1"},
    )

    assert result.status == 404
    assert result.body["error"] == "session_not_found"
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "SESSION_NOT_FOUND",
            "message": "session not found",
            "target": "webrtc",
            "retryable": False,
        }
    ]
    assert gateway.session.ice_candidates == []


@pytest.mark.asyncio
async def test_webrtc_ice_use_case_returns_vnext_error_for_entity_mismatch() -> None:
    """ICE use case reports entity mismatches with API vNext errors."""
    gateway = FakeWebRTCGateway()

    result = await WebRTCICEUseCase(gateway).execute(
        entity_id="camera.back",
        session_id="abcdef1234567890",
        candidate={"candidate": "candidate:1"},
    )

    assert result.status == 403
    assert result.body["error"] == "session_entity_mismatch"
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "SESSION_ENTITY_MISMATCH",
            "message": "session entity mismatch",
            "target": "webrtc",
            "retryable": False,
        }
    ]
    assert gateway.session.ice_candidates == []


@pytest.mark.asyncio
async def test_webrtc_hangup_use_case_closes_matching_session() -> None:
    """Hangup use case closes the session through the gateway."""
    gateway = FakeWebRTCGateway()

    result = await WebRTCHangupUseCase(gateway).execute(
        entity_id="camera.front",
        session_id="abcdef1234567890",
    )

    assert result.status == 200
    assert result.body["status"] == "closed"
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {"status": "closed"}
    assert gateway.closed == ["abcdef1234567890-full"]


@pytest.mark.asyncio
async def test_webrtc_hangup_use_case_returns_vnext_error_for_missing_session() -> None:
    """Hangup use case reports missing sessions with API vNext errors."""
    gateway = FakeWebRTCGateway()

    result = await WebRTCHangupUseCase(gateway).execute(
        entity_id="camera.front",
        session_id="missing-session",
    )

    assert result.status == 404
    assert result.body["error"] == "session_not_found"
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "SESSION_NOT_FOUND",
            "message": "session not found",
            "target": "webrtc",
            "retryable": False,
        }
    ]
    assert gateway.closed == []


@pytest.mark.asyncio
async def test_webrtc_hangup_use_case_returns_vnext_error_for_entity_mismatch() -> None:
    """Hangup use case reports entity mismatches with API vNext errors."""
    gateway = FakeWebRTCGateway()

    result = await WebRTCHangupUseCase(gateway).execute(
        entity_id="camera.back",
        session_id="abcdef1234567890",
    )

    assert result.status == 403
    assert result.body["error"] == "session_entity_mismatch"
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "SESSION_ENTITY_MISMATCH",
            "message": "session entity mismatch",
            "target": "webrtc",
            "retryable": False,
        }
    ]
    assert gateway.closed == []


@pytest.mark.asyncio
async def test_webrtc_offer_use_case_creates_answer_and_updates_session() -> None:
    """Offer use case consumes a token, signals the gateway, and returns an answer."""
    gateway = FakeWebRTCGateway()

    result = await WebRTCOfferUseCase(gateway).execute(
        entity_id="camera.front",
        token="valid-token",
        sdp_offer="offer-sdp",
    )

    assert result.status == 200
    expected_answer = {
        "type": "answer",
        "sdp": "answer-sdp",
        "session_id": "abcdef1234567890",
    }
    assert result.body["type"] == "answer"
    assert result.body["sdp"] == "answer-sdp"
    assert result.body["session_id"] == "abcdef1234567890"
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == expected_answer
    assert gateway.consumed == [("valid-token", "camera.front")]
    assert gateway.state_updates == [
        {
            "token": "abcdef1234567890-full",
            "state": "connecting",
            "local_sdp": None,
            "remote_sdp": "offer-sdp",
        },
        {
            "token": "abcdef1234567890-full",
            "state": "connected",
            "local_sdp": "answer-sdp",
            "remote_sdp": None,
        },
    ]


@pytest.mark.asyncio
async def test_webrtc_offer_use_case_rejects_invalid_token() -> None:
    """Offer use case reports invalid or expired tokens."""
    result = await WebRTCOfferUseCase(FakeWebRTCGateway()).execute(
        entity_id="camera.front",
        token="invalid-token",
        sdp_offer="offer-sdp",
    )

    assert result.status == 401
    assert result.body["error"] == "invalid_or_expired_token"
    assert result.body["message"] == "Token is invalid or expired"
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "INVALID_OR_EXPIRED_TOKEN",
            "message": "invalid or expired token",
            "target": "webrtc",
            "retryable": False,
        }
    ]


@pytest.mark.asyncio
async def test_webrtc_offer_invalid_token_response_matches_api_vnext_fixture() -> None:
    """WebRTC offer invalid-token response remains stable for legacy clients."""
    result = await WebRTCOfferUseCase(FakeWebRTCGateway()).execute(
        entity_id="camera.front",
        token="invalid-token",
        sdp_offer="offer-sdp",
    )

    assert result.status == 401
    assert result.body == _fixture("webrtc-offer-invalid-token.json")


@pytest.mark.asyncio
async def test_webrtc_offer_use_case_reports_signaling_failure() -> None:
    """Offer use case returns the session id when answer creation fails."""
    gateway = FakeWebRTCGateway()
    gateway.answer_error = RuntimeError("go2rtc failed")

    result = await WebRTCOfferUseCase(gateway).execute(
        entity_id="camera.front",
        token="valid-token",
        sdp_offer="offer-sdp",
    )

    assert result.status == 500
    assert result.body["error"] == "webrtc_failed"
    assert result.body["message"] == "go2rtc failed"
    assert result.body["session_id"] == "abcdef1234567890"
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "WEBRTC_FAILED",
            "message": "webrtc failed",
            "target": "webrtc",
            "retryable": False,
        }
    ]


@pytest.mark.asyncio
async def test_webrtc_offer_signaling_failure_response_matches_api_vnext_fixture() -> None:
    """WebRTC offer signaling failure keeps legacy session id and vNext errors."""
    gateway = FakeWebRTCGateway()
    gateway.answer_error = RuntimeError("go2rtc failed")

    result = await WebRTCOfferUseCase(gateway).execute(
        entity_id="camera.front",
        token="valid-token",
        sdp_offer="offer-sdp",
    )

    assert result.status == 500
    assert result.body == _fixture("webrtc-offer-signaling-failure.json")
