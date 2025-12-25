"""Push state changes to Smartly Platform webhook."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

import aiohttp

from .acl import get_allowed_entities
from .audit import log_push_fail, log_push_success
from .auth import sign_outgoing_request
from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_INSTANCE_ID,
    CONF_PUSH_BATCH_INTERVAL,
    CONF_WEBHOOK_URL,
    DEFAULT_PUSH_BATCH_INTERVAL,
    HEADER_SIGNATURE,
    HEARTBEAT_INTERVAL,
    PUSH_RETRY_BACKOFF_BASE,
    PUSH_RETRY_MAX,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import Event, HomeAssistant, State

_LOGGER = logging.getLogger(__name__)


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
        async with self._lock:
            event_data = {
                "event_type": "state_changed",
                "data": {
                    "entity_id": entity_id,
                    "old_state": self._state_to_dict(old_state) if old_state else None,
                    "new_state": self._state_to_dict(new_state),
                }
            }
            self._pending_events.append(event_data)

    def _state_to_dict(self, state: State) -> dict[str, Any]:
        """Convert State object to dictionary."""
        return {
            "state": state.state,
            "attributes": dict(state.attributes),
            "last_changed": state.last_changed.isoformat() if state.last_changed else None,
            "last_updated": state.last_updated.isoformat() if state.last_updated else None,
        }

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
        from urllib.parse import urlparse

        webhook_url = self.config_entry.data.get(CONF_WEBHOOK_URL)
        if not webhook_url:
            _LOGGER.debug("No webhook URL configured, skipping heartbeat")
            return

        client_secret = self.config_entry.data.get(CONF_CLIENT_SECRET, "")
        instance_id = self.config_entry.data.get(CONF_INSTANCE_ID, "")
        client_id = self.config_entry.data.get(CONF_CLIENT_ID, "")

        payload = {
            "event_type": "heartbeat",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        body = json.dumps(payload).encode("utf-8")

        # Extract path from webhook URL for HMAC signature
        parsed_url = urlparse(webhook_url)
        path = parsed_url.path.rstrip("/")

        try:
            headers = sign_outgoing_request(
                client_secret, instance_id, body, client_id, path
            )

            if self._session is None:
                self._session = aiohttp.ClientSession()

            async with self._session.post(
                webhook_url,
                data=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    _LOGGER.debug("Heartbeat sent successfully")
                else:
                    response_text = await response.text()
                    _LOGGER.warning(
                        "Heartbeat failed with status %d: %s",
                        response.status,
                        response_text[:200],
                    )
        except asyncio.TimeoutError:
            _LOGGER.warning("Heartbeat timeout")
        except aiohttp.ClientError as err:
            _LOGGER.warning("Heartbeat client error: %s", err)
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
        
        # Log request body for debugging
        _LOGGER.debug(
            "Push request body (%d bytes): %s",
            len(body),
            json.dumps(payload, indent=2, ensure_ascii=False)[:1000],
        )
        
        # Extract path from webhook URL for HMAC signature
        # Per platform spec: PATH without query string and without trailing slash
        parsed_url = urlparse(webhook_url)
        path = parsed_url.path.rstrip("/")

        for attempt in range(PUSH_RETRY_MAX):
            try:
                headers = sign_outgoing_request(
                    client_secret, instance_id, body, client_id, path
                )
                
                # Log headers for debugging (mask signature)
                headers_log = headers.copy()
                if HEADER_SIGNATURE in headers_log:
                    headers_log[HEADER_SIGNATURE] = f"{headers_log[HEADER_SIGNATURE][:16]}..."
                _LOGGER.debug(
                    "Push request headers: %s",
                    json.dumps(headers_log, indent=2)
                )

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
                asyncio.create_task(
                    self._queue_event(entity_id, old_state, new_state)
                )

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
