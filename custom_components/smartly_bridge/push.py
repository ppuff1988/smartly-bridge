"""Push state changes to Smartly Platform webhook."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Callable

import aiohttp

from .acl import get_allowed_entities
from .audit import log_push_fail, log_push_success
from .auth import sign_outgoing_request
from .const import (
    BRIDGE_CHART_LOOKBACK_HOURS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_INSTANCE_ID,
    CONF_PUSH_BATCH_INTERVAL,
    CONF_WEBHOOK_URL,
    DEFAULT_PUSH_BATCH_INTERVAL,
    DOMAIN,
    HEADER_SIGNATURE,
    HEARTBEAT_INTERVAL,
    MAX_CONCURRENT_HISTORY_QUERIES,
    PUSH_RETRY_BACKOFF_BASE,
    PUSH_RETRY_MAX,
)
from .utils import (
    build_bridge_chart,
    build_bridge_chart_from_states,
    format_numeric_attributes,
    format_sensor_state,
    numeric_state_value,
    signal_attribute_key_for_entity,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import Event, HomeAssistant, State

_LOGGER = logging.getLogger(__name__)


def _history_end_time(value: Any) -> datetime:
    """Return a timezone-aware history query end time."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    return datetime.now(timezone.utc)


def _push_history_gateway(hass: HomeAssistant, semaphore_factory: Callable[[], Any]) -> Any | None:
    """Return the setup-created history gateway for push."""
    integration_data = hass.data.get(DOMAIN)
    if isinstance(integration_data, dict):
        runtime_adapters = integration_data.setdefault("runtime_adapters", {})
        return runtime_adapters.get("history_gateway")
    return None


