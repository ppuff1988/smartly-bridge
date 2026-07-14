"""History query planning helpers."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from ..const import (
    BRIDGE_CHART_DEVICE_CLASSES,
    DOMAIN_VISUALIZATION_CONFIG,
    HISTORY_DEFAULT_LIMIT,
    HISTORY_MAX_DURATION_DAYS,
    VIZUALIZATION_CONFIG,
)
from ..domain.models import BridgeResponse
from ..utils import format_numeric_attributes, get_decimal_places
from .ports import HistoryGatewayPort

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000
SMARTLY_API_SCHEMA_VERSION = "2026.06"


@dataclass(frozen=True)
class HistoryPagination:
    """Parsed pagination settings for a history query."""

    cursor_str: str | None
    cursor_data: dict[str, str] | None
    page_size: int
    limit: int
    use_pagination: bool


@dataclass(frozen=True)
class SingleHistoryQuery:
    """Single entity history query."""

    entity_id: str
    start_time: datetime
    end_time: datetime
    significant_changes_only: bool
    limit: int
    page_size: int
    use_pagination: bool
    cursor_data: dict[str, str] | None = None
    first_state_with_attrs: Any | None = None


@dataclass(frozen=True)
class BatchHistoryQuery:
    """Batch history query."""

    entity_ids: list[str]
    denied_entity_ids: list[str]
    start_time: datetime
    end_time: datetime
    limit: int
    significant_changes_only: bool


@dataclass(frozen=True)
class StatisticsQuery:
    """Statistics query."""

    entity_id: str
    start_time: datetime
    end_time: datetime
    period: str


def encode_cursor(timestamp: str, last_changed: str) -> str:
    """Encode cursor data for pagination."""
    cursor_json = json.dumps({"ts": timestamp, "lc": last_changed}, separators=(",", ":"))
    return base64.urlsafe_b64encode(cursor_json.encode()).decode()


def decode_cursor(cursor: str) -> dict[str, str] | None:
    """Decode cursor data for pagination."""
    try:
        cursor_json = base64.urlsafe_b64decode(cursor.encode()).decode()
        cursor_data = json.loads(cursor_json)
        if "ts" in cursor_data and "lc" in cursor_data:
            return cursor_data
    except (ValueError, KeyError, json.JSONDecodeError):
        pass
    return None


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string."""
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return None


class HistoryQueryPlanner:
    """Framework-independent history query planning."""

    def __init__(
        self,
        *,
        default_limit: int = HISTORY_DEFAULT_LIMIT,
        max_duration_days: int = HISTORY_MAX_DURATION_DAYS,
        default_page_size: int = DEFAULT_PAGE_SIZE,
        max_page_size: int = MAX_PAGE_SIZE,
    ) -> None:
        self._default_limit = default_limit
        self._max_duration_days = max_duration_days
        self._default_page_size = default_page_size
        self._max_page_size = max_page_size

    def validate_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> BridgeResponse | None:
        """Validate public history time range rules."""
        if end_time - start_time > timedelta(days=self._max_duration_days):
            return _history_error_response(
                "time_range_too_large",
                status=400,
                target="history.time_range",
            )

        if start_time > end_time:
            return _history_error_response(
                "invalid_time_range",
                status=400,
                target="history.time_range",
            )

        return None

    def parse_pagination_params(
        self,
        query: dict[str, Any],
        start_time: datetime,
        end_time: datetime,
    ) -> HistoryPagination:
        """Parse cursor pagination and limit settings."""
        start_time = _ensure_timezone(start_time)
        end_time = _ensure_timezone(end_time)

        cursor_str = query.get("cursor")
        cursor_data = decode_cursor(cursor_str) if cursor_str else None

        try:
            page_size = int(query.get("page_size", self._default_page_size))
            page_size = min(max(1, page_size), self._max_page_size)
            use_pagination = "page_size" in query or cursor_str is not None
        except ValueError:
            page_size = self._default_page_size
            use_pagination = cursor_str is not None

        duration_hours = (end_time - start_time).total_seconds() / 3600
        if use_pagination:
            limit = page_size + 1
        elif duration_hours <= 24:
            limit = 999999
        else:
            try:
                limit = int(query.get("limit", self._default_limit))
                limit = min(limit, self._default_limit)
            except ValueError:
                limit = self._default_limit

        return HistoryPagination(
            cursor_str=cursor_str,
            cursor_data=cursor_data,
            page_size=page_size,
            limit=limit,
            use_pagination=use_pagination,
        )

    def apply_pagination_filter(
        self,
        entity_states: list[Any],
        cursor_data: dict[str, str] | None,
        page_size: int,
        use_pagination: bool,
        state_formatter: Callable[[Any], dict[str, Any]],
    ) -> tuple[list[Any], bool]:
        """Filter and trim query results for cursor pagination."""
        if not use_pagination:
            return entity_states, False

        if cursor_data:
            cursor_lc = cursor_data.get("lc")
            if cursor_lc:
                entity_states = [
                    state
                    for state in entity_states
                    if state_formatter(state).get("last_changed", "") < cursor_lc
                ]

        has_more = len(entity_states) > page_size
        if has_more:
            entity_states = entity_states[:page_size]

        return entity_states, has_more


