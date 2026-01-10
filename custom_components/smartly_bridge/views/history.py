"""History views for Smartly Bridge integration.

This module provides APIs to query device history data from Home Assistant's
Recorder component, allowing the platform to access historical states and
statistics for entities.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.helpers.http import HomeAssistantView
from homeassistant.util import dt as dt_util

from ..acl import is_entity_allowed
from ..audit import log_deny
from ..auth import RateLimiter, verify_request
from ..const import (
    API_PATH_HISTORY,
    API_PATH_HISTORY_BATCH,
    API_PATH_STATISTICS,
    CONF_ALLOWED_CIDRS,
    CONF_CLIENT_SECRET,
    CONF_TRUST_PROXY,
    DEFAULT_TRUST_PROXY,
    DOMAIN,
    HISTORY_DEFAULT_HOURS,
    HISTORY_DEFAULT_LIMIT,
    HISTORY_MAX_DURATION_DAYS,
    HISTORY_MAX_ENTITIES_BATCH,
    RATE_WINDOW,
)

_LOGGER = logging.getLogger(__name__)


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO 8601 datetime string."""
    if not value:
        return None
    try:
        return dt_util.parse_datetime(value)
    except (ValueError, TypeError):
        return None


def _format_state(state) -> dict[str, Any]:
    """Format a State object or compressed state dict to a dictionary."""
    # Handle compressed state format (dict)
    if isinstance(state, dict):
        # Get timestamps, use lu as fallback for lc if not available
        lc_timestamp = state.get("lc", 0)
        lu_timestamp = state.get("lu", 0)

        # If lc is 0 or None, use lu instead
        if not lc_timestamp:
            lc_timestamp = lu_timestamp

        return {
            "state": state.get("s", "unknown"),
            "attributes": state.get("a", {}),
            "last_changed": (
                datetime.fromtimestamp(lc_timestamp, tz=dt_util.UTC).isoformat()
                if lc_timestamp
                else dt_util.utcnow().isoformat()
            ),
            "last_updated": (
                datetime.fromtimestamp(lu_timestamp, tz=dt_util.UTC).isoformat()
                if lu_timestamp
                else dt_util.utcnow().isoformat()
            ),
        }

    # Handle State object
    return {
        "state": state.state,
        "attributes": dict(state.attributes),
        "last_changed": state.last_changed.isoformat(),
        "last_updated": state.last_updated.isoformat(),
    }


class SmartlyHistoryView(web.View):
    """Handle GET /api/smartly/history/{entity_id} requests.

    Query historical states for a single entity.
    """

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
        """Handle history query request."""
        # Get integration data
        data = self._get_integration_data()
        if data is None:
            return web.json_response(
                {"error": "integration_not_configured"},
                status=500,
            )

        client_secret = data.get(CONF_CLIENT_SECRET)
        if not client_secret:
            return web.json_response(
                {"error": "client_secret_not_configured"},
                status=500,
            )
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
                service="history",
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
                service="history",
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

        # Get entity_id from path
        entity_id = self.request.match_info.get("entity_id")
        if not entity_id:
            return web.json_response(
                {"error": "entity_id_required"},
                status=400,
            )

        # Check entity access permission
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self.hass)
        if not is_entity_allowed(self.hass, entity_id, entity_registry):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service="history",
                reason="entity_not_allowed",
            )
            return web.json_response(
                {"error": "entity_not_allowed"},
                status=403,
            )

        # Parse query parameters
        query = self.request.query
        now = dt_util.utcnow()

        end_time = _parse_datetime(query.get("end_time"))
        if end_time is None:
            end_time = now

        start_time = _parse_datetime(query.get("start_time"))
        if start_time is None:
            start_time = end_time - timedelta(hours=HISTORY_DEFAULT_HOURS)

        # Validate time range
        max_duration = timedelta(days=HISTORY_MAX_DURATION_DAYS)
        if end_time - start_time > max_duration:
            return web.json_response(
                {
                    "error": "time_range_too_large",
                    "max_days": HISTORY_MAX_DURATION_DAYS,
                },
                status=400,
            )

        if start_time > end_time:
            return web.json_response(
                {"error": "invalid_time_range"},
                status=400,
            )

        # Parse limit parameter
        try:
            limit = int(query.get("limit", HISTORY_DEFAULT_LIMIT))
            limit = min(limit, HISTORY_DEFAULT_LIMIT)
        except ValueError:
            limit = HISTORY_DEFAULT_LIMIT

        # Get significant_changes_only parameter
        significant_changes_only = query.get("significant_changes_only", "true").lower() == "true"

        # Query history from Recorder
        try:
            from homeassistant.components.recorder import history
            from homeassistant.helpers.recorder import get_instance

            recorder_instance = get_instance(self.hass)
            states = await recorder_instance.async_add_executor_job(
                history.get_significant_states,
                self.hass,
                start_time,
                end_time,
                [entity_id],
                None,  # filters
                True,  # include_start_time_state
                significant_changes_only,
                True,  # minimal_response
                False,  # no_attributes
                True,  # compressed_state_format
            )
        except Exception as err:
            _LOGGER.error("Failed to query history for %s: %s", entity_id, err)
            return web.json_response(
                {"error": "history_query_failed"},
                status=500,
            )

        # Format response
        entity_states = states.get(entity_id, [])
        truncated = len(entity_states) > limit
        history_data = [_format_state(s) for s in entity_states[:limit]]

        return web.json_response(
            {
                "entity_id": entity_id,
                "history": history_data,
                "count": len(history_data),
                "truncated": truncated,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
            },
            status=200,
        )


