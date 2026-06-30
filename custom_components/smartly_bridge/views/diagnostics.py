"""Raw diagnostic views."""

from __future__ import annotations

from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from ..adapters.home_assistant import HomeAssistantRawDiagnosticStore
from ..application.diagnostics import RawDiagnosticFetchUseCase, raw_diagnostic_error_response
from ..auth import RateLimiter, verify_request
from ..const import (
    API_PATH_RAW_DIAGNOSTIC,
    CONF_ALLOWED_CIDRS,
    CONF_CLIENT_SECRET,
    CONF_TRUST_PROXY,
    DEFAULT_TRUST_PROXY,
    DOMAIN,
    RATE_WINDOW,
)
from .base import BaseView


class SmartlyRawDiagnosticView(BaseView):
    """Handle GET /api/smartly/diagnostics/raw/{raw_ref} requests."""

    def _raw_diagnostic_store(self) -> Any:
        """Return the setup-created raw diagnostic store."""
        runtime_adapters = self.hass.data[DOMAIN].setdefault("runtime_adapters", {})
        store = runtime_adapters.get("raw_diagnostic_store")
        if store is None:
            store = HomeAssistantRawDiagnosticStore(self.hass)
            runtime_adapters["raw_diagnostic_store"] = store
        return store

    async def _authorize(self) -> web.Response | str:
        """Authorize a raw diagnostic request."""
        data = self._get_integration_data()
        if data is None:
            result = raw_diagnostic_error_response(
                "integration_not_configured",
                message="Smartly Bridge integration is not configured",
                status=500,
                target="diagnostics.raw.integration",
            )
            return web.json_response(result.body, status=result.status, headers=result.headers)

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
            result = raw_diagnostic_error_response(
                auth_result.error or "auth_failed",
                message="Raw diagnostic request authentication failed",
                status=401,
                target="diagnostics.raw.auth",
            )
            return web.json_response(result.body, status=result.status, headers=result.headers)

        if not await rate_limiter.check(auth_result.client_id or ""):
            result = raw_diagnostic_error_response(
                "rate_limited",
                message="Raw diagnostic request was rate limited",
                status=429,
                target="diagnostics.raw.rate_limit",
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
        return auth_result.client_id or "unknown"

    async def get(self) -> web.Response:
        """Return masked raw diagnostic data."""
        auth = await self._authorize()
        if isinstance(auth, web.Response):
            return auth
        raw_ref = self.request.match_info.get("raw_ref", "")
        result = RawDiagnosticFetchUseCase(self._raw_diagnostic_store()).execute(raw_ref)
        return web.json_response(result.body, status=result.status, headers=result.headers)


class SmartlyRawDiagnosticViewWrapper(HomeAssistantView):
    """Wrapper for raw diagnostic fetch view."""

    url = API_PATH_RAW_DIAGNOSTIC
    name = "api:smartly:diagnostics:raw"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request."""
        view = SmartlyRawDiagnosticView(request)
        return await view.get()
