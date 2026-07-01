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
    """Return a raw diagnostic JSON response with optional request context."""
    return web.json_response(
        _with_request_context(result_body, request),
        status=status,
        headers=headers,
    )


def _fetch_raw_diagnostic(store: Any, *, raw_ref: str) -> Any:
    """Execute the raw diagnostic fetch use case with a resolved store port."""
    return RawDiagnosticFetchUseCase(store).execute(raw_ref)


def _raw_diagnostic_store(hass: Any) -> Any:
    """Return the setup-created raw diagnostic store or create a legacy fallback."""
    runtime_adapters = hass.data[DOMAIN].setdefault("runtime_adapters", {})
    store = runtime_adapters.get("raw_diagnostic_store")
    if store is None:
        store = HomeAssistantRawDiagnosticStore(hass)
        runtime_adapters["raw_diagnostic_store"] = store
    return store


class SmartlyRawDiagnosticView(BaseView):
    """Handle GET /api/smartly/diagnostics/raw/{raw_ref} requests."""

    def _raw_diagnostic_store(self) -> Any:
        """Return the setup-created raw diagnostic store."""
        return _raw_diagnostic_store(self.hass)

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
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        if not await rate_limiter.check(auth_result.client_id or ""):
            result = raw_diagnostic_error_response(
                "rate_limited",
                message="Raw diagnostic request was rate limited",
                status=429,
                target="diagnostics.raw.rate_limit",
            )
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
        return auth_result.client_id or "unknown"

    async def get(self) -> web.Response:
        """Return masked raw diagnostic data."""
        auth = await self._authorize()
        if isinstance(auth, web.Response):
            return auth
        raw_ref = self.request.match_info.get("raw_ref", "")
        result = _fetch_raw_diagnostic(
            self._raw_diagnostic_store(),
            raw_ref=raw_ref,
        )
        return _json_response(
            result.body,
            self.request,
            status=result.status,
            headers=result.headers,
        )


class SmartlyRawDiagnosticViewWrapper(HomeAssistantView):
    """Wrapper for raw diagnostic fetch view."""

    url = API_PATH_RAW_DIAGNOSTIC
    name = "api:smartly:diagnostics:raw"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request."""
        view = SmartlyRawDiagnosticView(request)
        return await view.get()