class SmartlyHistoryViewWrapper(HomeAssistantView):
    """HomeAssistant view wrapper for history API."""

    url = API_PATH_HISTORY
    name = "api:smartly:history"
    requires_auth = False

    async def get(self, request: web.Request, entity_id: str) -> web.Response:
        """Handle GET request."""
        view = SmartlyHistoryView(request)
        return await view.get()


class SmartlyHistoryBatchView(web.View):
    """Handle POST /api/smartly/history/batch requests.

    Query historical states for multiple entities at once.
    """

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
        """Handle batch history query request."""
        # Get integration data
        data = self._get_integration_data()
        if data is None:
            return web.json_response(
                {"error": "integration_not_configured"},
                status=500,
            )

        client_secret = data.get(CONF_CLIENT_SECRET)
        if not client_secret:
            return web.json_response(
                {"error": "client_secret_not_configured"},
                status=500,
            )
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
                service="history_batch",
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
                service="history_batch",
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
        except Exception:
            return web.json_response(
                {"error": "invalid_json"},
                status=400,
            )

        entity_ids = body.get("entity_ids", [])
        if not isinstance(entity_ids, list) or not entity_ids:
            return web.json_response(
                {"error": "entity_ids_required"},
                status=400,
            )

        # Limit batch size
        if len(entity_ids) > HISTORY_MAX_ENTITIES_BATCH:
            return web.json_response(
                {
                    "error": "too_many_entities",
                    "max_entities": HISTORY_MAX_ENTITIES_BATCH,
                },
                status=400,
            )

        # Check entity access permissions
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self.hass)
        allowed_entity_ids = []
        denied_entity_ids = []

        for eid in entity_ids:
            if is_entity_allowed(self.hass, eid, entity_registry):
                allowed_entity_ids.append(eid)
            else:
                denied_entity_ids.append(eid)
                log_deny(
                    _LOGGER,
                    client_id=auth_result.client_id or "unknown",
                    entity_id=eid,
                    service="history_batch",
                    reason="entity_not_allowed",
                )

        if not allowed_entity_ids:
            return web.json_response(
                {"error": "no_allowed_entities"},
                status=403,
            )

        # Parse time parameters
        now = dt_util.utcnow()

        end_time = _parse_datetime(body.get("end_time"))
        if end_time is None:
            end_time = now

        start_time = _parse_datetime(body.get("start_time"))
        if start_time is None:
            start_time = end_time - timedelta(hours=HISTORY_DEFAULT_HOURS)

        # Validate time range
        max_duration = timedelta(days=HISTORY_MAX_DURATION_DAYS)
        if end_time - start_time > max_duration:
            return web.json_response(
                {
                    "error": "time_range_too_large",
                    "max_days": HISTORY_MAX_DURATION_DAYS,
                },
                status=400,
            )

        if start_time > end_time:
            return web.json_response(
                {"error": "invalid_time_range"},
                status=400,
            )

        # Parse limit parameter
        try:
            limit = int(body.get("limit", HISTORY_DEFAULT_LIMIT))
            limit = min(limit, HISTORY_DEFAULT_LIMIT)
        except (ValueError, TypeError):
            limit = HISTORY_DEFAULT_LIMIT

        # Query history from Recorder
        try:
            from homeassistant.components.recorder import history
            from homeassistant.helpers.recorder import get_instance

            recorder_instance = get_instance(self.hass)
            states = await recorder_instance.async_add_executor_job(
                history.get_significant_states,
                self.hass,
                start_time,
                end_time,
                allowed_entity_ids,
                None,  # filters
                True,  # include_start_time_state
                True,  # significant_changes_only
            )
        except Exception as err:
            _LOGGER.error("Failed to query batch history: %s", err)
            return web.json_response(
                {"error": "history_query_failed"},
                status=500,
            )

        # Format response
        history_data: dict[str, list[dict[str, Any]]] = {}
        count_data: dict[str, int] = {}
        truncated_data: dict[str, bool] = {}

        for eid in allowed_entity_ids:
            entity_states = states.get(eid, [])
            truncated_data[eid] = len(entity_states) > limit
            history_data[eid] = [_format_state(s) for s in entity_states[:limit]]
            count_data[eid] = len(history_data[eid])

        return web.json_response(
            {
                "history": history_data,
                "count": count_data,
                "truncated": truncated_data,
                "denied_entities": denied_entity_ids,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
            },
            status=200,
        )


