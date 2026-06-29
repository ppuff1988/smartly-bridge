"""Control API view for Smartly Bridge."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from ..adapters.home_assistant import (
    HomeAssistantCommandTargetResolver,
    HomeAssistantControlGateway,
    HomeAssistantEntityPolicy,
    LoggingAuditAdapter,
)
from ..application.control import (
    ControlCommand,
    ControlUseCase,
    SmartlyCommand,
    SmartlyCommandUseCase,
    control_error_response,
)
from ..audit import log_deny
from ..auth import RateLimiter, verify_request
from ..const import (
    API_PATH_CONTROL,
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


def _slug(value: Any) -> str:
    """Convert Platform identifiers to Home Assistant entity-id segments."""
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).lower())
    return normalized.strip("_")


def _service_data_from_body(body: dict[str, Any]) -> dict[str, Any]:
    """Return service data from the canonical key or frontend data alias."""
    service_data = body.get("service_data")
    if service_data is None:
        service_data = body.get("data", {})
        if isinstance(service_data, dict) and "target" in service_data:
            service_data = {key: value for key, value in service_data.items() if key != "target"}
    return service_data


def _entity_id_from_body(body: dict[str, Any]) -> str | None:
    """Return target entity ID from canonical key or frontend device_id alias."""
    return body.get("entity_id") or body.get("device_id")


def _normalize_control_body(body: dict[str, Any]) -> dict[str, Any]:
    """Normalize supported Platform control payloads to canonical control fields."""
    if "capability" not in body and "command" not in body and "target" not in body:
        return {
            "entity_id": _entity_id_from_body(body),
            "action": body.get("action"),
            "service_data": _service_data_from_body(body),
            "actor": body.get("actor", {}),
        }

    device_id = body.get("device_id") or body.get("device")
    capability = body.get("capability")
    target = body.get("target")
    entity_id = body.get("target_entity_id")

    if entity_id is None and isinstance(target, str) and "." in target:
        entity_id = target
    elif entity_id is None and device_id and capability:
        entity_id_parts = [_slug(device_id)]
        if target:
            entity_id_parts.append(_slug(target))
        entity_id = f"{_slug(capability)}.{'_'.join(entity_id_parts)}"

    return {
        "entity_id": entity_id,
        "action": body.get("command"),
        "service_data": _service_data_from_body(body),
        "actor": body.get("actor", {}),
    }


def _smartly_command_from_body(body: dict[str, Any]) -> SmartlyCommand | None:
    """Return API vNext SmartlyCommand when the body uses canonical command shape."""
    required = ("command_id", "device_id", "capability", "command")
    if not all(body.get(field) for field in required):
        return None

    params = body.get("params", {})
    source = body.get("source")
    return SmartlyCommand(
        command_id=str(body["command_id"]),
        device_id=str(body["device_id"]),
        capability=str(body["capability"]),
        command=str(body["command"]),
        params=params if isinstance(params, dict) else {},
        source=source if isinstance(source, dict) else None,
    )


class SmartlyControlView(web.View):
    """Handle POST /api/smartly/control requests."""

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
        """Handle control request from Platform."""
        # Get integration data
        data = self._get_integration_data()
        if data is None:
            result = control_error_response("integration_not_configured", status=500)
            return web.json_response(result.body, status=result.status, headers=result.headers)

        client_secret = data.get(CONF_CLIENT_SECRET)
        allowed_cidrs = data.get(CONF_ALLOWED_CIDRS, "")
        trust_proxy_mode = data.get(CONF_TRUST_PROXY, DEFAULT_TRUST_PROXY)
        nonce_cache = self.hass.data[DOMAIN]["nonce_cache"]
        rate_limiter: RateLimiter = self.hass.data[DOMAIN]["rate_limiter"]

        # Verify authentication
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
                service="",
                reason=error,
            )
            result = control_error_response(error, status=401)
            return web.json_response(result.body, status=result.status, headers=result.headers)

        # Check rate limit
        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id="",
                service="",
                reason="rate_limited",
            )
            result = control_error_response("rate_limited", status=429)
            return web.json_response(
                result.body,
                status=result.status,
                headers={
                    "Retry-After": str(RATE_WINDOW),
                    "X-RateLimit-Remaining": "0",
                    **result.headers,
                },
            )

        # Parse request body
        try:
            body = await self.request.json()
        except json.JSONDecodeError:
            result = control_error_response("invalid_json", status=400)
            return web.json_response(result.body, status=result.status, headers=result.headers)

        smartly_command = _smartly_command_from_body(body)
        if smartly_command is not None:
            result = await SmartlyCommandUseCase(
                HomeAssistantEntityPolicy(self.hass),
                HomeAssistantControlGateway(self.hass),
                LoggingAuditAdapter(_LOGGER),
                HomeAssistantCommandTargetResolver(self.hass),
            ).execute(auth_result.client_id or "unknown", smartly_command)
            return web.json_response(result.body, status=result.status, headers=result.headers)

        normalized_body = _normalize_control_body(body)
        entity_id = normalized_body["entity_id"]
        action = normalized_body["action"]
        service_data = normalized_body["service_data"]
        actor = normalized_body["actor"]

        if not entity_id or not action:
            return web.json_response(
                {"error": "missing_required_fields"},
                status=400,
            )

        use_case = ControlUseCase(
            HomeAssistantEntityPolicy(self.hass),
            HomeAssistantControlGateway(self.hass),
            LoggingAuditAdapter(_LOGGER),
        )
        result = await use_case.execute(
            auth_result.client_id or "unknown",
            ControlCommand(
                entity_id=entity_id,
                action=action,
                service_data=service_data,
                actor=actor,
            ),
        )
        return web.json_response(result.body, status=result.status, headers=result.headers)


class SmartlyControlViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyControlView to work with HA's view registration."""

    url = API_PATH_CONTROL
    name = "api:smartly:control"
    requires_auth = False  # We handle auth ourselves via HMAC

    async def post(self, request: web.Request) -> web.Response:
        """Handle POST request."""
        view = SmartlyControlView(request)
        return await view.post()