def _ensure_timezone(value: datetime) -> datetime:
    """Ensure a datetime has UTC tzinfo for duration math."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _history_error_response(
    error: str,
    *,
    status: int,
    target: str = "history",
) -> BridgeResponse:
    """Return an API vNext history error response."""
    return BridgeResponse(
        {
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": error.upper(),
                    "message": error.replace("_", " "),
                    "target": target,
                    "retryable": False,
                }
            ],
        },
        status=status,
    )


def _history_success_response(body: dict[str, Any], *, status: int = 200) -> BridgeResponse:
    """Return an API vNext history success response."""
    return BridgeResponse(
        {
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": body,
            "warnings": [],
            "errors": [],
        },
        status=status,
    )


class HistoryResponseFormatter:
    """Framework-independent history response formatting."""

    def format_state(
        self,
        state: Any,
        decimal_places: int | None = None,
        include_attributes: bool = True,
    ) -> dict[str, Any]:
        """Format a State-like object or compressed state dict."""
        if isinstance(state, dict):
            return self._format_compressed_state(state, decimal_places, include_attributes)

        result = {
            "state": self.format_state_value(state.state, decimal_places),
            "last_changed": state.last_changed.isoformat(),
            "last_updated": state.last_updated.isoformat(),
        }
        if include_attributes:
            attributes = dict(state.attributes)
            result["attributes"] = format_numeric_attributes(attributes) if attributes else {}
        return result

    def format_state_value(self, state: str, decimal_places: int | None) -> str | float:
        """Format a state value with optional numeric precision."""
        if state in ("", "unknown", "unavailable", None):
            return state

        try:
            numeric_value = float(state)
            if decimal_places is not None:
                return round(numeric_value, decimal_places)
            return numeric_value
        except (ValueError, TypeError):
            return state

    def ensure_time_bounds(
        self,
        history_data: list[dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
        is_numeric: bool,
    ) -> list[dict[str, Any]]:
        """Fill missing start/end time boundary points for non-paginated history."""
        if not history_data:
            return []

        result = []
        start_time_iso = start_time.isoformat()
        end_time_iso = end_time.isoformat()

        first_data = history_data[0]
        first_time = first_data.get("last_changed", first_data.get("last_updated", start_time_iso))
        if first_time > start_time_iso and is_numeric:
            result.append(
                {
                    "state": self._coerce_numeric_fill_value(first_data.get("state")),
                    "last_changed": start_time_iso,
                    "last_updated": start_time_iso,
                }
            )

        result.extend(history_data)

        last_data = history_data[-1]
        last_time = last_data.get("last_changed", last_data.get("last_updated", end_time_iso))
        if last_time < end_time_iso:
            result.append(
                {
                    "state": last_data.get("state"),
                    "last_changed": end_time_iso,
                    "last_updated": end_time_iso,
                }
            )

        return result

    def format_response(
        self,
        *,
        entity_states: list[Any],
        entity_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: int,
        page_size: int,
        has_more: bool,
        use_pagination: bool,
        metadata: dict[str, Any] | None = None,
        total_count: int | None = None,
    ) -> dict[str, Any]:
        """Format a single-entity history response."""
        decimal_places = metadata.get("decimal_places") if metadata else None
        is_numeric = metadata.get("is_numeric", False) if metadata else False
        if is_numeric and decimal_places is None:
            decimal_places = 2

        if use_pagination:
            history_data = [
                self.format_state(state, decimal_places, include_attributes=index == 0)
                for index, state in enumerate(entity_states)
            ]
        else:
            history_data = [
                self.format_state(state, decimal_places, include_attributes=index == 0)
                for index, state in enumerate(entity_states[:limit])
            ]
            history_data = self.ensure_time_bounds(
                history_data,
                start_time,
                end_time,
                is_numeric,
            )

        response_data: dict[str, Any] = {
            "entity_id": entity_id,
            "history": history_data,
            "count": len(history_data),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }

        if use_pagination:
            response_data["page_size"] = page_size
            response_data["has_more"] = has_more
            if total_count is not None:
                response_data["total_count"] = total_count
            if has_more and history_data:
                last_state = history_data[-1]
                response_data["next_cursor"] = encode_cursor(
                    last_state["last_updated"],
                    last_state["last_changed"],
                )
        else:
            response_data["truncated"] = has_more

        if metadata:
            response_data["metadata"] = metadata
            device_class = metadata.get("device_class")
            unit = metadata.get("unit_of_measurement", "")
            if device_class:
                response_data["device_class"] = device_class
            if unit:
                response_data["unit_of_measurement"] = unit

            bridge_chart = self._bridge_chart(history_data, device_class, unit)
            if bridge_chart is not None:
                response_data["bridge_chart"] = bridge_chart

        return response_data

    def _bridge_chart(
        self,
        history_data: list[dict[str, Any]],
        device_class: Any,
        unit: Any,
    ) -> dict[str, Any] | None:
        if device_class not in BRIDGE_CHART_DEVICE_CLASSES:
            return None

        decimal_places = get_decimal_places(str(device_class), str(unit or ""))
        points = []
        for state in history_data:
            timestamp = state.get("last_changed") or state.get("last_updated")
            if timestamp is None:
                continue

            try:
                value = float(state.get("state"))
            except (TypeError, ValueError):
                continue

            if decimal_places is not None:
                value = round(value, decimal_places)
            points.append({"at": timestamp, "value": value})

        if not points:
            return None

        return {
            "metric": device_class,
            "unit": unit or "",
            "points": points,
        }

    def _format_compressed_state(
        self,
        state: dict[str, Any],
        decimal_places: int | None,
        include_attributes: bool,
    ) -> dict[str, Any]:
        lc_timestamp = state.get("lc", 0)
        lu_timestamp = state.get("lu", 0)
        if not lc_timestamp:
            lc_timestamp = lu_timestamp

        result: dict[str, Any] = {
            "state": self.format_state_value(state.get("s", "unknown"), decimal_places),
            "last_changed": (
                datetime.fromtimestamp(lc_timestamp, tz=timezone.utc).isoformat()
                if lc_timestamp
                else datetime.now(timezone.utc).isoformat()
            ),
            "last_updated": (
                datetime.fromtimestamp(lu_timestamp, tz=timezone.utc).isoformat()
                if lu_timestamp
                else datetime.now(timezone.utc).isoformat()
            ),
        }

        if include_attributes:
            attributes = state.get("a", {})
            result["attributes"] = format_numeric_attributes(attributes) if attributes else {}

        return result

    def _coerce_numeric_fill_value(self, state: Any) -> float | int:
        """Return a numeric start boundary fill value."""
        try:
            if isinstance(state, (int, float)):
                return state
            if state not in ("unknown", "unavailable", None):
                return float(state)
        except (ValueError, TypeError):
            pass
        return 0


class HistoryMetadataBuilder:
    """Build visualization metadata for history responses."""

    def build(
        self,
        entity_id: str,
        first_state: dict[str, Any],
        all_states: list[dict[str, Any]] | None = None,
        current_attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate metadata from history and optional current state attributes."""
        domain = entity_id.split(".")[0] if "." in entity_id else "sensor"
        attributes = first_state.get("attributes", {})
        device_class = attributes.get("device_class")
        unit = attributes.get("unit_of_measurement", "")
        state_value = first_state.get("state", "")

        if device_class is None and all_states:
            device_class, unit = self._find_device_class(all_states, unit)

        if current_attributes:
            if device_class is None:
                device_class = current_attributes.get("device_class")
            if not unit:
                unit = current_attributes.get("unit_of_measurement", "")
            if "friendly_name" not in attributes and "friendly_name" in current_attributes:
                attributes = dict(attributes)
                attributes["friendly_name"] = current_attributes.get("friendly_name")

        is_numeric = self._is_numeric(state_value)
        visualization = self._visualization(domain, device_class, is_numeric)
        decimal_places = self._decimal_places(entity_id, device_class, unit, is_numeric)

        return {
            "domain": domain,
            "device_class": device_class,
            "unit_of_measurement": unit,
            "friendly_name": attributes.get("friendly_name", entity_id),
            "is_numeric": is_numeric,
            "visualization": visualization,
            "decimal_places": decimal_places,
        }

    def _find_device_class(
        self,
        all_states: list[dict[str, Any]],
        unit: str,
    ) -> tuple[str | None, str]:
        for state in all_states:
            state_attrs = state.get("attributes", {})
            if state_attrs.get("device_class"):
                found_unit = unit or state_attrs.get("unit_of_measurement", "")
                return state_attrs.get("device_class"), found_unit
        return None, unit

    def _is_numeric(self, state_value: Any) -> bool:
        try:
            if state_value not in ("", "unknown", "unavailable", None):
                float(state_value)
                return True
        except (ValueError, TypeError):
            pass
        return False

    def _visualization(
        self,
        domain: str,
        device_class: str | None,
        is_numeric: bool,
    ) -> dict[str, Any]:
        if device_class and device_class in VIZUALIZATION_CONFIG:
            return VIZUALIZATION_CONFIG[device_class].copy()
        if domain in DOMAIN_VISUALIZATION_CONFIG:
            return DOMAIN_VISUALIZATION_CONFIG[domain].copy()
        if is_numeric:
            return {
                "type": "chart",
                "chart_type": "line",
                "color": "#607D8B",
                "show_points": True,
                "interpolation": "linear",
            }
        return {
            "type": "timeline",
            "on_color": "#66BB6A",
            "off_color": "#BDBDBD",
        }

    def _decimal_places(
        self,
        entity_id: str,
        device_class: str | None,
        unit: str,
        is_numeric: bool,
    ) -> int | None:
        if not is_numeric:
            return None

        if device_class:
            decimal_places = get_decimal_places(device_class, unit)
            if decimal_places is not None:
                return decimal_places

        entity_name = entity_id.split(".")[-1].lower()
        for key in [
            "current",
            "voltage",
            "power",
            "energy",
            "temperature",
            "humidity",
            "battery",
            "pressure",
            "power_factor",
            "frequency",
        ]:
            if key in entity_name:
                decimal_places = get_decimal_places(key, unit)
                if decimal_places is not None:
                    return decimal_places

        return 2


