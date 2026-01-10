"""Sync views for Smartly Bridge integration."""

import logging
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from ..acl import get_allowed_entities, get_structure
from ..audit import log_deny
from ..auth import RateLimiter, verify_request
from ..const import (
    API_PATH_SYNC,
    API_PATH_SYNC_STATES,
    CONF_ALLOWED_CIDRS,
    CONF_CLIENT_SECRET,
    CONF_TRUST_PROXY,
    DEFAULT_TRUST_PROXY,
    DOMAIN,
    RATE_WINDOW,
)
from ..utils import format_numeric_attributes

_LOGGER = logging.getLogger(__name__)


class SmartlySyncView(web.View):
    """Handle GET /api/smartly/sync/structure requests."""

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

    async def get(self) -> web.Response:
        """Handle sync request from Platform."""
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
                service="sync",
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
                service="sync",
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

        # Get registries
        from homeassistant.helpers import area_registry as ar
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er
        from homeassistant.helpers import floor_registry as fr

        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)
        area_registry = ar.async_get(self.hass)
        floor_registry = fr.async_get(self.hass)

        # Get allowed entities
        allowed_entities = get_allowed_entities(self.hass, entity_registry)

        # Build structure
        structure = get_structure(
            self.hass,
            allowed_entities,
            entity_registry,
            device_registry,
            area_registry,
            floor_registry,
        )

        return web.json_response(structure, status=200)


class SmartlySyncStatesView(web.View):
    """Handle GET /api/smartly/sync/states requests."""

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

    async def get(self) -> web.Response:
        """Handle sync states request from Platform."""
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
                service="sync_states",
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
                service="sync_states",
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

        # Get entity registry
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self.hass)
        allowed_entities = get_allowed_entities(self.hass, entity_registry)

        # Build states list
        states = []
        for entity_id in allowed_entities:
            state = self.hass.states.get(entity_id)
            if state:
                # Get entity registry entry for icon info
                entry = entity_registry.async_get(entity_id)

                states.append(
                    {
                        "entity_id": entity_id,
                        "state": state.state,
                        "attributes": format_numeric_attributes(dict(state.attributes)),
                        "last_changed": (
                            state.last_changed.isoformat() if state.last_changed else None
                        ),
                        "last_updated": (
                            state.last_updated.isoformat() if state.last_updated else None
                        ),
                        "icon": (entry.icon or entry.original_icon) if entry else None,
                    }
                )

        return web.json_response(
            {"states": states, "count": len(states)},
            status=200,
        )


# Wrapper classes for Home Assistant view registration


class SmartlySyncViewWrapper(HomeAssistantView):
    """Wrapper for SmartlySyncView to work with HA's view registration."""

    url = API_PATH_SYNC
    name = "api:smartly:sync"
    requires_auth = False  # We handle auth ourselves via HMAC

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request."""
        view = SmartlySyncView(request)
        return await view.get()


class SmartlySyncStatesViewWrapper(HomeAssistantView):
    """Wrapper for SmartlySyncStatesView to work with HA's view registration."""

    url = API_PATH_SYNC_STATES
    name = "api:smartly:sync:states"
    requires_auth = False  # We handle auth ourselves via HMAC

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request."""
        view = SmartlySyncStatesView(request)
        return await view.get()
