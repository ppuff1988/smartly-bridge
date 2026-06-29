"""Stateless device event ingestion API view for Smartly Bridge."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from ..adapters.home_assistant import (
    DEVICE_EVENT_TYPE,
    HomeAssistantDeviceEventPublisher,
    InMemoryDeviceEventDeduplicator,
)
from ..application.device_events import (
    DeviceEventCommand,
    DeviceEventUseCase,
    is_supported_button_action,
)
from ..audit import log_deny
from ..auth import RateLimiter, verify_request
from ..const import (
    API_PATH_DEVICE_EVENTS,
    CONF_ALLOWED_CIDRS,
    CONF_CLIENT_SECRET,
    CONF_TRUST_PROXY,
    DEFAULT_TRUST_PROXY,
    DOMAIN,
    RATE_WINDOW,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def _is_valid_timestamp(value: Any) -> bool:
    """Return whether value is an ISO 8601 timestamp string."""
    if not isinstance(value, str) or not value:
        return False

    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


class SmartlyDeviceEventsView(web.View):
    """Handle POST /api/smartly/devices/{device_id}/events requests."""

    def __init__(self, request: web.Request) -> None:
        """Initialize the view."""
        super().__init__(request)
        self.hass: HomeAssistant = request.app["hass"]

    def _get_integration_data(self) -> dict[str, Any] | None:
        """Get integration config entry data."""
        if DOMAIN not in self.hass.data:
            return None

        config_entry = self.hass.data[DOMAIN].get("config_entry")
        if config_entry:
            return config_entry.data

        return None

    async def post(self) -> web.Response:
        """Handle stateless device event request from Platform."""
        try:
            return await self._post()
        except Exception as err:
            _LOGGER.exception("Failed to handle device event")
            return web.json_response(
                {
                    "error": "device_event_failed",
                    "message": f"{type(err).__name__}: {err}",
                },
                status=500,
            )

    async def _post(self) -> web.Response:
        """Handle stateless device event request from Platform."""
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
                entity_id="",
                service="device_event",
                reason=auth_result.error or "auth_failed",
            )
            return web.json_response({"error": auth_result.error}, status=401)

        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id="",
                service="device_event",
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

        try:
            body = await self.request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "invalid_json"}, status=400)

        device_id = self.request.match_info.get("device_id")
        event_type = body.get("type")
        action = body.get("action")
        timestamp = body.get("timestamp")
        meta = body.get("meta", {})

        if not device_id or event_type != "button_action" or not action or not timestamp:
            return web.json_response({"error": "missing_required_fields"}, status=400)

        if not is_supported_button_action(action):
            return web.json_response(
                {"error": "invalid_action", "message": "Unsupported button action"},
                status=400,
            )

        if not _is_valid_timestamp(timestamp):
            return web.json_response({"error": "invalid_timestamp"}, status=400)

        if meta is not None and not isinstance(meta, dict):
            return web.json_response({"error": "invalid_meta"}, status=400)

        deduplicator = self.hass.data[DOMAIN].setdefault(
            "device_event_deduplicator",
            InMemoryDeviceEventDeduplicator(),
        )
        result = await DeviceEventUseCase(
            HomeAssistantDeviceEventPublisher(self.hass),
            deduplicator=deduplicator,
        ).execute(
            auth_result.client_id or "unknown",
            DeviceEventCommand(
                device_id=device_id,
                type=event_type,
                action=action,
                timestamp=timestamp,
                meta=meta or {},
            ),
        )

        return web.json_response(result.body, status=result.status, headers=result.headers)


class SmartlyDeviceEventsViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyDeviceEventsView to work with HA's view registration."""

    url = API_PATH_DEVICE_EVENTS
    name = "api:smartly:device_events"
    requires_auth = False

    async def post(self, request: web.Request, device_id: str | None = None) -> web.Response:
        """Handle POST request."""
        if device_id is not None and "device_id" not in request.match_info:
            request.match_info["device_id"] = device_id
        view = SmartlyDeviceEventsView(request)
        return await view.post()
