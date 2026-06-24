"""Home Assistant adapters for application ports."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from ..acl import (
    get_allowed_entities,
    get_entity_domain,
    get_structure,
    is_entity_allowed,
    is_service_allowed,
)
from ..audit import log_control, log_deny
from ..const import DEFAULT_DOMAIN_ICONS
from ..domain.models import CameraSnapshot, CameraStreamInfo, EntityStateSnapshot
from ..utils import format_numeric_attributes, format_sensor_state


class LoggingAuditAdapter:
    """Audit adapter backed by the existing logging helpers."""

    def __init__(self, logger: Any) -> None:
        self._logger = logger

    def deny(
        self,
        client_id: str,
        entity_id: str,
        service: str,
        reason: str,
        actor: dict[str, Any] | None = None,
    ) -> None:
        """Record a denied operation."""
        log_deny(
            self._logger,
            client_id=client_id,
            entity_id=entity_id,
            service=service,
            reason=reason,
            actor=actor,
        )

    def control(
        self,
        client_id: str,
        entity_id: str,
        service: str,
        result: str,
        actor: dict[str, Any] | None = None,
    ) -> None:
        """Record a control operation."""
        log_control(
            self._logger,
            client_id=client_id,
            entity_id=entity_id,
            service=service,
            result=result,
            actor=actor,
        )


class HomeAssistantEntityPolicy:
    """Entity and service policy backed by Home Assistant registries."""

    def __init__(
        self,
        hass: Any,
        *,
        entity_allowed_fn: Callable[[Any, str, Any], bool] = is_entity_allowed,
        service_allowed_fn: Callable[[str, str], bool] = is_service_allowed,
    ) -> None:
        self._hass = hass
        self._entity_allowed_fn = entity_allowed_fn
        self._service_allowed_fn = service_allowed_fn

    def is_entity_allowed(self, entity_id: str) -> bool:
        """Return whether an entity can be accessed by Platform."""
        from homeassistant.helpers import entity_registry as er

        return self._entity_allowed_fn(self._hass, entity_id, er.async_get(self._hass))

    def is_service_allowed(self, entity_id: str, action: str) -> bool:
        """Return whether an action is allowed for the entity domain."""
        return self._service_allowed_fn(get_entity_domain(entity_id), action)


class HomeAssistantControlGateway:
    """Control gateway backed by Home Assistant services."""

    def __init__(self, hass: Any, *, sleep_seconds: float = 0.1) -> None:
        self._hass = hass
        self._sleep_seconds = sleep_seconds

    async def call_service(
        self, entity_id: str, action: str, service_data: dict[str, Any]
    ) -> EntityStateSnapshot | None:
        """Call a service and return the updated entity state."""
        domain = get_entity_domain(entity_id)
        await self._hass.services.async_call(
            domain,
            action,
            {"entity_id": entity_id, **service_data},
            blocking=True,
        )
        await asyncio.sleep(self._sleep_seconds)

        state = self._hass.states.get(entity_id)
        if state is None:
            return None
        return EntityStateSnapshot(
            entity_id=entity_id,
            state=state.state,
            attributes=format_numeric_attributes(dict(state.attributes)),
        )


class HomeAssistantSyncGateway:
    """Structure sync gateway backed by Home Assistant registries."""

    def __init__(
        self,
        hass: Any,
        *,
        allowed_entities_fn: Callable[[Any, Any], list[str]] = get_allowed_entities,
        structure_fn: Callable[
            [Any, list[str], Any, Any, Any, Any], dict[str, Any]
        ] = get_structure,
    ) -> None:
        self._hass = hass
        self._allowed_entities_fn = allowed_entities_fn
        self._structure_fn = structure_fn

    def get_structure(self) -> dict[str, Any]:
        """Return the allowed structure payload."""
        from homeassistant.helpers import area_registry as ar
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er
        from homeassistant.helpers import floor_registry as fr

        entity_registry = er.async_get(self._hass)
        allowed_entities = self._allowed_entities_fn(self._hass, entity_registry)
        return self._structure_fn(
            self._hass,
            allowed_entities,
            entity_registry,
            dr.async_get(self._hass),
            ar.async_get(self._hass),
            fr.async_get(self._hass),
        )


class HomeAssistantStateSyncGateway:
    """State sync gateway backed by Home Assistant state and entity registries."""

    def __init__(
        self,
        hass: Any,
        *,
        allowed_entities_fn: Callable[[Any, Any], list[str]] = get_allowed_entities,
    ) -> None:
        self._hass = hass
        self._allowed_entities_fn = allowed_entities_fn

    def list_states(self) -> list[EntityStateSnapshot]:
        """Return allowed entity state snapshots."""
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self._hass)
        allowed_entities = self._allowed_entities_fn(self._hass, entity_registry)

        snapshots: list[EntityStateSnapshot] = []
        for entity_id in allowed_entities:
            state = self._hass.states.get(entity_id)
            if state is None:
                continue

            entry = entity_registry.async_get(entity_id)
            icon = state.attributes.get("icon")
            if not icon and entry:
                icon = entry.icon or entry.original_icon
            if not icon:
                icon = DEFAULT_DOMAIN_ICONS.get(get_entity_domain(entity_id))

            snapshots.append(
                EntityStateSnapshot(
                    entity_id=entity_id,
                    state=format_sensor_state(state.state, state.attributes),
                    attributes=format_numeric_attributes(dict(state.attributes)),
                    last_changed=state.last_changed.isoformat() if state.last_changed else None,
                    last_updated=state.last_updated.isoformat() if state.last_updated else None,
                    icon=icon,
                )
            )
        return snapshots


class HomeAssistantCameraGateway:
    """Camera gateway backed by Home Assistant state and CameraManager."""

    def __init__(
        self,
        hass: Any,
        camera_manager: Any,
        *,
        allowed_entities_fn: Callable[[Any, Any], list[str]] = get_allowed_entities,
    ) -> None:
        self._hass = hass
        self._camera_manager = camera_manager
        self._allowed_entities_fn = allowed_entities_fn

    def list_allowed_camera_ids(self) -> list[str]:
        """Return allowed camera entity IDs."""
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self._hass)
        return [
            entity_id
            for entity_id in self._allowed_entities_fn(self._hass, entity_registry)
            if entity_id.startswith("camera.")
        ]

    def get_camera_state(self, entity_id: str) -> dict[str, Any] | None:
        """Return camera state metadata."""
        state = self._hass.states.get(entity_id)
        if state is None:
            return None

        return {
            "entity_id": entity_id,
            "name": state.attributes.get("friendly_name", entity_id),
            "state": state.state,
            "is_streaming": state.attributes.get("is_streaming", False),
            "brand": state.attributes.get("brand"),
            "model": state.attributes.get("model_name"),
            "supported_features": state.attributes.get("supported_features", 0),
        }

    async def get_stream_info(self, entity_id: str) -> CameraStreamInfo | None:
        """Return camera stream capabilities."""
        if self._camera_manager is None:
            return None

        stream_info = await self._camera_manager.get_stream_info(entity_id)
        if stream_info is None:
            return None

        return CameraStreamInfo(
            entity_id=stream_info.entity_id,
            name=stream_info.name,
            supports_snapshot=stream_info.supports_snapshot,
            supports_mjpeg=stream_info.supports_mjpeg,
            supports_hls=stream_info.supports_hls,
            supports_webrtc=stream_info.supports_webrtc,
            is_streaming=stream_info.is_streaming,
        )

    def get_cache_stats(self) -> dict[str, Any]:
        """Return camera snapshot cache statistics."""
        if self._camera_manager is None:
            return {}
        return self._camera_manager.get_cache_stats()

    def get_hls_stats(self) -> dict[str, Any]:
        """Return HLS statistics."""
        if self._camera_manager is None:
            return {}
        return self._camera_manager.get_hls_stats()

    def register_camera(self, config: dict[str, Any]) -> None:
        """Register a camera configuration."""
        from ..camera import CameraConfig

        self._camera_manager.register_camera(CameraConfig(**config))

    def unregister_camera(self, entity_id: str) -> None:
        """Unregister a camera configuration."""
        self._camera_manager.unregister_camera(entity_id)

    async def clear_cache(self, entity_id: str | None = None) -> int:
        """Clear snapshot cache."""
        return await self._camera_manager.clear_cache(entity_id)

    def list_registered_cameras(self) -> list[dict[str, Any]]:
        """Return registered cameras."""
        return self._camera_manager.list_cameras()

    async def get_snapshot(
        self,
        entity_id: str,
        force_refresh: bool = False,
        if_none_match: str | None = None,
    ) -> tuple[CameraSnapshot | None, bool]:
        """Return a camera snapshot."""
        snapshot, not_modified = await self._camera_manager.get_snapshot(
            entity_id,
            force_refresh=force_refresh,
            if_none_match=if_none_match,
        )
        if snapshot is None:
            return None, not_modified
        return (
            CameraSnapshot(
                entity_id=snapshot.entity_id,
                image_data=snapshot.image_data,
                content_type=snapshot.content_type,
                timestamp=snapshot.timestamp,
                etag=snapshot.etag,
            ),
            not_modified,
        )

    async def start_hls_stream(self, entity_id: str) -> dict[str, Any] | None:
        """Start an HLS stream."""
        return await self._camera_manager.start_hls_stream(entity_id)

    async def stop_hls_stream(self, entity_id: str) -> bool:
        """Stop an HLS stream."""
        return await self._camera_manager.stop_hls_stream(entity_id)


class HomeAssistantWebRTCGateway:
    """WebRTC gateway backed by Home Assistant state and WebRTCTokenManager."""

    def __init__(self, hass: Any, webrtc_manager: Any) -> None:
        self._hass = hass
        self._webrtc_manager = webrtc_manager

    def camera_exists(self, entity_id: str) -> bool:
        """Return whether the camera entity exists."""
        return self._hass.states.get(entity_id) is not None

    async def generate_token(self, entity_id: str, client_id: str) -> Any:
        """Generate a WebRTC token."""
        return await self._webrtc_manager.generate_token(
            entity_id=entity_id,
            client_id=client_id,
        )

    def get_ice_servers(
        self,
        turn_url: str | None = None,
        turn_username: str | None = None,
        turn_credential: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return configured ICE servers."""
        from ..webrtc import get_default_ice_servers, get_ice_servers_with_turn

        if turn_url and turn_username and turn_credential:
            return get_ice_servers_with_turn(turn_url, turn_username, turn_credential)
        return get_default_ice_servers()

    def get_session_by_partial_token(self, session_id: str) -> Any | None:
        """Return a WebRTC session by public session id."""
        return self._webrtc_manager.get_session_by_partial_token(session_id)

    async def consume_token(self, token: str, entity_id: str) -> Any | None:
        """Consume a WebRTC token and create a session."""
        return await self._webrtc_manager.consume_token(token, entity_id)

    async def update_session_state(
        self,
        token: str,
        state: str,
        local_sdp: str | None = None,
        remote_sdp: str | None = None,
    ) -> None:
        """Update a WebRTC session."""
        await self._webrtc_manager.update_session_state(
            token_str=token,
            state=state,
            local_sdp=local_sdp,
            remote_sdp=remote_sdp,
        )

    async def create_webrtc_answer(self, entity_id: str, offer_sdp: str, session: Any) -> str:
        """Create a WebRTC SDP answer through go2rtc."""
        from homeassistant.components.camera import async_get_stream_source
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        from ..const import DOMAIN, GO2RTC_URL, GO2RTC_WEBRTC_TIMEOUT

        stream_source = await async_get_stream_source(self._hass, entity_id)
        if not stream_source:
            raise RuntimeError(f"No stream source available for camera {entity_id}")

        data = self._hass.data.get(DOMAIN, {}).get("config_entry")
        go2rtc_url = GO2RTC_URL
        if data:
            go2rtc_url = data.data.get("go2rtc_url", GO2RTC_URL)

        session_client = async_get_clientsession(self._hass)
        stream_name = entity_id
        payload = {"type": "offer", "sdp": offer_sdp}
        url = f"{go2rtc_url}/api/webrtc"
        params = {"src": stream_name}

        try:
            return await self._post_webrtc_offer(
                session_client,
                url,
                params,
                payload,
                GO2RTC_WEBRTC_TIMEOUT,
            )
        except RuntimeError as err:
            if "404" not in str(err):
                raise

        await self._add_stream_to_go2rtc(
            session_client,
            go2rtc_url,
            stream_name,
            stream_source,
        )
        return await self._post_webrtc_offer(
            session_client,
            url,
            params,
            payload,
            GO2RTC_WEBRTC_TIMEOUT,
            retry=True,
        )

    async def _post_webrtc_offer(
        self,
        session_client: Any,
        url: str,
        params: dict[str, str],
        payload: dict[str, str],
        timeout_seconds: int,
        *,
        retry: bool = False,
    ) -> str:
        import aiohttp
        from aiohttp import ClientTimeout

        timeout = ClientTimeout(total=timeout_seconds)
        try:
            async with session_client.post(
                url,
                params=params,
                json=payload,
                timeout=timeout,
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    answer_sdp = result.get("sdp", "")
                    if answer_sdp:
                        return answer_sdp
                    suffix = " after retry" if retry else ""
                    raise RuntimeError(f"go2rtc returned empty SDP answer{suffix}")

                error_text = await response.text()
                suffix = " after adding stream" if retry else ""
                raise RuntimeError(
                    f"go2rtc WebRTC request failed{suffix}: "
                    f"{response.status} - {error_text}"
                )
        except aiohttp.ClientError as err:
            raise RuntimeError(f"Failed to connect to go2rtc server. Error: {err}") from err

    async def _add_stream_to_go2rtc(
        self,
        session_client: Any,
        go2rtc_url: str,
        stream_name: str,
        stream_source: str,
    ) -> None:
        import aiohttp

        url = f"{go2rtc_url}/api/streams"
        params = {"name": stream_name, "src": stream_source}
        try:
            async with session_client.put(url, params=params) as response:
                await response.text()
        except aiohttp.ClientError:
            return

    async def close_session(self, token: str) -> bool:
        """Close a WebRTC session."""
        return await self._webrtc_manager.close_session(token)


class HomeAssistantHistoryGateway:
    """History gateway backed by Home Assistant Recorder."""

    def __init__(
        self,
        hass: Any,
        semaphore_factory: Callable[[], Any],
    ) -> None:
        self._hass = hass
        self._semaphore_factory = semaphore_factory

    async def query_states(
        self,
        entity_id: str,
        start_time: Any,
        end_time: Any,
        significant_changes_only: bool,
    ) -> list[Any]:
        """Return raw recorder states for an entity."""
        states = await self._query_recorder(
            start_time,
            end_time,
            [entity_id],
            significant_changes_only,
            no_attributes=False,
        )
        return states.get(entity_id, [])

    async def query_batch_states(
        self,
        entity_ids: list[str],
        start_time: Any,
        end_time: Any,
        significant_changes_only: bool,
    ) -> dict[str, list[Any]]:
        """Return raw recorder states for multiple entities."""
        return await self._query_recorder(
            start_time,
            end_time,
            entity_ids,
            significant_changes_only,
            no_attributes=False,
        )

    async def first_state_with_attributes(self, entity_id: str, start_time: Any) -> Any | None:
        """Return the first state with attributes near the query start."""
        from datetime import timedelta

        states = await self._query_recorder(
            start_time,
            start_time + timedelta(seconds=1),
            [entity_id],
            significant_changes_only=True,
            no_attributes=False,
        )
        first_state_list = states.get(entity_id, [])
        if first_state_list:
            return first_state_list[0]
        return None

    async def count_states(
        self,
        entity_id: str,
        start_time: Any,
        end_time: Any,
        significant_changes_only: bool,
    ) -> int:
        """Return total state count for an entity."""
        states = await self._query_recorder(
            start_time,
            end_time,
            [entity_id],
            significant_changes_only,
            no_attributes=True,
        )
        return len(states.get(entity_id, []))

    def get_current_attributes(self, entity_id: str) -> dict[str, Any] | None:
        """Return current entity attributes."""
        current_state = self._hass.states.get(entity_id)
        if current_state and current_state.attributes:
            return dict(current_state.attributes)
        return None

    async def query_statistics(
        self,
        entity_id: str,
        start_time: Any,
        end_time: Any,
        period: str,
    ) -> list[dict[str, Any]]:
        """Return recorder statistics for an entity."""
        from homeassistant.components.recorder.statistics import statistics_during_period
        from homeassistant.helpers.recorder import get_instance

        stat_types = {"mean", "min", "max", "sum", "state"}
        recorder_instance = get_instance(self._hass)
        stat_result = await recorder_instance.async_add_executor_job(
            statistics_during_period,
            self._hass,
            start_time,
            end_time,
            {entity_id},
            period,
            None,
            stat_types,
        )
        return stat_result.get(entity_id, [])

    async def _query_recorder(
        self,
        start_time: Any,
        end_time: Any,
        entity_ids: list[str],
        significant_changes_only: bool,
        no_attributes: bool,
    ) -> dict[str, list[Any]]:
        from homeassistant.components.recorder import history
        from homeassistant.helpers.recorder import get_instance

        semaphore = self._semaphore_factory()
        async with semaphore:
            recorder_instance = get_instance(self._hass)
            return await recorder_instance.async_add_executor_job(
                history.get_significant_states,
                self._hass,
                start_time,
                end_time,
                entity_ids,
                None,
                True,
                significant_changes_only,
                True,
                no_attributes,
                True,
            )
