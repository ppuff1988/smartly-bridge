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
    HomeAssistantLocalAutomationRuleStore,
    HomeAssistantSmartlyCommandExecutor,
    InMemoryDeviceEventDeduplicator,
)
from ..application.device_events import (
    DeviceEventCommand,
    DeviceEventUseCase,
    device_event_error_response,
    is_supported_button_action,
)
from ..application.local_automation import LocalAutomationUseCase
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


def _missing_event_field_target(
    device_id: Any,
    event_type: Any,
    action: Any,
    timestamp: Any,
) -> str:
    """Return the first missing or invalid required event field target."""
    if not device_id:
        return "event.device_id"
    if event_type != "button_action":
        return "event.type"
    if not action:
        return "event.action"
    if not timestamp:
        return "event.timestamp"
    return "event"


def _has_local_automation_rules(integration_data: dict[str, Any]) -> bool:
    """Return whether local automation rules are configured."""
    if "local_automation_rules" in integration_data:
        return bool(integration_data.get("local_automation_rules"))
    config_entry = integration_data.get("config_entry")
    data = getattr(config_entry, "data", {}) if config_entry else {}
    return bool(data.get("local_automation_rules"))


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
            error = auth_result.error or "auth_failed"
            log_deny(
                _LOGGER,
                client_id=self.request.headers.get("X-Client-Id", "unknown"),
                entity_id="",
                service="device_event",
                reason=error,
            )
            result = device_event_error_response(
                command=DeviceEventCommand(
                    device_id=self.request.match_info.get("device_id", ""),
                    type="",
                    action="",
                    timestamp="",
                    meta={},
                ),
                error=error,
                message="Device event request authentication failed",
                target="request.auth",
                status=401,
            )
            return web.json_response(result.body, status=result.status, headers=result.headers)

        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id="",
                service="device_event",
                reason="rate_limited",
            )
            result = device_event_error_response(
                command=DeviceEventCommand(
                    device_id=self.request.match_info.get("device_id", ""),
                    type="",
                    action="",
                    timestamp="",
                    meta={},
                ),
                error="rate_limited",
                message="Device event request was rate limited",
                target="request.rate_limit",
                status=429,
            )
            return web.json_response(
                result.body,
                status=result.status,
                headers={
                    "Retry-After": str(RATE_WINDOW),
                    "X-RateLimit-Remaining": "0",
                    **result.headers,
                },
            )

        try:
            body = await self.request.json()
        except json.JSONDecodeError:
            result = device_event_error_response(
                command=DeviceEventCommand(
                    device_id=self.request.match_info.get("device_id", ""),
                    type="",
                    action="",
                    timestamp="",
                    meta={},
                ),
                error="invalid_json",
                message="Invalid JSON body",
                target="request.body",
            )
            return web.json_response(result.body, status=result.status, headers=result.headers)

        device_id = self.request.match_info.get("device_id")
        event_type = body.get("type")
        action = body.get("action")
        timestamp = body.get("timestamp")
        meta = body.get("meta", {})

        if not device_id or event_type != "button_action" or not action or not timestamp:
            result = device_event_error_response(
                command=DeviceEventCommand(
                    device_id=device_id or "",
                    type=event_type or "",
                    action=action or "",
                    timestamp=timestamp or "",
                    meta=meta if isinstance(meta, dict) else {},
                ),
                error="missing_required_fields",
                message="Missing required event fields",
                target=_missing_event_field_target(device_id, event_type, action, timestamp),
            )
            return web.json_response(result.body, status=result.status, headers=result.headers)

        if not is_supported_button_action(action):
            result = device_event_error_response(
                command=DeviceEventCommand(
                    device_id=device_id,
                    type=event_type,
                    action=action,
                    timestamp=timestamp,
                    meta=meta or {},
                ),
                error="invalid_action",
                message="Unsupported button action",
                target="event.action",
            )
            return web.json_response(result.body, status=result.status, headers=result.headers)

        if not _is_valid_timestamp(timestamp):
            result = device_event_error_response(
                command=DeviceEventCommand(
                    device_id=device_id,
                    type=event_type,
                    action=action,
                    timestamp=timestamp,
                    meta=meta or {},
                ),
                error="invalid_timestamp",
                message="Invalid event timestamp",
                target="event.timestamp",
            )
            return web.json_response(result.body, status=result.status, headers=result.headers)

        if meta is not None and not isinstance(meta, dict):
            result = device_event_error_response(
                command=DeviceEventCommand(
                    device_id=device_id,
                    type=event_type,
                    action=action,
                    timestamp=timestamp,
                    meta={},
                ),
                error="invalid_meta",
                message="Invalid event metadata",
                target="event.meta",
            )
            return web.json_response(result.body, status=result.status, headers=result.headers)

        deduplicator = self.hass.data[DOMAIN].setdefault(
            "device_event_deduplicator",
            InMemoryDeviceEventDeduplicator(),
        )
        automation = None
        if _has_local_automation_rules(self.hass.data[DOMAIN]):
            automation = LocalAutomationUseCase(
                HomeAssistantLocalAutomationRuleStore(self.hass),
                HomeAssistantSmartlyCommandExecutor(self.hass, _LOGGER),
            )
        result = await DeviceEventUseCase(
            HomeAssistantDeviceEventPublisher(self.hass),
            deduplicator=deduplicator,
            automation=automation,
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
