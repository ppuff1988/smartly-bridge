"""Tests for history application query planning."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.smartly_bridge.application.history import (
    BatchHistoryQuery,
    BatchHistoryUseCase,
    HistoryMetadataBuilder,
    HistoryQueryPlanner,
    HistoryResponseFormatter,
    SingleHistoryQuery,
    SingleHistoryUseCase,
    StatisticsQuery,
    StatisticsUseCase,
    decode_cursor,
    encode_cursor,
    parse_datetime,
)


def test_parse_datetime_accepts_iso8601_and_rejects_invalid_values() -> None:
    """Datetime parsing is framework independent."""
    parsed = parse_datetime("2026-01-10T10:00:00+00:00")

    assert parsed == datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)
    assert parse_datetime(None) is None
    assert parse_datetime("not-a-date") is None


def test_validate_time_range_rejects_large_and_reversed_ranges() -> None:
    """History queries enforce the same public time range errors."""
    planner = HistoryQueryPlanner(max_duration_days=30)
    start_time = datetime(2026, 1, 1, tzinfo=timezone.utc)

    too_large = planner.validate_time_range(start_time, start_time + timedelta(days=31))
    reversed_range = planner.validate_time_range(start_time + timedelta(hours=1), start_time)

    assert too_large is not None
    assert too_large.status == 400
    assert too_large.body["error"] == "time_range_too_large"
    assert too_large.body["max_days"] == 30
    assert too_large.body["schema_version"] == "2026.06"
    assert too_large.body["data"] == {"status": "rejected"}
    assert too_large.body["warnings"] == []
    assert too_large.body["errors"] == [
        {
            "code": "TIME_RANGE_TOO_LARGE",
            "message": "time range too large",
            "target": "history.time_range",
            "retryable": False,
        }
    ]
    assert reversed_range is not None
    assert reversed_range.status == 400
    assert reversed_range.body["error"] == "invalid_time_range"
    assert reversed_range.body["schema_version"] == "2026.06"
    assert reversed_range.body["data"] == {"status": "rejected"}
    assert reversed_range.body["warnings"] == []
    assert reversed_range.body["errors"] == [
        {
            "code": "INVALID_TIME_RANGE",
            "message": "invalid time range",
            "target": "history.time_range",
            "retryable": False,
        }
    ]
    assert planner.validate_time_range(start_time, start_time + timedelta(hours=1)) is None


def test_parse_pagination_params_clamps_page_size_and_uses_page_extra_limit() -> None:
    """Pagination requests fetch one extra record to detect has_more."""
    planner = HistoryQueryPlanner(default_limit=500, default_page_size=100, max_page_size=1000)
    start_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_time = start_time + timedelta(days=2)

    pagination = planner.parse_pagination_params(
        {"page_size": "5000"},
        start_time,
        end_time,
    )

    assert pagination.page_size == 1000
    assert pagination.limit == 1001
    assert pagination.use_pagination is True


def test_parse_pagination_params_keeps_unpaginated_short_ranges_unlimited() -> None:
    """Legacy short-range queries keep the old effectively unlimited limit."""
    planner = HistoryQueryPlanner(default_limit=500)
    start_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)

    pagination = planner.parse_pagination_params({}, start_time, end_time)

    assert pagination.limit == 999999
    assert pagination.use_pagination is False


def test_cursor_round_trip_and_pagination_filter() -> None:
    """Cursor pagination keeps only rows older than the cursor and detects more rows."""
    planner = HistoryQueryPlanner()
    cursor = encode_cursor("2026-01-01T02:00:00+00:00", "2026-01-01T02:00:00+00:00")
    cursor_data = decode_cursor(cursor)
    states = [
        {"last_changed": "2026-01-01T03:00:00+00:00"},
        {"last_changed": "2026-01-01T01:00:00+00:00"},
        {"last_changed": "2026-01-01T00:30:00+00:00"},
    ]

    filtered, has_more = planner.apply_pagination_filter(
        states,
        cursor_data,
        page_size=1,
        use_pagination=True,
        state_formatter=lambda state: state,
    )

    assert filtered == [{"last_changed": "2026-01-01T01:00:00+00:00"}]
    assert has_more is True


def test_format_state_formats_compressed_state_and_attributes() -> None:
    """Compressed recorder rows are serialized without framework objects."""
    formatter = HistoryResponseFormatter()

    result = formatter.format_state(
        {
            "s": "25.567",
            "lc": 1767225600,
            "lu": 1767225660,
            "a": {"temperature": 25.567, "friendly_name": "Temperature"},
        },
        decimal_places=1,
        include_attributes=True,
    )

    assert result["state"] == 25.6
    assert result["attributes"]["temperature"] == 25.6
    assert result["last_changed"].startswith("2026-01-01T00:00:00")


def test_ensure_time_bounds_fills_numeric_edges() -> None:
    """Non-paginated numeric history includes start/end boundary points."""
    formatter = HistoryResponseFormatter()
    start_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)

    result = formatter.ensure_time_bounds(
        [
            {
                "state": 10.0,
                "last_changed": (start_time + timedelta(hours=1)).isoformat(),
                "last_updated": (start_time + timedelta(hours=1)).isoformat(),
            }
        ],
        start_time,
        end_time,
        is_numeric=True,
    )

    assert result[0] == {
        "state": 10.0,
        "last_changed": start_time.isoformat(),
        "last_updated": start_time.isoformat(),
    }
    assert result[-1]["last_changed"] == end_time.isoformat()


def test_format_response_adds_pagination_cursor() -> None:
    """Paginated history responses include has_more and next_cursor."""
    formatter = HistoryResponseFormatter()
    start_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)

    result = formatter.format_response(
        entity_states=[
            {"s": "11", "lc": 1767229200, "lu": 1767229200},
            {"s": "10", "lc": 1767225600, "lu": 1767225600},
        ],
        entity_id="sensor.temperature",
        start_time=start_time,
        end_time=end_time,
        limit=2,
        page_size=2,
        has_more=True,
        use_pagination=True,
        metadata={"is_numeric": True, "decimal_places": 1},
        total_count=5,
    )

    assert result["entity_id"] == "sensor.temperature"
    assert result["count"] == 2
    assert result["has_more"] is True
    assert result["total_count"] == 5
    assert decode_cursor(result["next_cursor"]) == {
        "ts": result["history"][-1]["last_updated"],
        "lc": result["history"][-1]["last_changed"],
    }


def test_format_response_adds_environment_bridge_chart() -> None:
    """Environment sensor history responses include compact chart points."""
    formatter = HistoryResponseFormatter()
    start_time = datetime(2026, 6, 26, 6, 0, tzinfo=timezone.utc)
    end_time = start_time + timedelta(minutes=20)

    result = formatter.format_response(
        entity_states=[
            {"s": "24.567", "lc": 1782453600, "lu": 1782453600},
            {"s": "24.789", "lc": 1782454200, "lu": 1782454200},
            {"s": "24.923", "lc": 1782454800, "lu": 1782454800},
        ],
        entity_id="sensor.temperature",
        start_time=start_time,
        end_time=end_time,
        limit=3,
        page_size=3,
        has_more=False,
        use_pagination=True,
        metadata={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "is_numeric": True,
            "decimal_places": 1,
        },
    )

    assert result["device_class"] == "temperature"
    assert result["unit_of_measurement"] == "°C"
    assert result["bridge_chart"] == {
        "metric": "temperature",
        "unit": "°C",
        "points": [
            {"at": "2026-06-26T06:00:00+00:00", "value": 24.6},
            {"at": "2026-06-26T06:10:00+00:00", "value": 24.8},
            {"at": "2026-06-26T06:20:00+00:00", "value": 24.9},
        ],
    }


def test_format_response_adds_air_quality_bridge_chart() -> None:
    """Air quality sensor history responses include compact chart points."""
    formatter = HistoryResponseFormatter()
    start_time = datetime(2026, 6, 26, 6, 0, tzinfo=timezone.utc)
    end_time = start_time + timedelta(minutes=10)

    result = formatter.format_response(
        entity_states=[
            {"s": "449.789", "lc": 1782453600, "lu": 1782453600},
            {"s": "451.2", "lc": 1782454200, "lu": 1782454200},
        ],
        entity_id="sensor.co2",
        start_time=start_time,
        end_time=end_time,
        limit=2,
        page_size=2,
        has_more=False,
        use_pagination=True,
        metadata={
            "device_class": "carbon_dioxide",
            "unit_of_measurement": "ppm",
            "is_numeric": True,
            "decimal_places": 0,
        },
    )

    assert result["device_class"] == "carbon_dioxide"
    assert result["unit_of_measurement"] == "ppm"
    assert result["bridge_chart"] == {
        "metric": "carbon_dioxide",
        "unit": "ppm",
        "points": [
            {"at": "2026-06-26T06:00:00+00:00", "value": 450},
            {"at": "2026-06-26T06:10:00+00:00", "value": 451},
        ],
    }


def test_metadata_builder_uses_history_device_class_for_numeric_sensor() -> None:
    """Metadata derives visualization and precision from historical attributes."""
    builder = HistoryMetadataBuilder()

    metadata = builder.build(
        "sensor.power",
        {"state": "12.345", "attributes": {"device_class": "power", "unit_of_measurement": "W"}},
    )

    assert metadata["domain"] == "sensor"
    assert metadata["device_class"] == "power"
    assert metadata["unit_of_measurement"] == "W"
    assert metadata["is_numeric"] is True
    assert metadata["decimal_places"] == 2
    assert metadata["visualization"]["type"] == "chart"


def test_metadata_builder_uses_carbon_dioxide_visualization() -> None:
    """CO2 device class gets air quality visualization and precision."""
    builder = HistoryMetadataBuilder()

    metadata = builder.build(
        "sensor.co2",
        {
            "state": "449.789",
            "attributes": {"device_class": "carbon_dioxide", "unit_of_measurement": "ppm"},
        },
    )

    assert metadata["device_class"] == "carbon_dioxide"
    assert metadata["decimal_places"] == 0
    assert metadata["visualization"]["chart_type"] == "area"


def test_metadata_builder_falls_back_to_current_attributes() -> None:
    """Current state attrs can fill metadata that is absent from history rows."""
    builder = HistoryMetadataBuilder()

    metadata = builder.build(
        "sensor.temperature",
        {"state": "25.5", "attributes": {}},
        current_attributes={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "friendly_name": "Room Temperature",
        },
    )

    assert metadata["device_class"] == "temperature"
    assert metadata["unit_of_measurement"] == "°C"
    assert metadata["friendly_name"] == "Room Temperature"
    assert metadata["decimal_places"] == 1


def test_metadata_builder_uses_timeline_for_non_numeric_unknown_domain() -> None:
    """Unknown non-numeric entities default to timeline visualization."""
    builder = HistoryMetadataBuilder()

    metadata = builder.build("binary_sensor.door", {"state": "off", "attributes": {}})

    assert metadata["is_numeric"] is False
    assert metadata["visualization"]["type"] == "timeline"
    assert metadata["decimal_places"] is None


class FakeHistoryGateway:
    """Fake history gateway."""

    def __init__(self, *, fail_count: bool = False, fail_first_state: bool = False) -> None:
        self.states = [
            {
                "s": "10",
                "lc": 1767225600,
                "lu": 1767225600,
                "a": {"device_class": "temperature", "unit_of_measurement": "°C"},
            },
            {"s": "11", "lc": 1767229200, "lu": 1767229200, "a": {}},
        ]
        self.current_attributes = {
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "friendly_name": "Room Temperature",
        }
        self.fail_count = fail_count
        self.fail_first_state = fail_first_state

    async def query_states(
        self,
        entity_id: str,
        start_time: datetime,
        end_time: datetime,
        significant_changes_only: bool,
    ) -> list[dict]:
        return self.states

    async def first_state_with_attributes(
        self,
        entity_id: str,
        start_time: datetime,
    ) -> dict | None:
        if self.fail_first_state:
            raise RuntimeError("metadata query failed")
        return self.states[0]

    async def count_states(
        self,
        entity_id: str,
        start_time: datetime,
        end_time: datetime,
        significant_changes_only: bool,
    ) -> int:
        if self.fail_count:
            raise RuntimeError("count query failed")
        return len(self.states)

    def get_current_attributes(self, entity_id: str) -> dict | None:
        return self.current_attributes


class FakeBatchHistoryGateway:
    """Fake batch history gateway."""

    def __init__(self) -> None:
        self.states = {
            "sensor.temperature": [
                {
                    "s": "10",
                    "lc": 1767225600,
                    "lu": 1767225600,
                    "a": {"device_class": "temperature", "unit_of_measurement": "°C"},
                },
                {"s": "11", "lc": 1767229200, "lu": 1767229200, "a": {}},
            ],
            "binary_sensor.door": [
                {
                    "s": "off",
                    "lc": 1767225600,
                    "lu": 1767225600,
                    "a": {"friendly_name": "Door"},
                }
            ],
        }
        self.current_attributes = {
            "sensor.temperature": {
                "device_class": "temperature",
                "unit_of_measurement": "°C",
                "friendly_name": "Room Temperature",
            },
            "binary_sensor.door": {"friendly_name": "Door"},
        }

    async def query_batch_states(
        self,
        entity_ids: list[str],
        start_time: datetime,
        end_time: datetime,
        significant_changes_only: bool,
    ) -> dict[str, list[dict]]:
        return {entity_id: self.states.get(entity_id, []) for entity_id in entity_ids}

    def get_current_attributes(self, entity_id: str) -> dict | None:
        return self.current_attributes.get(entity_id)


class FakeStatisticsGateway:
    """Fake statistics gateway."""

    async def query_statistics(
        self,
        entity_id: str,
        start_time: datetime,
        end_time: datetime,
        period: str,
    ) -> list[dict]:
        return [
            {
                "start": 1767225600,
                "end": 1767229200,
                "mean": 150.5,
                "min": 50.0,
                "max": 300.0,
                "sum": 3612.0,
                "state": None,
            },
            {
                "start": 1767229200,
                "end": None,
                "mean": None,
                "state": 180.0,
            },
        ]


@pytest.mark.asyncio
async def test_single_history_use_case_formats_gateway_states() -> None:
    """Single history use case queries through a port and formats the response."""
    start_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)
    use_case = SingleHistoryUseCase(FakeHistoryGateway())

    result = await use_case.execute(
        SingleHistoryQuery(
            entity_id="sensor.temperature",
            start_time=start_time,
            end_time=end_time,
            significant_changes_only=True,
            limit=999999,
            page_size=100,
            use_pagination=False,
        )
    )

    assert result.status == 200
    assert result.body["entity_id"] == "sensor.temperature"
    assert result.body["count"] >= 2
    assert result.body["metadata"]["device_class"] == "temperature"
    assert result.body["metadata"]["friendly_name"] == "Room Temperature"
    assert result.body["truncated"] is False


@pytest.mark.asyncio
async def test_batch_history_use_case_formats_multiple_entities() -> None:
    """Batch history use case formats each allowed entity independently."""
    start_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)
    use_case = BatchHistoryUseCase(FakeBatchHistoryGateway())

    result = await use_case.execute(
        BatchHistoryQuery(
            entity_ids=["sensor.temperature", "binary_sensor.door"],
            denied_entity_ids=["sensor.denied"],
            start_time=start_time,
            end_time=end_time,
            limit=999999,
            significant_changes_only=True,
        )
    )

    assert result.status == 200
    assert result.body["history"]["sensor.temperature"][0]["state"] == 11.0
    assert result.body["history"]["binary_sensor.door"][0]["state"] == "off"
    assert result.body["count"] == {"sensor.temperature": 4, "binary_sensor.door": 2}
    assert result.body["truncated"] == {
        "sensor.temperature": False,
        "binary_sensor.door": False,
    }
    assert result.body["denied_entities"] == ["sensor.denied"]
    assert result.body["metadata"]["sensor.temperature"]["device_class"] == "temperature"


@pytest.mark.asyncio
async def test_batch_history_use_case_marks_truncated_entities() -> None:
    """Batch history marks entities truncated when raw rows exceed the limit."""
    start_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_time = start_time + timedelta(days=2)
    use_case = BatchHistoryUseCase(FakeBatchHistoryGateway())

    result = await use_case.execute(
        BatchHistoryQuery(
            entity_ids=["sensor.temperature"],
            denied_entity_ids=[],
            start_time=start_time,
            end_time=end_time,
            limit=1,
            significant_changes_only=True,
        )
    )

    assert result.status == 200
    assert result.body["count"] == {"sensor.temperature": 3}
    assert result.body["truncated"] == {"sensor.temperature": True}


@pytest.mark.asyncio
async def test_statistics_use_case_formats_recorder_statistics() -> None:
    """Statistics use case formats timestamp buckets and omits null values."""
    start_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)
    use_case = StatisticsUseCase(FakeStatisticsGateway())

    result = await use_case.execute(
        StatisticsQuery(
            entity_id="sensor.energy",
            start_time=start_time,
            end_time=end_time,
            period="hour",
        )
    )

    assert result.status == 200
    assert result.body["entity_id"] == "sensor.energy"
    assert result.body["period"] == "hour"
    assert result.body["count"] == 2
    assert result.body["statistics"][0] == {
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-01T01:00:00+00:00",
        "mean": 150.5,
        "min": 50.0,
        "max": 300.0,
        "sum": 3612.0,
    }
    assert result.body["statistics"][1] == {
        "start": "2026-01-01T01:00:00+00:00",
        "end": None,
        "state": 180.0,
    }
    assert result.body["start_time"] == start_time.isoformat()
    assert result.body["end_time"] == end_time.isoformat()


@pytest.mark.asyncio
async def test_single_history_use_case_counts_first_paginated_page() -> None:
    """First paginated page includes total_count and next_cursor when more data exists."""
    start_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)
    use_case = SingleHistoryUseCase(FakeHistoryGateway())

    result = await use_case.execute(
        SingleHistoryQuery(
            entity_id="sensor.temperature",
            start_time=start_time,
            end_time=end_time,
            significant_changes_only=True,
            limit=2,
            page_size=1,
            use_pagination=True,
        )
    )

    assert result.status == 200
    assert result.body["page_size"] == 1
    assert result.body["has_more"] is True
    assert result.body["total_count"] == 2
    assert "next_cursor" in result.body


@pytest.mark.asyncio
async def test_single_history_use_case_falls_back_when_count_fails() -> None:
    """Count failures do not fail the first paginated page."""
    start_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)
    use_case = SingleHistoryUseCase(FakeHistoryGateway(fail_count=True))

    result = await use_case.execute(
        SingleHistoryQuery(
            entity_id="sensor.temperature",
            start_time=start_time,
            end_time=end_time,
            significant_changes_only=True,
            limit=2,
            page_size=1,
            use_pagination=True,
        )
    )

    assert result.status == 200
    assert result.body["total_count"] == 2


@pytest.mark.asyncio
async def test_single_history_use_case_ignores_first_state_metadata_failure() -> None:
    """Cursor pages still return data when the metadata continuity query fails."""
    start_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)
    use_case = SingleHistoryUseCase(FakeHistoryGateway(fail_first_state=True))

    result = await use_case.execute(
        SingleHistoryQuery(
            entity_id="sensor.temperature",
            start_time=start_time,
            end_time=end_time,
            significant_changes_only=True,
            limit=2,
            page_size=2,
            use_pagination=True,
            cursor_data={"lc": "2026-01-01T00:00:01+00:00", "ts": "ignored"},
        )
    )

    assert result.status == 200
    assert result.body["entity_id"] == "sensor.temperature"