class SingleHistoryUseCase:
    """Query and format single-entity history through a port."""

    def __init__(
        self,
        gateway: HistoryGatewayPort,
        *,
        planner: HistoryQueryPlanner | None = None,
        formatter: HistoryResponseFormatter | None = None,
        metadata_builder: HistoryMetadataBuilder | None = None,
    ) -> None:
        self._gateway = gateway
        self._planner = planner or HistoryQueryPlanner()
        self._formatter = formatter or HistoryResponseFormatter()
        self._metadata_builder = metadata_builder or HistoryMetadataBuilder()

    async def execute(self, query: SingleHistoryQuery) -> BridgeResponse:
        """Execute a single history query."""
        raw_states = await self._gateway.query_states(
            query.entity_id,
            query.start_time,
            query.end_time,
            query.significant_changes_only,
        )
        entity_states = list(reversed(raw_states))

        first_state_with_attrs = query.first_state_with_attrs
        if query.use_pagination and query.cursor_data and first_state_with_attrs is None:
            try:
                first_state_with_attrs = await self._gateway.first_state_with_attributes(
                    query.entity_id,
                    query.start_time,
                )
            except Exception:
                first_state_with_attrs = None

        total_count = None
        if query.use_pagination and not query.cursor_data:
            try:
                total_count = await self._gateway.count_states(
                    query.entity_id,
                    query.start_time,
                    query.end_time,
                    query.significant_changes_only,
                )
            except Exception:
                total_count = len(entity_states)

        entity_states, has_more = self._planner.apply_pagination_filter(
            entity_states,
            query.cursor_data,
            query.page_size,
            query.use_pagination,
            self._formatter.format_state,
        )

        if not query.use_pagination:
            has_more = len(raw_states) > query.limit

        metadata = self._build_metadata(query.entity_id, entity_states, first_state_with_attrs)
        body = self._formatter.format_response(
            entity_states=entity_states,
            entity_id=query.entity_id,
            start_time=query.start_time,
            end_time=query.end_time,
            limit=query.limit,
            page_size=query.page_size,
            has_more=has_more,
            use_pagination=query.use_pagination,
            metadata=metadata,
            total_count=total_count,
        )
        return _history_success_response(body)

    def _build_metadata(
        self,
        entity_id: str,
        entity_states: list[Any],
        first_state_with_attrs: Any | None,
    ) -> dict[str, Any] | None:
        if not entity_states:
            return None

        formatted_states = [
            self._formatter.format_state(state, include_attributes=True) for state in entity_states
        ]

        for state in entity_states:
            if isinstance(state, dict) and state.get("a"):
                return self._metadata_builder.build(
                    entity_id,
                    self._formatter.format_state(state),
                    all_states=formatted_states,
                    current_attributes=self._gateway.get_current_attributes(entity_id),
                )
            if not isinstance(state, dict) and getattr(state, "attributes", None):
                return self._metadata_builder.build(
                    entity_id,
                    self._formatter.format_state(state, include_attributes=True),
                    all_states=formatted_states,
                    current_attributes=self._gateway.get_current_attributes(entity_id),
                )

        if first_state_with_attrs is not None:
            return self._metadata_builder.build(
                entity_id,
                self._formatter.format_state(first_state_with_attrs),
                all_states=formatted_states,
                current_attributes=self._gateway.get_current_attributes(entity_id),
            )

        return self._metadata_builder.build(
            entity_id,
            self._formatter.format_state(entity_states[0]),
            all_states=formatted_states,
            current_attributes=self._gateway.get_current_attributes(entity_id),
        )


