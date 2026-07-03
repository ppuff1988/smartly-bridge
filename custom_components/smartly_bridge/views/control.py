"""Control API view for Smartly Bridge."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from ..application.control import (
    SmartlyCommand,
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


def _with_request_context(body: dict[str, Any], request: web.Request) -> dict[str, Any]:
    """Attach optional vNext request correlation fields from HTTP headers."""
    enriched = dict(body)
    request_id = request.headers.get("X-Request-Id")
    correlation_id = request.headers.get("X-Correlation-Id")
    if request_id:
        enriched["request_id"] = request_id
    if correlation_id:
        enriched["correlation_id"] = correlation_id
    return enriched


def _json_response(
    result_body: dict[str, Any],
    request: web.Request,
    *,
    status: int,
    headers: dict[str, str] | None = None,
) -> web.Response:
    """Return a control JSON response with optional request context."""
    return web.json_response(
        _with_request_context(result_body, request),
        status=status,
        headers=headers,
    )


async def _execute_smartly_command(executor: Any, client_id: str, command: SmartlyCommand) -> Any:
    """Execute the canonical SmartlyCommand with the selected runtime port."""
    return await executor.execute(client_id, command)


def _smartly_command_executor(
    hass: Any,
) -> Any | None:
    """Return the setup-created canonical command executor."""
    integration_data = hass.data.setdefault(DOMAIN, {})
    runtime_adapters = integration_data.setdefault("runtime_adapters", {})
    return runtime_adapters.get("smartly_command_executor")


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

    def _smartly_command_executor(self) -> Any:
        """Return the setup-created canonical command executor."""
        return _smartly_command_executor(self.hass)

    async def post(self) -> web.Response:
        """Handle control request from Platform."""
        # Get integration data
        data = self._get_integration_data()
        if data is None:
            result = control_error_response("integration_not_configured", status=500)
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

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
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

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
            return _json_response(
                result.body,
                self.request,
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
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        smartly_command = _smartly_command_from_body(body)
        if smartly_command is not None:
            executor = self._smartly_command_executor()
            if executor is None:
                result = control_error_response(
                    "smartly_command_executor_unavailable",
                    status=500,
                )
                return _json_response(
                    result.body,
                    self.request,
                    status=result.status,
                    headers=result.headers,
                )
            result = await _execute_smartly_command(
                executor,
                auth_result.client_id or "unknown",
                smartly_command,
            )
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        result = control_error_response("missing_required_fields", status=400)
        return _json_response(
            result.body,
            self.request,
            status=result.status,
            headers=result.headers,
        )


class SmartlyControlViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyControlView to work with HA's view registration."""

    url = API_PATH_CONTROL
    name = "api:smartly:control"
    requires_auth = False  # We handle auth ourselves via HMAC

    async def post(self, request: web.Request) -> web.Response:
        """Handle POST request."""
        view = SmartlyControlView(request)
        return await view.post()
