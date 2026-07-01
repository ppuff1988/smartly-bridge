"""Local automation rule management views."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from ..adapters.home_assistant import _home_assistant_local_automation_rule_store
from ..application.local_automation import (
    LocalAutomationRuleCreateUseCase,
    LocalAutomationRuleDeleteUseCase,
    LocalAutomationRuleUpdateUseCase,
    LocalAutomationRulesListUseCase,
    local_automation_rule_error_response,
)
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
    """Return a local automation JSON response with optional request context."""
    return web.json_response(
        _with_request_context(result_body, request),
        status=status,
        headers=headers,
    )


def _local_automation_rules_list_use_case(
    rule_store: Any,
) -> LocalAutomationRulesListUseCase:
    """Build the local automation rules list application use case."""
    return LocalAutomationRulesListUseCase(rule_store)


def _list_local_automation_rules(
    rule_store: Any,
    *,
    use_case_factory: Callable[[Any], Any] = _local_automation_rules_list_use_case,
) -> Any:
    """Execute the local automation rules list use case with a rule store port."""
    return use_case_factory(rule_store).execute()


def _local_automation_rule_create_use_case(
    rule_store: Any,
) -> LocalAutomationRuleCreateUseCase:
    """Build the local automation rule create application use case."""
    return LocalAutomationRuleCreateUseCase(rule_store)


def _create_local_automation_rule(
    rule_store: Any,
    payload: dict[str, Any],
    *,
    use_case_factory: Callable[[Any], Any] = _local_automation_rule_create_use_case,
) -> Any:
    """Execute the local automation rule create use case with a rule store port."""
    return use_case_factory(rule_store).execute(payload)


def _local_automation_rule_update_use_case(
    rule_store: Any,
) -> LocalAutomationRuleUpdateUseCase:
    """Build the local automation rule update application use case."""
    return LocalAutomationRuleUpdateUseCase(rule_store)


def _update_local_automation_rule(
    rule_store: Any,
    rule_id: str,
    payload: dict[str, Any],
    *,
    use_case_factory: Callable[[Any], Any] = _local_automation_rule_update_use_case,
) -> Any:
    """Execute the local automation rule update use case with a rule store port."""
    return use_case_factory(rule_store).execute(rule_id, payload)


def _local_automation_rule_delete_use_case(
    rule_store: Any,
) -> LocalAutomationRuleDeleteUseCase:
    """Build the local automation rule delete application use case."""
    return LocalAutomationRuleDeleteUseCase(rule_store)


def _delete_local_automation_rule(
    rule_store: Any,
    rule_id: str,
    *,
    use_case_factory: Callable[[Any], Any] = _local_automation_rule_delete_use_case,
) -> Any:
    """Execute the local automation rule delete use case with a rule store port."""
    return use_case_factory(rule_store).execute(rule_id)


def _local_automation_rule_store(hass: Any) -> Any:
    """Return the setup-created local automation rule store or create a fallback."""
    integration_data = hass.data.setdefault(DOMAIN, {})
    runtime_adapters = integration_data.setdefault("runtime_adapters", {})
    rule_store = runtime_adapters.get("local_automation_rule_store")
    if rule_store is None:
        rule_store = _home_assistant_local_automation_rule_store(hass)
        runtime_adapters["local_automation_rule_store"] = rule_store
    return rule_store


class SmartlyLocalAutomationRulesView(BaseView):
    """Handle GET /api/smartly/automations/local/rules requests."""

    def _rule_store(self) -> Any:
        """Return the setup-created local automation rule store."""
        return _local_automation_rule_store(self.hass)

    async def _authorize(self, service: str) -> web.Response | str:
        """Authorize a local automation rule management request."""
        data = self._get_integration_data()
        if data is None:
            result = local_automation_rule_error_response(
                "integration_not_configured",
                message="Smartly Bridge integration is not configured",
                status=500,
                target="integration",
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
            error = auth_result.error or "auth_failed"
            log_deny(
                _LOGGER,
                client_id=self.request.headers.get("X-Client-Id", "unknown"),
                entity_id="",
                service=service,
                reason=error,
            )
            result = local_automation_rule_error_response(
                error,
                message="Local automation rule request authentication failed",
                status=401,
                target="request.auth",
            )
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )

        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id="",
                service=service,
                reason="rate_limited",
            )
            result = local_automation_rule_error_response(
                "rate_limited",
                message="Local automation rule request was rate limited",
                status=429,
                target="request.rate_limit",
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
        """Return configured local automation rules."""
        auth = await self._authorize("local_automation_rules")
        if isinstance(auth, web.Response):
            return auth
        result = _list_local_automation_rules(self._rule_store())
        return _json_response(
            result.body,
            self.request,
            status=result.status,
            headers=result.headers,
        )

    async def post(self) -> web.Response:
        """Create a local automation rule."""
        auth = await self._authorize("local_automation_rules_create")
        if isinstance(auth, web.Response):
            return auth
        payload = await self._json_payload()
        if isinstance(payload, web.Response):
            return payload
        result = _create_local_automation_rule(self._rule_store(), payload)
        return _json_response(
            result.body,
            self.request,
            status=result.status,
            headers=result.headers,
        )

    async def put(self) -> web.Response:
        """Update a local automation rule."""
        auth = await self._authorize("local_automation_rules_update")
        if isinstance(auth, web.Response):
            return auth
        payload = await self._json_payload()
        if isinstance(payload, web.Response):
            return payload
        rule_id = payload.get("rule_id") if isinstance(payload, dict) else None
        result = _update_local_automation_rule(
            self._rule_store(),
            rule_id if isinstance(rule_id, str) else "",
            payload,
        )
        return _json_response(
            result.body,
            self.request,
            status=result.status,
            headers=result.headers,
        )

    async def delete(self) -> web.Response:
        """Delete a local automation rule."""
        auth = await self._authorize("local_automation_rules_delete")
        if isinstance(auth, web.Response):
            return auth
        payload = await self._json_payload()
        if isinstance(payload, web.Response):
            return payload
        rule_id = payload.get("rule_id") if isinstance(payload, dict) else None
        result = _delete_local_automation_rule(
            self._rule_store(),
            rule_id if isinstance(rule_id, str) else "",
        )
        return _json_response(
            result.body,
            self.request,
            status=result.status,
            headers=result.headers,
        )

    async def _json_payload(self) -> dict[str, Any] | web.Response:
        """Return request JSON payload or an API vNext invalid JSON response."""
        try:
            payload = await self.request.json()
        except (json.JSONDecodeError, ValueError):
            result = local_automation_rule_error_response(
                "invalid_json",
                message="Request body must be valid JSON",
                status=400,
                target="request.body",
            )
            return _json_response(
                result.body,
                self.request,
                status=result.status,
                headers=result.headers,
            )
        return payload if isinstance(payload, dict) else {}


class SmartlyLocalAutomationRulesViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyLocalAutomationRulesView to work with HA registration."""

    url = API_PATH_LOCAL_AUTOMATION_RULES
    name = "api:smartly:local_automation_rules"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request."""
        view = SmartlyLocalAutomationRulesView(request)
        return await view.get()

    async def post(self, request: web.Request) -> web.Response:
        """Handle POST request."""
        view = SmartlyLocalAutomationRulesView(request)
        return await view.post()

    async def put(self, request: web.Request) -> web.Response:
        """Handle PUT request."""
        view = SmartlyLocalAutomationRulesView(request)
        return await view.put()

    async def delete(self, request: web.Request) -> web.Response:
        """Handle DELETE request."""
        view = SmartlyLocalAutomationRulesView(request)
        return await view.delete()
