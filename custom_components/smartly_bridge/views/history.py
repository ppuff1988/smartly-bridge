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
    DOMAIN_VISUALIZATION_CONFIG,
    HISTORY_DEFAULT_HOURS,
    HISTORY_DEFAULT_LIMIT,
    HISTORY_MAX_DURATION_DAYS,
    HISTORY_MAX_ENTITIES_BATCH,
    RATE_WINDOW,
    VIZUALIZATION_CONFIG,
)
from ..utils import format_numeric_attributes, get_decimal_places

_LOGGER = logging.getLogger(__name__)


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO 8601 datetime string."""
    if not value:
        return None
    try:
        return dt_util.parse_datetime(value)
    except (ValueError, TypeError):
        return None


def _get_entity_metadata(entity_id: str, first_state: dict[str, Any]) -> dict[str, Any]:
    """Generate metadata for entity history visualization.

    Args:
        entity_id: Entity ID
        first_state: First state in history (contains attributes)

    Returns:
        Metadata dict with visualization config, unit, precision, etc.
    """
    domain = entity_id.split(".")[0] if "." in entity_id else "sensor"
    attributes = first_state.get("attributes", {})
    device_class = attributes.get("device_class")
    unit = attributes.get("unit_of_measurement", "")
    state_value = first_state.get("state", "")

    # Determine if state is numeric
    is_numeric = False
    try:
        if state_value not in ("", "unknown", "unavailable", None):
            float(state_value)
            is_numeric = True
    except (ValueError, TypeError):
        pass

    # Get visualization config
    viz_config = {}
    if device_class and device_class in VIZUALIZATION_CONFIG:
        viz_config = VIZUALIZATION_CONFIG[device_class].copy()
    elif domain in DOMAIN_VISUALIZATION_CONFIG:
        viz_config = DOMAIN_VISUALIZATION_CONFIG[domain].copy()
    else:
        # Default config based on data type
        if is_numeric:
            viz_config = {
                "type": "chart",
                "chart_type": "line",
                "color": "#607D8B",
                "show_points": True,
                "interpolation": "linear",
            }
        else:
            viz_config = {
                "type": "timeline",
                "on_color": "#66BB6A",
                "off_color": "#BDBDBD",
            }

    # Get decimal precision
    decimal_places = None
    if is_numeric and device_class:
        decimal_places = get_decimal_places(device_class, unit)

    metadata = {
        "domain": domain,
        "device_class": device_class,
        "unit_of_measurement": unit,
        "friendly_name": attributes.get("friendly_name", entity_id),
        "is_numeric": is_numeric,
        "visualization": viz_config,
    }

    if decimal_places is not None:
        metadata["decimal_places"] = decimal_places

    return metadata


def _format_state_value(state: str, decimal_places: int | None) -> str | float:
    """Format state value with proper precision.

    Args:
        state: State value as string
        decimal_places: Number of decimal places to round to

    Returns:
        Formatted value (float if numeric, string otherwise)
    """
    if state in ("", "unknown", "unavailable", None):
        return state

    try:
        numeric_value = float(state)
        if decimal_places is not None:
            return round(numeric_value, decimal_places)
        return numeric_value
    except (ValueError, TypeError):
        return state


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
    # Handle compressed state format (dict)
    if isinstance(state, dict):
        # Get timestamps, use lu as fallback for lc if not available
        lc_timestamp = state.get("lc", 0)
        lu_timestamp = state.get("lu", 0)

        # If lc is 0 or None, use lu instead
        if not lc_timestamp:
            lc_timestamp = lu_timestamp

        # Get state value and format it
        state_value = state.get("s", "unknown")
        formatted_state = _format_state_value(state_value, decimal_places)

        result = {
            "state": formatted_state,
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

        # Add attributes if requested and available
        if include_attributes:
            attributes = state.get("a", {})
            formatted_attributes = format_numeric_attributes(attributes) if attributes else {}
            result["attributes"] = formatted_attributes

        return result

    # Handle State object
    state_value = state.state
    formatted_state = _format_state_value(state_value, decimal_places)

    result = {
        "state": formatted_state,
        "last_changed": state.last_changed.isoformat(),
        "last_updated": state.last_updated.isoformat(),
    }

    # Add attributes if requested
    if include_attributes:
        attributes = dict(state.attributes)
        formatted_attributes = format_numeric_attributes(attributes) if attributes else {}
        result["attributes"] = formatted_attributes

    return result


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
    if not history_data:
        # 如果沒有任何歷史數據，回傳空列表
        return []

    result = []
    start_time_iso = start_time.isoformat()
    end_time_iso = end_time.isoformat()

    # 解析第一筆數據的時間
    first_data = history_data[0]
    first_time = first_data.get("last_changed", first_data.get("last_updated", start_time_iso))

    # 如果第一筆數據時間晚於 start_time，在開始處插入一個點
    if first_time > start_time_iso:
        # 對於數值型數據，插入第一個已知值或 0
        if is_numeric:
            first_state = first_data.get("state")
            # 如果第一個狀態是數值，使用它；否則使用 0
            try:
                if isinstance(first_state, (int, float)):
                    fill_value = first_state
                elif first_state not in ("unknown", "unavailable", None):
                    fill_value = float(first_state)
                else:
                    fill_value = 0
            except (ValueError, TypeError):
                fill_value = 0

            result.append(
                {
                    "state": fill_value,
                    "last_changed": start_time_iso,
                    "last_updated": start_time_iso,
                }
            )

    # 添加所有原始數據
    result.extend(history_data)

    # 解析最後一筆數據的時間
    last_data = history_data[-1]
    last_time = last_data.get("last_changed", last_data.get("last_updated", end_time_iso))

    # 如果最後一筆數據時間早於 end_time，在結束處插入一個點
    if last_time < end_time_iso:
        # 使用最後一個已知狀態值
        last_state = last_data.get("state")
        result.append(
            {
                "state": last_state,
                "last_changed": end_time_iso,
                "last_updated": end_time_iso,
            }
        )

    return result


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
        # 對於 24 小時內的查詢，不限制筆數；超過 24 小時則使用預設限制
        duration_hours = (end_time - start_time).total_seconds() / 3600
        if duration_hours <= 24:
            # 24 小時內不限制筆數，使用一個很大的值
            limit = 999999
        else:
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

        # Generate metadata from first state with attributes
        metadata = None
        if entity_states:
            # Find first state with attributes
            for state in entity_states:
                if isinstance(state, dict) and state.get("a"):
                    metadata = _get_entity_metadata(entity_id, _format_state(state))
                    break
                elif not isinstance(state, dict):
                    # State object
                    if hasattr(state, "attributes") and state.attributes:
                        metadata = _get_entity_metadata(
                            entity_id, _format_state(state, include_attributes=True)
                        )
                        break

            # If no attributes found, use first state anyway
            if not metadata:
                metadata = _get_entity_metadata(entity_id, _format_state(entity_states[0]))

        # Get decimal places for state formatting
        decimal_places = metadata.get("decimal_places") if metadata else None
        is_numeric = metadata.get("is_numeric", False) if metadata else False

        # Format history data with proper precision
        # Include full attributes only for first state, omit for subsequent if unchanged
        history_data = []
        for i, s in enumerate(entity_states[:limit]):
            include_attrs = i == 0  # Only include attributes for first state
            history_data.append(_format_state(s, decimal_places, include_attrs))

        # 確保時間範圍完整，填補邊界點
        history_data = _ensure_time_bounds(history_data, start_time, end_time, is_numeric)

        response_data = {
            "entity_id": entity_id,
            "history": history_data,
            "count": len(history_data),
            "truncated": truncated,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }

        # Add metadata if available
        if metadata:
            response_data["metadata"] = metadata

        return web.json_response(
            response_data,
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
        metadata_data: dict[str, dict[str, Any]] = {}

        for eid in allowed_entity_ids:
            entity_states = states.get(eid, [])
            truncated_data[eid] = len(entity_states) > limit

            # Generate metadata for entity
            metadata = None
            if entity_states:
                # Find first state with attributes
                for state in entity_states:
                    # Check if it's a State object (not dict)
                    if not isinstance(state, dict):
                        if hasattr(state, "attributes") and state.attributes:
                            metadata = _get_entity_metadata(
                                eid, _format_state(state, include_attributes=True)
                            )
                            break
                    elif state.get("a"):  # Compressed format with attributes
                        metadata = _get_entity_metadata(eid, _format_state(state))
                        break

                if not metadata:
                    metadata = _get_entity_metadata(eid, _format_state(entity_states[0]))

            # Get decimal places and is_numeric for formatting and boundary filling
            decimal_places = metadata.get("decimal_places") if metadata else None
            is_numeric = metadata.get("is_numeric", False) if metadata else False

            # Format history data
            formatted_states = [
                _format_state(s, decimal_places, include_attributes=(i == 0))
                for i, s in enumerate(entity_states[:limit])
            ]

            # 確保時間範圍完整，填補邊界點
            formatted_states = _ensure_time_bounds(
                formatted_states, start_time, end_time, is_numeric
            )

            history_data[eid] = formatted_states
            count_data[eid] = len(formatted_states)

            # Add metadata if available
            if metadata:
                metadata_data[eid] = metadata

        response = {
            "history": history_data,
            "count": count_data,
            "truncated": truncated_data,
            "denied_entities": denied_entity_ids,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }

        # Add metadata if any entities have it
        if metadata_data:
            response["metadata"] = metadata_data

        return web.json_response(response, status=200)


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
