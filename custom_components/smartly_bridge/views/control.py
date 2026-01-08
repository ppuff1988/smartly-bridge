"""Control API view for Smartly Bridge."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from ..acl import get_entity_domain, is_entity_allowed, is_service_allowed
from ..audit import log_control, log_deny
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
from ..utils import format_numeric_attributes

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


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
            return web.json_response(
                {"error": "integration_not_configured"},
                status=500,
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
            log_deny(
                _LOGGER,
                client_id=self.request.headers.get("X-Client-Id", "unknown"),
                entity_id="",
                service="",
                reason=auth_result.error or "auth_failed",
            )
            return web.json_response(
                {"error": auth_result.error},
                status=401,
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
            return web.json_response(
                {"error": "rate_limited"},
                status=429,
                headers={
                    "Retry-After": str(RATE_WINDOW),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Parse request body
        try:
            body = await self.request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"error": "invalid_json"},
                status=400,
            )

        entity_id = body.get("entity_id")
        action = body.get("action")
        service_data = body.get("service_data", {})
        actor = body.get("actor", {})

        if not entity_id or not action:
            return web.json_response(
                {"error": "missing_required_fields"},
                status=400,
            )

        # Get entity registry
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self.hass)

        # Check entity is allowed
        if not is_entity_allowed(self.hass, entity_id, entity_registry):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service=action,
                reason="entity_not_allowed",
                actor=actor,
            )
            return web.json_response(
                {"error": "entity_not_allowed"},
                status=403,
            )

        # Check service is allowed
        domain = get_entity_domain(entity_id)
        if not is_service_allowed(domain, action):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service=action,
                reason="service_not_allowed",
                actor=actor,
            )
            return web.json_response(
                {"error": "service_not_allowed"},
                status=403,
            )

        # Call the service
        try:
            # Prepare service data
            service_call_data = {"entity_id": entity_id, **service_data}

            await self.hass.services.async_call(
                domain,
                action,
                service_call_data,
                blocking=True,
            )

            # Wait a short moment for state to propagate
            await asyncio.sleep(0.1)

            log_control(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service=action,
                result="success",
                actor=actor,
            )

            # Get new state after service call
            new_state = self.hass.states.get(entity_id)

            return web.json_response(
                {
                    "success": True,
                    "entity_id": entity_id,
                    "action": action,
                    "new_state": new_state.state if new_state else None,
                    "new_attributes": (
                        format_numeric_attributes(dict(new_state.attributes)) if new_state else None
                    ),
                },
                status=200,
            )

        except Exception as err:
            _LOGGER.error("Service call failed: %s", err)
            log_control(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service=action,
                result=f"error: {type(err).__name__}",
                actor=actor,
            )
            return web.json_response(
                {"error": "service_call_failed"},
                status=500,
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
