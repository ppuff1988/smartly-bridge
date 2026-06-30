"""Sync views for Smartly Bridge integration."""

import logging
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from ..acl import get_allowed_entities, get_structure
from ..adapters.home_assistant import (
    HomeAssistantRawDiagnosticStore,
    HomeAssistantStateSyncGateway,
    HomeAssistantSyncGateway,
)
from ..application.sync import SyncStatesUseCase, SyncStructureUseCase, sync_error_response
from ..audit import log_deny
from ..auth import RateLimiter, verify_request
from ..const import (
    API_PATH_STATES,
    API_PATH_SYNC,
    API_PATH_SYNC_STATES,
    CONF_ALLOWED_CIDRS,
    CONF_CLIENT_SECRET,
    CONF_TRUST_PROXY,
    CONF_USE_LOGICAL_DEVICES,
    DEFAULT_TRUST_PROXY,
    DOMAIN,
    RATE_WINDOW,
)

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

    def _sync_structure_gateway(self) -> Any:
        """Return the setup-created sync structure gateway."""
        runtime_adapters = self.hass.data[DOMAIN].setdefault("runtime_adapters", {})
        return runtime_adapters.setdefault(
            "sync_structure_gateway",
            HomeAssistantSyncGateway(
                self.hass,
                allowed_entities_fn=get_allowed_entities,
                structure_fn=get_structure,
            ),
        )

    async def get(self) -> web.Response:
        """Handle sync request from Platform."""
        # Get integration data
        data = self._get_integration_data()
        if data is None:
            result = sync_error_response(
                "integration_not_configured",
                status=500,
                target="sync.structure.integration",
            )
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
                service="sync",
                reason=error,
            )
            result = sync_error_response(error, status=401, target="sync.structure.auth")
            return web.json_response(result.body, status=result.status, headers=result.headers)

        # Check rate limit
        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id="",
                service="sync",
                reason="rate_limited",
            )
            result = sync_error_response(
                "rate_limited",
                status=429,
                target="sync.structure.rate_limit",
            )
            return web.json_response(
                result.body,
                status=result.status,
                headers={
                    "Retry-After": str(RATE_WINDOW),
                    "X-RateLimit-Remaining": "0",
                },
            )

        result = SyncStructureUseCase(self._sync_structure_gateway()).execute()
        return web.json_response(result.body, status=result.status, headers=result.headers)


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

    def _sync_states_gateway(self) -> Any:
        """Return the setup-created sync states gateway."""
        runtime_adapters = self.hass.data[DOMAIN].setdefault("runtime_adapters", {})
        return runtime_adapters.setdefault(
            "sync_states_gateway",
            HomeAssistantStateSyncGateway(
                self.hass,
                allowed_entities_fn=get_allowed_entities,
            ),
        )

    def _raw_diagnostic_recorder(self) -> Any:
        """Return the setup-created raw diagnostic recorder."""
        runtime_adapters = self.hass.data[DOMAIN].setdefault("runtime_adapters", {})
        return runtime_adapters.setdefault(
            "raw_diagnostic_store",
            HomeAssistantRawDiagnosticStore(self.hass),
        )

    async def get(self) -> web.Response:
        """Handle sync states request from Platform."""
        # Get integration data
        data = self._get_integration_data()
        if data is None:
            result = sync_error_response(
                "integration_not_configured",
                status=500,
                target="sync.states.integration",
            )
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
                service="sync_states",
                reason=error,
            )
            result = sync_error_response(error, status=401, target="sync.states.auth")
            return web.json_response(result.body, status=result.status, headers=result.headers)

        # Check rate limit
        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id="",
                service="sync_states",
                reason="rate_limited",
            )
            result = sync_error_response(
                "rate_limited",
                status=429,
                target="sync.states.rate_limit",
            )
            return web.json_response(
                result.body,
                status=result.status,
                headers={
                    "Retry-After": str(RATE_WINDOW),
                    "X-RateLimit-Remaining": "0",
                },
            )

        result = await SyncStatesUseCase(
            self._sync_states_gateway(),
            use_logical_devices=bool(data.get(CONF_USE_LOGICAL_DEVICES, False)),
            raw_diagnostic_recorder=self._raw_diagnostic_recorder(),
        ).execute()
        return web.json_response(result.body, status=result.status, headers=result.headers)


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


class SmartlyLegacyStatesViewWrapper(SmartlySyncStatesViewWrapper):
    """Backward-compatible alias for legacy states clients."""

    url = API_PATH_STATES
    name = "api:smartly:states"
