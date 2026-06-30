"""Ports used by framework-independent application use cases."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from ..domain.models import BridgeResponse, CameraSnapshot, CameraStreamInfo, EntityStateSnapshot

if TYPE_CHECKING:
    from .control import SmartlyCommand


class EntityPolicyPort(Protocol):
    """Checks entity and service authorization."""

    def is_entity_allowed(self, entity_id: str) -> bool:
        """Return whether an entity can be accessed by Platform."""

    def is_service_allowed(self, entity_id: str, action: str) -> bool:
        """Return whether an action is allowed for the entity domain."""


class ControlGatewayPort(Protocol):
    """Executes allowed control commands."""

    async def call_service(
        self, entity_id: str, action: str, service_data: dict[str, Any]
    ) -> EntityStateSnapshot | None:
        """Call a Home Assistant service and return the updated entity state."""


class CommandTargetResolverPort(Protocol):
    """Resolves canonical Smartly commands to source control targets."""

    def resolve_command_target(self, device_id: str, capability: str) -> str | None:
        """Return the source entity ID for a logical device capability."""


class AuditPort(Protocol):
    """Records control and denial events."""

    def deny(
        self,
        client_id: str,
        entity_id: str,
        service: str,
        reason: str,
        actor: dict[str, Any] | None = None,
    ) -> None:
        """Record a denied operation."""

    def control(
        self,
        client_id: str,
        entity_id: str,
        service: str,
        result: str,
        actor: dict[str, Any] | None = None,
    ) -> None:
        """Record a control operation."""


class DeviceEventPublisherPort(Protocol):
    """Publishes canonical device events to the runtime event bus."""

    def publish_device_event(self, event_data: dict[str, Any]) -> None:
        """Publish a normalized device event."""


class DeviceEventDeduplicatorPort(Protocol):
    """Tracks event idempotency keys for stateless event ingestion."""

    def event_id_for_key(self, key: str) -> str | None:
        """Return the existing event ID for a key, if it was seen before."""

    def remember_event(self, key: str, event_id: str) -> None:
        """Remember the event ID for an idempotency key."""


class LocalAutomationPort(Protocol):
    """Handles canonical device events with local automation rules."""

    async def handle_device_event(
        self,
        client_id: str,
        event: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Run matching local automations for a canonical event."""


class LocalAutomationRuleStorePort(Protocol):
    """Provides local automation rules."""

    def list_rules(self) -> list[Any]:
        """Return configured local automation rules."""

    def create_rule(self, rule: Any) -> bool:
        """Persist a new local automation rule."""

    def update_rule(self, rule: Any) -> bool:
        """Replace an existing local automation rule."""

    def delete_rule(self, rule_id: str) -> bool:
        """Delete an existing local automation rule."""


class SmartlyCommandExecutorPort(Protocol):
    """Executes canonical Smartly commands."""

    async def execute(self, client_id: str, command: "SmartlyCommand") -> BridgeResponse:
        """Execute a canonical Smartly command."""


class SyncStructurePort(Protocol):
    """Provides the allowed entity structure."""

    def get_structure(self) -> dict[str, Any]:
        """Return the structure payload."""


class SyncStatesPort(Protocol):
    """Provides allowed entity states."""

    async def list_states(self) -> list[EntityStateSnapshot]:
        """Return allowed entity state snapshots."""


class RawDiagnosticStorePort(Protocol):
    """Provides raw diagnostic payloads by raw reference."""

    def get_raw_diagnostic(self, raw_ref: str) -> dict[str, Any] | None:
        """Return a raw diagnostic payload for a reference."""


class RawDiagnosticRecorderPort(Protocol):
    """Stores raw diagnostic payloads by raw reference."""

    def record_raw_diagnostic(self, raw_ref: str, payload: dict[str, Any]) -> None:
        """Record a raw diagnostic payload for a reference."""