class SmartlyHistoryBatchViewWrapper(HomeAssistantView):
    """HomeAssistant view wrapper for batch history API."""

    url = API_PATH_HISTORY_BATCH
    name = "api:smartly:history:batch"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        """Handle POST request."""
        view = SmartlyHistoryBatchView(request)
        return await view.post()


class SmartlyStatisticsView(web.View):
    """Handle GET /api/smartly/statistics/{entity_id} requests.

    Query statistical data (mean, min, max, sum) for a single entity.
    """

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
        """Handle statistics query request."""
        # Get integration data
        data = self._get_integration_data()
        if data is None:
            return web.json_response(
                {"error": "integration_not_configured"},
                status=500,
            )

        client_secret = data.get(CONF_CLIENT_SECRET)
        if not client_secret:
            return web.json_response(
                {"error": "client_secret_not_configured"},
                status=500,
            )
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
                service="statistics",
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
                service="statistics",
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

        # Get entity_id from path
        entity_id = self.request.match_info.get("entity_id")
        if not entity_id:
            return web.json_response(
                {"error": "entity_id_required"},
                status=400,
            )

        # Check entity access permission
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self.hass)
        if not is_entity_allowed(self.hass, entity_id, entity_registry):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service="statistics",
                reason="entity_not_allowed",
            )
            return web.json_response(
                {"error": "entity_not_allowed"},
                status=403,
            )

        # Parse query parameters
        query = self.request.query
        now = dt_util.utcnow()

        end_time = _parse_datetime(query.get("end_time"))
        if end_time is None:
            end_time = now

        start_time = _parse_datetime(query.get("start_time"))
        if start_time is None:
            start_time = end_time - timedelta(hours=HISTORY_DEFAULT_HOURS)

        # Validate time range
        max_duration = timedelta(days=HISTORY_MAX_DURATION_DAYS)
        if end_time - start_time > max_duration:
            return web.json_response(
                {
                    "error": "time_range_too_large",
                    "max_days": HISTORY_MAX_DURATION_DAYS,
                },
                status=400,
            )

        if start_time > end_time:
            return web.json_response(
                {"error": "invalid_time_range"},
                status=400,
            )

        # Parse period parameter (hour, day, week, month)
        period = query.get("period", "hour")
        if period not in ("hour", "day", "week", "month"):
            return web.json_response(
                {"error": "invalid_period", "valid_periods": ["hour", "day", "week", "month"]},
                status=400,
            )

        # Query statistics from Recorder
        try:
            from typing import Literal

            from homeassistant.components.recorder.statistics import statistics_during_period
            from homeassistant.helpers.recorder import get_instance

            # Get statistic_id (usually same as entity_id for sensors)
            statistic_id = entity_id

            # Define types to query - use Literal types for type safety
            stat_types: set[
                Literal["change", "last_reset", "max", "mean", "min", "state", "sum"]
            ] = {"mean", "min", "max", "sum", "state"}

            # statistics_during_period returns dict with start as timestamp (float)
            recorder_instance = get_instance(self.hass)
            stat_result = await recorder_instance.async_add_executor_job(
                statistics_during_period,
                self.hass,
                start_time,
                end_time,
                {statistic_id},
                period,
                None,  # units
                stat_types,
            )
        except Exception as err:
            _LOGGER.error("Failed to query statistics for %s: %s", entity_id, err)
            return web.json_response(
                {"error": "statistics_query_failed"},
                status=500,
            )

        # Format response
        stats = stat_result.get(entity_id, [])
        statistics_data: list[dict[str, Any]] = []

        for stat in stats:
            # start is a float timestamp in statistics_during_period result
            start_ts = stat.get("start")
            end_ts = stat.get("end")
            start_iso = (
                datetime.fromtimestamp(start_ts, tz=dt_util.UTC).isoformat() if start_ts else None
            )
            end_iso = datetime.fromtimestamp(end_ts, tz=dt_util.UTC).isoformat() if end_ts else None
            stat_entry: dict[str, Any] = {
                "start": start_iso,
                "end": end_iso,
            }
            # Add available statistics
            if "mean" in stat and stat["mean"] is not None:
                stat_entry["mean"] = stat["mean"]
            if "min" in stat and stat["min"] is not None:
                stat_entry["min"] = stat["min"]
            if "max" in stat and stat["max"] is not None:
                stat_entry["max"] = stat["max"]
            if "sum" in stat and stat["sum"] is not None:
                stat_entry["sum"] = stat["sum"]
            if "state" in stat and stat["state"] is not None:
                stat_entry["state"] = stat["state"]

            statistics_data.append(stat_entry)

        return web.json_response(
            {
                "entity_id": entity_id,
                "period": period,
                "statistics": statistics_data,
                "count": len(statistics_data),
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
            },
            status=200,
        )


class SmartlyStatisticsViewWrapper(HomeAssistantView):
    """HomeAssistant view wrapper for statistics API."""

    url = API_PATH_STATISTICS
    name = "api:smartly:statistics"
    requires_auth = False

    async def get(self, request: web.Request, entity_id: str) -> web.Response:
        """Handle GET request."""
        view = SmartlyStatisticsView(request)
        return await view.get()
