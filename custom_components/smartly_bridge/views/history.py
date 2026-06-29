"""History views for Smartly Bridge integration.

This module provides APIs to query device history data from Home Assistant's
Recorder component, allowing the platform to access historical states and
statistics for entities.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.helpers.http import HomeAssistantView
from homeassistant.util import dt as dt_util

from ..acl import is_entity_allowed
from ..adapters.home_assistant import HomeAssistantHistoryGateway
from ..application.history import (
    BatchHistoryQuery,
    BatchHistoryUseCase,
    HistoryMetadataBuilder,
    HistoryQueryPlanner,
    HistoryResponseFormatter,
    SingleHistoryQuery,
    SingleHistoryUseCase,
    StatisticsQuery,
    StatisticsUseCase,
    _history_error_response,
    decode_cursor,
    encode_cursor,
    parse_datetime,
)
from ..audit import log_deny
from ..auth import AuthResult, RateLimiter, verify_request
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
    HISTORY_MAX_ENTITIES_BATCH,
    MAX_CONCURRENT_HISTORY_QUERIES,
    RATE_WINDOW,
)

_LOGGER = logging.getLogger(__name__)
_HISTORY_FORMATTER = HistoryResponseFormatter()
_HISTORY_METADATA_BUILDER = HistoryMetadataBuilder()

# Semaphore for limiting concurrent database queries
_history_query_semaphore: asyncio.Semaphore | None = None


def _get_history_semaphore() -> asyncio.Semaphore:
    """Get or create the history query semaphore."""
    global _history_query_semaphore
    if _history_query_semaphore is None:
        _history_query_semaphore = asyncio.Semaphore(MAX_CONCURRENT_HISTORY_QUERIES)
    return _history_query_semaphore


def _encode_cursor(timestamp: str, last_changed: str) -> str:
    """Encode cursor for pagination.

    Args:
        timestamp: ISO 8601 timestamp
        last_changed: ISO 8601 last_changed timestamp

    Returns:
        Base64 encoded cursor string
    """
    return encode_cursor(timestamp, last_changed)


def _decode_cursor(cursor: str) -> dict[str, str] | None:
    """Decode cursor for pagination.

    Args:
        cursor: Base64 encoded cursor string

    Returns:
        Dict with timestamp and last_changed, or None if invalid
    """
    return decode_cursor(cursor)


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO 8601 datetime string."""
    return parse_datetime(value)


def _get_entity_metadata(
    entity_id: str,
    first_state: dict[str, Any],
    all_states: list[dict[str, Any]] | None = None,
    hass: HomeAssistant | None = None,
) -> dict[str, Any]:
    """Generate metadata for entity history visualization.

    Args:
        entity_id: Entity ID
        first_state: First state in history (contains attributes)
        all_states: Optional list of all states to search for device_class
        hass: Optional HomeAssistant instance to get current state

    Returns:
        Metadata dict with visualization config, unit, precision, etc.
    """
    current_attributes = None
    if hass is not None:
        current_state = hass.states.get(entity_id)
        if current_state and current_state.attributes:
            current_attributes = dict(current_state.attributes)

    return _HISTORY_METADATA_BUILDER.build(
        entity_id,
        first_state,
        all_states=all_states,
        current_attributes=current_attributes,
    )


def _format_state_value(state: str, decimal_places: int | None) -> str | float:
    """Format state value with proper precision.

    Args:
        state: State value as string
        decimal_places: Number of decimal places to round to

    Returns:
        Formatted value (float if numeric, string otherwise)
    """
    return _HISTORY_FORMATTER.format_state_value(state, decimal_places)


def _format_state(
    state, decimal_places: int | None = None, include_attributes: bool = True
) -> dict[str, Any]:
    """Format a State object or compressed state dict to a dictionary.

    Args:
        state: State object or compressed state dict
        decimal_places: Number of decimal places for numeric state values
        include_attributes: Whether to include attributes in output

    Returns:
        Formatted state dict
    """
    return _HISTORY_FORMATTER.format_state(state, decimal_places, include_attributes)


