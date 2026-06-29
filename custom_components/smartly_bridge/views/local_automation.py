"""Local automation rule management views."""

from __future__ import annotations

import logging

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from ..adapters.home_assistant import HomeAssistantLocalAutomationRuleStore
from ..application.local_automation import LocalAutomationRulesListUseCase
from ..audit import log_deny
from ..auth import RateLimiter, verify_request
from ..const import (
    API_PATH_LOCAL_AUTOMATION_RULES,
    CONF_ALLOWED_CIDRS,
    CONF_CLIENT_SECRET,
    CONF_TRUST_PROXY,
    DEFAULT_TRUST_PROXY,
    DOMAIN,
    RATE_WINDOW,
)
from .base import BaseView

_LOGGER = logging.getLogger(__name__)


class SmartlyLocalAutomationRulesView(BaseView):
    """Handle GET /api/smartly/automations/local/rules requests."""

    async def get(self) -> web.Response:
        """Return configured local automation rules."""
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
                service="local_automation_rules",
                reason=auth_result.error or "auth_failed",
            )
            return web.json_response(
                {"error": auth_result.error},
                status=401,
            )

        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id="",
                service="local_automation_rules",
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

        result = LocalAutomationRulesListUseCase(
            HomeAssistantLocalAutomationRuleStore(self.hass)
        ).execute()
        return web.json_response(result.body, status=result.status, headers=result.headers)


class SmartlyLocalAutomationRulesViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyLocalAutomationRulesView to work with HA registration."""

    url = API_PATH_LOCAL_AUTOMATION_RULES
    name = "api:smartly:local_automation_rules"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request."""
        view = SmartlyLocalAutomationRulesView(request)
        return await view.get()