class StatePushManager:
    """Manages pushing state changes to Platform webhook."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the push manager."""
        self.hass = hass
        self.config_entry = config_entry
        self._pending_events: list[dict[str, Any]] = []
        self._batch_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._unsub_state_changed: Callable[[], None] | None = None
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()
        self._history_semaphore = asyncio.Semaphore(MAX_CONCURRENT_HISTORY_QUERIES)

    async def start(self) -> None:
        """Start listening for state changes."""
        from homeassistant.core import callback
        from homeassistant.helpers import entity_registry as er
        from homeassistant.helpers.event import async_track_state_change_event

        self._session = aiohttp.ClientSession()

        entity_registry = er.async_get(self.hass)
        allowed_entities = get_allowed_entities(self.hass, entity_registry)

        if not allowed_entities:
            _LOGGER.warning("No entities with smartly label found")
            return

        @callback
        def state_changed_listener(event: Event) -> None:
            """Handle state changed events."""
            entity_id = event.data.get("entity_id")
            old_state = event.data.get("old_state")
            new_state = event.data.get("new_state")

            if entity_id and new_state:
                asyncio.create_task(self._queue_event(entity_id, old_state, new_state))

        # Track state changes for allowed entities
        self._unsub_state_changed = async_track_state_change_event(
            self.hass,
            allowed_entities,
            state_changed_listener,
        )

        # Start batch processing task
        self._batch_task = asyncio.create_task(self._batch_loop())

        # Start heartbeat task
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        _LOGGER.info(
            "StatePushManager started, tracking %d entities",
            len(allowed_entities),
        )

    async def stop(self) -> None:
        """Stop listening and clean up."""
        self._stop_event.set()

        if self._unsub_state_changed:
            self._unsub_state_changed()
            self._unsub_state_changed = None

        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
            self._batch_task = None

        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        # Flush remaining events
        if self._pending_events:
            await self._flush_events()

        if self._session:
            await self._session.close()
            self._session = None

        _LOGGER.info("StatePushManager stopped")

    async def _queue_event(
        self,
        entity_id: str,
        old_state: State | None,
        new_state: State,
    ) -> None:
        """Queue a state change event for batch processing."""
        new_state_data = self._state_to_dict(new_state, entity_id)
        bridge_chart = await self._bridge_chart_for_state(entity_id, new_state)
        if bridge_chart is not None:
            new_state_data["attributes"]["bridge_chart"] = bridge_chart

        async with self._lock:
            event_data = {
                "event_type": "state_changed",
                "entity_id": entity_id,
                "old_state": self._state_to_dict(old_state, entity_id) if old_state else None,
                "new_state": new_state_data,
                "state": new_state_data["state"],
                "attributes": new_state_data["attributes"],
                "last_changed": new_state_data["last_changed"],
                "last_updated": new_state_data["last_updated"],
                "timestamp": new_state.last_changed.isoformat() if new_state.last_changed else None,
            }
            self._pending_events.append(event_data)

    def _get_history_semaphore(self) -> asyncio.Semaphore:
        """Return the recorder query semaphore for bridge chart preloading."""
        return self._history_semaphore

    def _history_gateway(self) -> Any | None:
        """Return the setup-created history gateway."""
        return _push_history_gateway(self.hass, self._get_history_semaphore)

    async def _bridge_chart_for_state(self, entity_id: str, state: State) -> dict[str, Any] | None:
        """Return recent bridge chart history for an eligible sensor."""
        attributes = format_numeric_attributes(dict(state.attributes))
        device_class = attributes.get("device_class")
        unit = attributes.get("unit_of_measurement")
        fallback_timestamp = state.last_updated.isoformat() if state.last_updated else None
        fallback_chart = build_bridge_chart_from_states(
            [],
            device_class,
            unit,
            fallback_state=state.state,
            fallback_timestamp=fallback_timestamp,
        )
        if fallback_chart is None:
            return None

        end_time = _history_end_time(getattr(state, "last_updated", None))
        start_time = end_time - timedelta(hours=BRIDGE_CHART_LOOKBACK_HOURS)
        history_gateway = self._history_gateway()
        if history_gateway is None:
            return fallback_chart
        history_states = await history_gateway.query_states(
            entity_id,
            start_time,
            end_time,
            significant_changes_only=True,
        )
        return (
            build_bridge_chart_from_states(
                history_states,
                device_class,
                unit,
                fallback_state=state.state,
                fallback_timestamp=fallback_timestamp,
            )
            or fallback_chart
        )

    def _state_to_dict(self, state: State, entity_id: str | None = None) -> dict[str, Any]:
        """Convert State object to dictionary."""
        # Format attributes (for complex devices with numeric values in attributes)
        raw_attributes = dict(state.attributes)
        if entity_id is not None:
            for key, value in self._sibling_signal_attributes(entity_id).items():
                raw_attributes.setdefault(key, value)
        formatted_attrs = format_numeric_attributes(raw_attributes)

        # Format the state value using the shared formatting function
        formatted_state = format_sensor_state(state.state, state.attributes)
        last_updated = state.last_updated.isoformat() if state.last_updated else None
        chart = build_bridge_chart(
            state.state,
            last_updated,
            formatted_attrs.get("device_class"),
            formatted_attrs.get("unit_of_measurement"),
        )
        if chart is not None:
            formatted_attrs["bridge_chart"] = chart

        return {
            "state": formatted_state,
            "attributes": formatted_attrs,
            "last_changed": state.last_changed.isoformat() if state.last_changed else None,
            "last_updated": last_updated,
        }

    def _sibling_signal_attributes(self, entity_id: str) -> dict[str, int | float]:
        """Return signal attributes exposed by sibling diagnostic entities."""
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self.hass)
        try:
            entry = entity_registry.async_get(entity_id)
        except AttributeError:
            return {}
        device_id = getattr(entry, "device_id", None) if entry else None
        if not device_id:
            return {}

        signal_attributes: dict[str, int | float] = {}
        for registry_entity_id, sibling in getattr(entity_registry, "entities", {}).items():
            sibling_entity_id = getattr(sibling, "entity_id", None)
            if not isinstance(sibling_entity_id, str):
                sibling_entity_id = (
                    registry_entity_id if isinstance(registry_entity_id, str) else None
                )
            if not sibling_entity_id or getattr(sibling, "device_id", None) != device_id:
                continue

            key = signal_attribute_key_for_entity(sibling_entity_id)
            if key is None:
                continue

            sibling_state = self.hass.states.get(sibling_entity_id)
            value = numeric_state_value(
                getattr(sibling_state, "state", None) if sibling_state else None
            )
            if value is not None:
                signal_attributes[key] = value

        return signal_attributes

    async def _batch_loop(self) -> None:
        """Process batched events at intervals."""
        batch_interval = self.config_entry.data.get(
            CONF_PUSH_BATCH_INTERVAL, DEFAULT_PUSH_BATCH_INTERVAL
        )

        while not self._stop_event.is_set():
            await asyncio.sleep(batch_interval)

            if self._pending_events:
                await self._flush_events()

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat to Platform."""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                if self._stop_event.is_set():
                    break
                await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as ex:
                _LOGGER.warning("Heartbeat failed: %s", ex)

    async def _send_heartbeat(self) -> None:
        """Send heartbeat request to Platform."""
        from datetime import datetime, timezone

        webhook_url = self.config_entry.data.get(CONF_WEBHOOK_URL)
        if not webhook_url:
            _LOGGER.debug("No webhook URL configured, skipping heartbeat")
            return

        # Create heartbeat event with same structure as state events
        heartbeat_event = {
            "event_type": "heartbeat",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Send heartbeat immediately using the same retry logic as state events
        try:
            await self._send_with_retry(webhook_url, [heartbeat_event])
        except Exception as ex:
            _LOGGER.warning("Failed to send heartbeat: %s", ex)

    async def _flush_events(self) -> None:
        """Send pending events to Platform."""
        async with self._lock:
            if not self._pending_events:
                return

            events_to_send = self._pending_events.copy()
            self._pending_events.clear()

        webhook_url = self.config_entry.data.get(CONF_WEBHOOK_URL)
        if not webhook_url:
            _LOGGER.debug("No webhook URL configured, skipping push")
            return

        await self._send_with_retry(webhook_url, events_to_send)

    async def _send_with_retry(
        self,
        webhook_url: str,
        events: list[dict[str, Any]],
    ) -> None:
        """Send events with exponential backoff retry."""
        from urllib.parse import urlparse

        client_secret = self.config_entry.data.get(CONF_CLIENT_SECRET, "")
        instance_id = self.config_entry.data.get(CONF_INSTANCE_ID, "")
        client_id = self.config_entry.data.get(CONF_CLIENT_ID, "")

        # Batch events in events array
        payload = {"events": events}
        body = json.dumps(payload).encode("utf-8")

        # Extract path from webhook URL for HMAC signature
        # Per platform spec: PATH without query string and without trailing slash
        parsed_url = urlparse(webhook_url)
        path = parsed_url.path.rstrip("/")

        for attempt in range(PUSH_RETRY_MAX):
            try:
                headers = sign_outgoing_request(client_secret, instance_id, body, client_id, path)

                # Log headers for debugging (mask signature)
                headers_log = headers.copy()
                if HEADER_SIGNATURE in headers_log:
                    headers_log[HEADER_SIGNATURE] = f"{headers_log[HEADER_SIGNATURE][:16]}..."

                async with self._session.post(
                    webhook_url,
                    data=body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        log_push_success(
                            _LOGGER,
                            instance_id=instance_id,
                            event_count=len(events),
                        )
                        return

                    elif response.status == 429:
                        # Rate limited, wait and retry
                        retry_after = int(response.headers.get("Retry-After", "60"))
                        _LOGGER.warning(
                            "Platform rate limited, waiting %ds",
                            retry_after,
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    else:
                        response_text = await response.text()
                        _LOGGER.error(
                            "Push failed with status %d to %s: %s",
                            response.status,
                            webhook_url,
                            response_text[:200],
                        )
                        # For 404, stop retrying immediately
                        if response.status == 404:
                            _LOGGER.error(
                                "Webhook URL not found (404). "
                                "Please check the webhook URL configuration: %s",
                                webhook_url,
                            )
                            return

            except asyncio.TimeoutError:
                _LOGGER.warning(
                    "Push timeout (attempt %d/%d)",
                    attempt + 1,
                    PUSH_RETRY_MAX,
                )
            except aiohttp.ClientError as err:
                _LOGGER.error(
                    "Push client error (attempt %d/%d): %s",
                    attempt + 1,
                    PUSH_RETRY_MAX,
                    err,
                )
            except Exception as err:
                _LOGGER.exception(
                    "Unexpected push error (attempt %d/%d): %s",
                    attempt + 1,
                    PUSH_RETRY_MAX,
                    err,
                )

            # Exponential backoff
            if attempt < PUSH_RETRY_MAX - 1:
                backoff = PUSH_RETRY_BACKOFF_BASE**attempt
                await asyncio.sleep(backoff)

        # All retries failed
        log_push_fail(
            _LOGGER,
            instance_id=instance_id,
            event_count=len(events),
            reason=f"max_retries_exceeded, webhook_url={webhook_url}",
        )

    async def refresh_tracked_entities(self) -> None:
        """Refresh the list of tracked entities."""
        # Stop current tracking
        if self._unsub_state_changed:
            self._unsub_state_changed()
            self._unsub_state_changed = None

        from homeassistant.core import callback
        from homeassistant.helpers import entity_registry as er
        from homeassistant.helpers.event import async_track_state_change_event

        entity_registry = er.async_get(self.hass)
        allowed_entities = get_allowed_entities(self.hass, entity_registry)

        if not allowed_entities:
            _LOGGER.warning("No entities with smartly label found")
            return

        @callback
        def state_changed_listener(event: Event) -> None:
            """Handle state changed events."""
            entity_id = event.data.get("entity_id")
            old_state = event.data.get("old_state")
            new_state = event.data.get("new_state")

            if entity_id and new_state:
                asyncio.create_task(self._queue_event(entity_id, old_state, new_state))

        # Track state changes for allowed entities
        self._unsub_state_changed = async_track_state_change_event(
            self.hass,
            allowed_entities,
            state_changed_listener,
        )

        _LOGGER.info(
            "Refreshed entity tracking, now tracking %d entities",
            len(allowed_entities),
        )