def _ensure_time_bounds(
    history_data: list[dict[str, Any]],
    start_time: datetime,
    end_time: datetime,
    is_numeric: bool,
) -> list[dict[str, Any]]:
    """確保歷史數據涵蓋完整時間範圍，填補缺失的邊界點。

    Args:
        history_data: 已格式化的歷史數據列表
        start_time: 查詢開始時間
        end_time: 查詢結束時間
        is_numeric: 是否為數值型數據

    Returns:
        填補後的歷史數據列表
    """
    return _HISTORY_FORMATTER.ensure_time_bounds(
        history_data,
        start_time,
        end_time,
        is_numeric,
    )


class SmartlyHistoryView(web.View):
    """Handle GET /api/smartly/history/{entity_id} requests.

    Query historical states for a single entity.
    """

    def __init__(self, request: web.Request) -> None:
        """Initialize the view."""
        super().__init__(request)
        self.hass: HomeAssistant = request.app["hass"]
        self._history_planner = HistoryQueryPlanner()

    def _get_integration_data(self) -> dict[str, Any] | None:
        """Get integration config entry data."""
        if DOMAIN not in self.hass.data:
            return None

        config_entry = self.hass.data[DOMAIN].get("config_entry")
        if config_entry:
            return config_entry.data

        return None

    def _parse_pagination_params(
        self, query, start_time: datetime, end_time: datetime
    ) -> tuple[str | None, dict[str, str] | None, int, int, bool]:
        """Parse pagination related parameters.

        Returns:
            tuple: (cursor_str, cursor_data, page_size, limit, use_pagination)
        """
        pagination = self._history_planner.parse_pagination_params(query, start_time, end_time)
        if pagination.cursor_str and not pagination.cursor_data:
            _LOGGER.error("Invalid cursor format")

        return (
            pagination.cursor_str,
            pagination.cursor_data,
            pagination.page_size,
            pagination.limit,
            pagination.use_pagination,
        )

    def _apply_pagination_filter(
        self,
        entity_states: list,
        cursor_data: dict[str, str] | None,
        page_size: int,
        use_pagination: bool,
    ) -> tuple[list, bool]:
        """Apply pagination filtering to entity states.

        Args:
            entity_states: List of entity states (reversed, newest first)
            cursor_data: Cursor data if continuing pagination
            page_size: Number of items per page
            use_pagination: Whether pagination is enabled

        Returns:
            tuple: (filtered_states, has_more)
        """
        return self._history_planner.apply_pagination_filter(
            entity_states,
            cursor_data,
            page_size,
            use_pagination,
            _format_state,
        )

    async def _verify_auth_and_rate_limit(
        self, data: dict[str, Any]
    ) -> tuple[AuthResult, web.Response | None]:
        """Verify authentication and rate limit.

        Returns:
            Tuple of (auth_result, error_response). If error_response is not None, return it.
            If error_response is None, auth_result will be valid.
        """
        client_secret = data.get(CONF_CLIENT_SECRET)
        if not client_secret:
            # This should never happen as we check in get(), but handle defensively
            dummy_auth = AuthResult(success=False, error="client_secret_not_configured")
            return dummy_auth, web.json_response(
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
            return auth_result, web.json_response(
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
            return auth_result, web.json_response(
                {"error": "rate_limited"},
                status=429,
                headers={
                    "Retry-After": str(RATE_WINDOW),
                    "X-RateLimit-Remaining": "0",
                },
            )

        return auth_result, None

    def _validate_time_range(self, start_time: datetime, end_time: datetime) -> web.Response | None:
        """Validate time range parameters.

        Returns:
            Error response if validation fails, None otherwise.
        """
        result = self._history_planner.validate_time_range(start_time, end_time)
        if result is not None:
            return web.json_response(result.body, status=result.status, headers=result.headers)

        return None

    def _adjust_query_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        cursor_data: dict[str, str] | None,
        entity_id: str,
    ) -> tuple[datetime, datetime]:
        """Adjust query time range for cursor pagination.

        Note: We don't actually adjust the query time range here anymore,
        because the filtering is done in _apply_pagination_filter instead.
        This is more reliable than trying to adjust the database query,
        which may have inclusive/exclusive boundary issues.

        Returns:
            Tuple of (query_start_time, query_end_time) - unchanged.
        """
        # No adjustment needed - filtering happens in _apply_pagination_filter
        return start_time, end_time

    async def get(self) -> web.Response:
        """Handle history query request."""
        # Get integration data
        data = self._get_integration_data()
        if data is None:
            return web.json_response(
                {"error": "integration_not_configured"},
                status=500,
            )

        if not data.get(CONF_CLIENT_SECRET):
            return web.json_response(
                {"error": "client_secret_not_configured"},
                status=500,
            )

        # Verify authentication and rate limit
        auth_result, error_response = await self._verify_auth_and_rate_limit(data)
        if error_response:
            return error_response

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

        end_time = _parse_datetime(query.get("end_time")) or now
        start_time = _parse_datetime(query.get("start_time")) or (
            end_time - timedelta(hours=HISTORY_DEFAULT_HOURS)
        )

        # Validate time range
        if error_response := self._validate_time_range(start_time, end_time):
            return error_response

        # Parse pagination parameters
        cursor_str, cursor_data, page_size, limit, use_pagination = self._parse_pagination_params(
            query, start_time, end_time
        )

        if cursor_str and not cursor_data:
            return web.json_response(
                {"error": "invalid_cursor"},
                status=400,
            )

        # Get query parameters
        significant_changes_only = query.get("significant_changes_only", "true").lower() == "true"

        # Adjust time range for cursor pagination
        query_start_time, query_end_time = self._adjust_query_time_range(
            start_time, end_time, cursor_data, entity_id
        )

        try:
            result = await SingleHistoryUseCase(
                HomeAssistantHistoryGateway(self.hass, _get_history_semaphore)
            ).execute(
                SingleHistoryQuery(
                    entity_id=entity_id,
                    start_time=query_start_time,
                    end_time=query_end_time,
                    significant_changes_only=significant_changes_only,
                    limit=limit,
                    page_size=page_size,
                    use_pagination=use_pagination,
                    cursor_data=cursor_data,
                )
            )
        except asyncio.TimeoutError:
            _LOGGER.error("History query timeout for %s", entity_id)
            result = _history_error_response("query_timeout", status=504)
            return web.json_response(result.body, status=result.status, headers=result.headers)
        except Exception as err:
            _LOGGER.error(
                "Failed to query history for %s (range: %s to %s): %s",
                entity_id,
                query_start_time.isoformat(),
                query_end_time.isoformat(),
                err,
                exc_info=True,
            )
            result = _history_error_response(
                "history_query_failed",
                status=500,
                legacy_fields={"message": str(err)},
            )
            return web.json_response(result.body, status=result.status, headers=result.headers)

        return web.json_response(result.body, status=result.status, headers=result.headers)


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
        self._history_planner = HistoryQueryPlanner()

    def _get_integration_data(self) -> dict[str, Any] | None:
        """Get integration config entry data."""
        if DOMAIN not in self.hass.data:
            return None

        config_entry = self.hass.data[DOMAIN].get("config_entry")
        if config_entry:
            return config_entry.data

        return None

    def _filter_allowed_entities(
        self,
        entity_ids: list[str],
        entity_registry,
        client_id: str,
    ) -> tuple[list[str], list[str]]:
        """Filter entity IDs by access permissions.

        Returns:
            Tuple of (allowed_entity_ids, denied_entity_ids)
        """
        allowed_entity_ids = []
        denied_entity_ids = []

        for eid in entity_ids:
            if is_entity_allowed(self.hass, eid, entity_registry):
                allowed_entity_ids.append(eid)
            else:
                denied_entity_ids.append(eid)
                log_deny(
                    _LOGGER,
                    client_id=client_id,
                    entity_id=eid,
                    service="history_batch",
                    reason="entity_not_allowed",
                )

        return allowed_entity_ids, denied_entity_ids

    def _parse_time_range(self, body: dict[str, Any]) -> tuple[datetime, datetime] | web.Response:
        """Parse and validate time range from request body.

        Returns:
            Tuple of (start_time, end_time) or error response
        """
        now = dt_util.utcnow()

        end_time = _parse_datetime(body.get("end_time"))
        if end_time is None:
            end_time = now

        start_time = _parse_datetime(body.get("start_time"))
        if start_time is None:
            start_time = end_time - timedelta(hours=HISTORY_DEFAULT_HOURS)

        result = self._history_planner.validate_time_range(start_time, end_time)
        if result is not None:
            return web.json_response(result.body, status=result.status, headers=result.headers)

        return start_time, end_time

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
        allowed_entity_ids, denied_entity_ids = self._filter_allowed_entities(
            entity_ids, entity_registry, auth_result.client_id or "unknown"
        )

        if not allowed_entity_ids:
            return web.json_response(
                {"error": "no_allowed_entities"},
                status=403,
            )

        # Parse time parameters
        time_result = self._parse_time_range(body)
        if isinstance(time_result, web.Response):
            return time_result
        start_time, end_time = time_result

        # Parse limit parameter
        # 對於 24 小時內的查詢，不限制筆數；超過 24 小時則使用預設限制
        duration_hours = (end_time - start_time).total_seconds() / 3600
        if duration_hours <= 24:
            # 24 小時內不限制筆數，使用一個很大的值
            limit = 999999
        else:
            try:
                limit = int(body.get("limit", HISTORY_DEFAULT_LIMIT))
                limit = min(limit, HISTORY_DEFAULT_LIMIT)
            except (ValueError, TypeError):
                limit = HISTORY_DEFAULT_LIMIT

        try:
            result = await BatchHistoryUseCase(
                HomeAssistantHistoryGateway(self.hass, _get_history_semaphore)
            ).execute(
                BatchHistoryQuery(
                    entity_ids=allowed_entity_ids,
                    denied_entity_ids=denied_entity_ids,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit,
                    significant_changes_only=True,
                )
            )
        except asyncio.TimeoutError:
            _LOGGER.error("Batch history query timeout for %d entities", len(allowed_entity_ids))
            result = _history_error_response("query_timeout", status=504, target="history.batch")
            return web.json_response(result.body, status=result.status, headers=result.headers)
        except Exception as err:
            _LOGGER.error("Failed to query batch history: %s", err)
            result = _history_error_response(
                "history_query_failed",
                status=500,
                target="history.batch",
            )
            return web.json_response(result.body, status=result.status, headers=result.headers)

        return web.json_response(result.body, status=result.status, headers=result.headers)


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
        self._history_planner = HistoryQueryPlanner()

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
            result = _history_error_response(
                "integration_not_configured",
                status=500,
                target="statistics.integration",
            )
            return web.json_response(result.body, status=result.status, headers=result.headers)

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

        result = self._history_planner.validate_time_range(start_time, end_time)
        if result is not None:
            return web.json_response(result.body, status=result.status, headers=result.headers)

        # Parse period parameter (hour, day, week, month)
        period = query.get("period", "hour")
        if period not in ("hour", "day", "week", "month"):
            result = _history_error_response(
                "invalid_period",
                status=400,
                target="statistics.period",
                legacy_fields={"valid_periods": ["hour", "day", "week", "month"]},
            )
            return web.json_response(result.body, status=result.status, headers=result.headers)

        try:
            result = await StatisticsUseCase(
                HomeAssistantHistoryGateway(self.hass, _get_history_semaphore)
            ).execute(
                StatisticsQuery(
                    entity_id=entity_id,
                    start_time=start_time,
                    end_time=end_time,
                    period=period,
                )
            )
        except Exception as err:
            _LOGGER.error("Failed to query statistics for %s: %s", entity_id, err)
            result = _history_error_response(
                "statistics_query_failed",
                status=500,
                target="statistics",
            )
            return web.json_response(result.body, status=result.status, headers=result.headers)

        return web.json_response(result.body, status=result.status, headers=result.headers)


class SmartlyStatisticsViewWrapper(HomeAssistantView):
    """HomeAssistant view wrapper for statistics API."""

    url = API_PATH_STATISTICS
    name = "api:smartly:statistics"
    requires_auth = False

    async def get(self, request: web.Request, entity_id: str) -> web.Response:
        """Handle GET request."""
        view = SmartlyStatisticsView(request)
        return await view.get()