class CameraGatewayPort(Protocol):
    """Provides camera operations to application use cases."""

    def list_allowed_camera_ids(self) -> list[str]:
        """Return camera entity IDs allowed for Platform access."""

    def get_camera_state(self, entity_id: str) -> dict[str, Any] | None:
        """Return serializable state metadata for a camera entity."""

    async def get_stream_info(self, entity_id: str) -> CameraStreamInfo | None:
        """Return stream capabilities for a camera."""

    def get_cache_stats(self) -> dict[str, Any]:
        """Return camera snapshot cache statistics."""

    def get_hls_stats(self) -> dict[str, Any]:
        """Return HLS stream statistics."""

    def register_camera(self, config: dict[str, Any]) -> None:
        """Register a camera configuration."""

    def unregister_camera(self, entity_id: str) -> None:
        """Unregister a camera configuration."""

    async def clear_cache(self, entity_id: str | None = None) -> int:
        """Clear camera cache."""

    def list_registered_cameras(self) -> list[dict[str, Any]]:
        """Return registered camera configurations."""

    async def get_snapshot(
        self,
        entity_id: str,
        force_refresh: bool = False,
        if_none_match: str | None = None,
    ) -> tuple[CameraSnapshot | None, bool]:
        """Return a camera snapshot and whether it matched the client cache."""

    async def start_hls_stream(self, entity_id: str) -> dict[str, Any] | None:
        """Start HLS streaming for a camera."""

    async def stop_hls_stream(self, entity_id: str) -> bool:
        """Stop HLS streaming for a camera."""

    async def stream_proxy(self, entity_id: str, request: Any, response: Any) -> None:
        """Proxy an MJPEG camera stream into a prepared response."""


class WebRTCGatewayPort(Protocol):
    """Provides WebRTC token and session operations."""

    def camera_exists(self, entity_id: str) -> bool:
        """Return whether the camera entity exists."""

    async def generate_token(self, entity_id: str, client_id: str) -> Any:
        """Generate a WebRTC token."""

    def get_ice_servers(
        self,
        turn_url: str | None = None,
        turn_username: str | None = None,
        turn_credential: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return ICE servers."""

    def get_session_by_partial_token(self, session_id: str) -> Any | None:
        """Return a WebRTC session by public session id."""

    async def consume_token(self, token: str, entity_id: str) -> Any | None:
        """Consume a WebRTC token and create a session."""

    async def update_session_state(
        self,
        token: str,
        state: str,
        local_sdp: str | None = None,
        remote_sdp: str | None = None,
    ) -> None:
        """Update a WebRTC session state."""

    async def create_webrtc_answer(self, entity_id: str, offer_sdp: str, session: Any) -> str:
        """Create an SDP answer for an offer."""

    async def close_session(self, token: str) -> bool:
        """Close a WebRTC session."""


class HistoryGatewayPort(Protocol):
    """Provides history data to application use cases."""

    async def query_states(
        self,
        entity_id: str,
        start_time: Any,
        end_time: Any,
        significant_changes_only: bool,
    ) -> list[Any]:
        """Return raw history states in recorder order."""

    async def query_batch_states(
        self,
        entity_ids: list[str],
        start_time: Any,
        end_time: Any,
        significant_changes_only: bool,
    ) -> dict[str, list[Any]]:
        """Return raw history states for multiple entities."""

    async def first_state_with_attributes(self, entity_id: str, start_time: Any) -> Any | None:
        """Return the first state with attributes for metadata continuity."""

    async def count_states(
        self,
        entity_id: str,
        start_time: Any,
        end_time: Any,
        significant_changes_only: bool,
    ) -> int:
        """Return total state count for a query."""

    def get_current_attributes(self, entity_id: str) -> dict[str, Any] | None:
        """Return current entity attributes if available."""

    async def query_statistics(
        self,
        entity_id: str,
        start_time: Any,
        end_time: Any,
        period: str,
    ) -> list[dict[str, Any]]:
        """Return recorder statistics for an entity."""