class BatchHistoryUseCase:
    """Query and format multi-entity history through a port."""

    def __init__(
        self,
        gateway: HistoryGatewayPort,
        *,
        formatter: HistoryResponseFormatter | None = None,
        metadata_builder: HistoryMetadataBuilder | None = None,
    ) -> None:
        self._gateway = gateway
        self._formatter = formatter or HistoryResponseFormatter()
        self._metadata_builder = metadata_builder or HistoryMetadataBuilder()

    async def execute(self, query: BatchHistoryQuery) -> BridgeResponse:
        """Execute a batch history query."""
        states = await self._gateway.query_batch_states(
            query.entity_ids,
            query.start_time,
            query.end_time,
            query.significant_changes_only,
        )

        history_data: dict[str, list[dict[str, Any]]] = {}
        count_data: dict[str, int] = {}
        truncated_data: dict[str, bool] = {}
        metadata_data: dict[str, dict[str, Any]] = {}

        for entity_id in query.entity_ids:
            entity_states = states.get(entity_id, [])
            truncated_data[entity_id] = len(entity_states) > query.limit
            formatted_states, metadata = self._format_entity_history(
                entity_id,
                entity_states,
                query.limit,
                query.start_time,
                query.end_time,
            )
            history_data[entity_id] = formatted_states
            count_data[entity_id] = len(formatted_states)
            if metadata:
                metadata_data[entity_id] = metadata

        body: dict[str, Any] = {
            "history": history_data,
            "count": count_data,
            "truncated": truncated_data,
            "denied_entities": query.denied_entity_ids,
            "start_time": query.start_time.isoformat(),
            "end_time": query.end_time.isoformat(),
        }
        if metadata_data:
            body["metadata"] = metadata_data

        return _history_success_response(body)

    def _format_entity_history(
        self,
        entity_id: str,
        entity_states: list[Any],
        limit: int,
        start_time: datetime,
        end_time: datetime,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        metadata = self._build_metadata(entity_id, entity_states)
        response = self._formatter.format_response(
            entity_states=list(reversed(entity_states)),
            entity_id=entity_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            page_size=limit,
            has_more=False,
            use_pagination=False,
            metadata=metadata,
        )
        return response["history"], metadata

    def _build_metadata(
        self,
        entity_id: str,
        entity_states: list[Any],
    ) -> dict[str, Any] | None:
        if not entity_states:
            return None

        formatted_states = [
            self._formatter.format_state(state, include_attributes=True) for state in entity_states
        ]
        current_attributes = self._gateway.get_current_attributes(entity_id)

        for state in entity_states:
            if isinstance(state, dict) and state.get("a"):
                return self._metadata_builder.build(
                    entity_id,
                    self._formatter.format_state(state),
                    all_states=formatted_states,
                    current_attributes=current_attributes,
                )
            if not isinstance(state, dict) and getattr(state, "attributes", None):
                return self._metadata_builder.build(
                    entity_id,
                    self._formatter.format_state(state, include_attributes=True),
                    all_states=formatted_states,
                    current_attributes=current_attributes,
                )

        return self._metadata_builder.build(
            entity_id,
            self._formatter.format_state(entity_states[0]),
            all_states=formatted_states,
            current_attributes=current_attributes,
        )


class StatisticsUseCase:
    """Query and format recorder statistics through a port."""

    def __init__(self, gateway: HistoryGatewayPort) -> None:
        self._gateway = gateway

    async def execute(self, query: StatisticsQuery) -> BridgeResponse:
        """Execute a statistics query."""
        stats = await self._gateway.query_statistics(
            query.entity_id,
            query.start_time,
            query.end_time,
            query.period,
        )
        statistics_data = [self._format_statistic(stat) for stat in stats]
        body = {
            "entity_id": query.entity_id,
            "period": query.period,
            "statistics": statistics_data,
            "count": len(statistics_data),
            "start_time": query.start_time.isoformat(),
            "end_time": query.end_time.isoformat(),
        }
        return _history_success_response(body)

    def _format_statistic(self, stat: dict[str, Any]) -> dict[str, Any]:
        stat_entry: dict[str, Any] = {
            "start": self._timestamp_to_iso(stat.get("start")),
            "end": self._timestamp_to_iso(stat.get("end")),
        }
        for key in ("mean", "min", "max", "sum", "state"):
            if key in stat and stat[key] is not None:
                stat_entry[key] = stat[key]
        return stat_entry

    def _timestamp_to_iso(self, timestamp: Any) -> str | None:
        if not timestamp:
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
