"""Tests for History Views."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.auth import AuthResult, NonceCache, RateLimiter
from custom_components.smartly_bridge.const import (
    DOMAIN,
    HISTORY_MAX_DURATION_DAYS,
    HISTORY_MAX_ENTITIES_BATCH,
)
from custom_components.smartly_bridge.views.history import (
    SmartlyHistoryBatchView,
    SmartlyHistoryView,
    SmartlyStatisticsView,
    _format_state,
    _parse_datetime,
)


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_parse_datetime_valid_iso(self):
        """Test parsing valid ISO 8601 datetime."""
        result = _parse_datetime("2026-01-10T10:00:00+00:00")
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 10

    def test_parse_datetime_none(self):
        """Test parsing None value."""
        result = _parse_datetime(None)
        assert result is None

    def test_parse_datetime_invalid(self):
        """Test parsing invalid datetime string."""
        result = _parse_datetime("not-a-date")
        assert result is None

    def test_format_state(self):
        """Test formatting a State object."""
        mock_state = MagicMock()
        mock_state.state = "on"
        mock_state.attributes = {"brightness": 255}
        mock_state.last_changed = datetime(2026, 1, 10, 10, 0, 0)
        mock_state.last_updated = datetime(2026, 1, 10, 10, 0, 0)

        result = _format_state(mock_state)

        assert result["state"] == "on"
        assert result["attributes"]["brightness"] == 255
        assert "last_changed" in result
        assert "last_updated" in result


class TestSmartlyHistoryView:
    """Tests for SmartlyHistoryView."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                        "trust_proxy": "off",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": RateLimiter(60, 60),
            }
        }
        hass.async_add_executor_job = AsyncMock()
        return hass

    @pytest.fixture
    def mock_request(self, mock_hass):
        """Create mock request."""
        request = MagicMock()
        request.app = {"hass": mock_hass}
        request.headers = {"X-Client-Id": "test_client"}
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        request.read = AsyncMock(return_value=b"")
        request.match_info = {"entity_id": "sensor.temperature"}
        request.query = {}
        return request

    @pytest.mark.asyncio
    async def test_integration_not_configured(self, mock_request, mock_hass):
        """Test error when integration not configured."""
        mock_hass.data = {}
        view = SmartlyHistoryView(mock_request)
        response = await view.get()
        assert response.status == 500
        data = json.loads(response.body)
        assert data["error"] == "integration_not_configured"

    @pytest.mark.asyncio
    async def test_client_secret_not_configured(self, mock_request, mock_hass):
        """Test error when client_secret not configured."""
        mock_hass.data[DOMAIN]["config_entry"].data = {"allowed_cidrs": ""}
        view = SmartlyHistoryView(mock_request)
        response = await view.get()
        assert response.status == 500
        data = json.loads(response.body)
        assert data["error"] == "client_secret_not_configured"

    @pytest.mark.asyncio
    async def test_auth_failure(self, mock_request):
        """Test authentication failure."""
        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=False, error="invalid_signature")

            view = SmartlyHistoryView(mock_request)
            response = await view.get()

            assert response.status == 401
            data = json.loads(response.body)
            assert data["error"] == "invalid_signature"

    @pytest.mark.asyncio
    async def test_rate_limited(self, mock_request, mock_hass):
        """Test rate limiting."""
        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=False)

            view = SmartlyHistoryView(mock_request)
            response = await view.get()

            assert response.status == 429
            data = json.loads(response.body)
            assert data["error"] == "rate_limited"

    @pytest.mark.asyncio
    async def test_entity_id_required(self, mock_request, mock_hass):
        """Test error when entity_id is missing."""
        mock_request.match_info = {}

        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=True)

            view = SmartlyHistoryView(mock_request)
            response = await view.get()

            assert response.status == 400
            data = json.loads(response.body)
            assert data["error"] == "entity_id_required"

    @pytest.mark.asyncio
    async def test_entity_not_allowed(self, mock_request, mock_hass):
        """Test entity access denied."""
        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=True)

            with patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=False,
            ):
                view = SmartlyHistoryView(mock_request)
                response = await view.get()

                assert response.status == 403
                data = json.loads(response.body)
                assert data["error"] == "entity_not_allowed"

    @pytest.mark.asyncio
    async def test_time_range_too_large(self, mock_request, mock_hass):
        """Test time range validation."""
        # Set time range > 30 days
        start_time = datetime.now() - timedelta(days=40)
        mock_request.query = {
            "start_time": start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
        }

        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=True)

            with patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ):
                view = SmartlyHistoryView(mock_request)
                response = await view.get()

                assert response.status == 400
                data = json.loads(response.body)
                assert data["error"] == "time_range_too_large"
                assert data["max_days"] == HISTORY_MAX_DURATION_DAYS

    @pytest.mark.asyncio
    async def test_successful_history_query(self, mock_request, mock_hass):
        """Test successful history query."""
        mock_state = MagicMock()
        mock_state.state = "22.5"
        mock_state.attributes = {"unit_of_measurement": "°C", "device_class": "temperature"}
        mock_state.last_changed = datetime(2026, 1, 10, 10, 0, 0)
        mock_state.last_updated = datetime(2026, 1, 10, 10, 0, 0)

        # Mock recorder instance
        mock_recorder = MagicMock()
        mock_recorder.async_add_executor_job = AsyncMock(
            return_value={"sensor.temperature": [mock_state]}
        )

        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=True)

            with patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ):
                with patch(
                    "homeassistant.helpers.recorder.get_instance",
                    return_value=mock_recorder,
                ):
                    view = SmartlyHistoryView(mock_request)
                    response = await view.get()

                    assert response.status == 200
                    data = json.loads(response.body)
                    assert data["entity_id"] == "sensor.temperature"
                    assert "history" in data
                    # 24 小時查詢會添加邊界點，所以數量會大於等於原始數據
                    assert data["count"] >= 1
                    assert data["truncated"] is False
                    # 驗證包含 metadata
                    assert "metadata" in data
                    assert data["metadata"]["is_numeric"] is True


class TestSmartlyHistoryBatchView:
    """Tests for SmartlyHistoryBatchView."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                        "trust_proxy": "off",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": RateLimiter(60, 60),
            }
        }
        hass.async_add_executor_job = AsyncMock()
        return hass

    @pytest.fixture
    def mock_request(self, mock_hass):
        """Create mock request."""
        request = MagicMock()
        request.app = {"hass": mock_hass}
        request.headers = {"X-Client-Id": "test_client"}
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        request.read = AsyncMock(return_value=b"")
        request.json = AsyncMock(
            return_value={
                "entity_ids": ["sensor.temp1", "sensor.temp2"],
                "start_time": "2026-01-09T00:00:00Z",
                "end_time": "2026-01-10T00:00:00Z",
            }
        )
        return request

    @pytest.mark.asyncio
    async def test_invalid_json(self, mock_request, mock_hass):
        """Test invalid JSON body."""
        mock_request.json = AsyncMock(side_effect=Exception("Invalid JSON"))

        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=True)

            view = SmartlyHistoryBatchView(mock_request)
            response = await view.post()

            assert response.status == 400
            data = json.loads(response.body)
            assert data["error"] == "invalid_json"

    @pytest.mark.asyncio
    async def test_entity_ids_required(self, mock_request, mock_hass):
        """Test error when entity_ids is missing."""
        mock_request.json = AsyncMock(return_value={})

        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=True)

            view = SmartlyHistoryBatchView(mock_request)
            response = await view.post()

            assert response.status == 400
            data = json.loads(response.body)
            assert data["error"] == "entity_ids_required"

    @pytest.mark.asyncio
    async def test_too_many_entities(self, mock_request, mock_hass):
        """Test error when too many entities requested."""
        mock_request.json = AsyncMock(
            return_value={
                "entity_ids": [f"sensor.temp{i}" for i in range(HISTORY_MAX_ENTITIES_BATCH + 1)]
            }
        )

        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=True)

            view = SmartlyHistoryBatchView(mock_request)
            response = await view.post()

            assert response.status == 400
            data = json.loads(response.body)
            assert data["error"] == "too_many_entities"
            assert data["max_entities"] == HISTORY_MAX_ENTITIES_BATCH

    @pytest.mark.asyncio
    async def test_successful_batch_query(self, mock_request, mock_hass):
        """Test successful batch history query."""
        mock_state = MagicMock()
        mock_state.state = "22.5"
        mock_state.attributes = {"unit_of_measurement": "°C", "device_class": "temperature"}
        mock_state.last_changed = datetime(2026, 1, 10, 10, 0, 0)
        mock_state.last_updated = datetime(2026, 1, 10, 10, 0, 0)

        # Mock recorder instance
        mock_recorder = MagicMock()
        mock_recorder.async_add_executor_job = AsyncMock(
            return_value={
                "sensor.temp1": [mock_state],
                "sensor.temp2": [mock_state, mock_state],
            }
        )

        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=True)

            with patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ):
                with patch(
                    "homeassistant.helpers.recorder.get_instance",
                    return_value=mock_recorder,
                ):
                    view = SmartlyHistoryBatchView(mock_request)
                    response = await view.post()

                    assert response.status == 200
                    data = json.loads(response.body)
                    assert "history" in data
                    assert "sensor.temp1" in data["history"]
                    assert "sensor.temp2" in data["history"]
                    # 24 小時查詢會添加邊界點，所以數量會大於等於原始數據
                    assert data["count"]["sensor.temp1"] >= 1
                    assert data["count"]["sensor.temp2"] >= 2
                    # 驗證包含 metadata
                    assert "metadata" in data
                    assert "sensor.temp1" in data["metadata"]
                    assert data["metadata"]["sensor.temp1"]["is_numeric"] is True


class TestSmartlyStatisticsView:
    """Tests for SmartlyStatisticsView."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                        "trust_proxy": "off",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": RateLimiter(60, 60),
            }
        }
        hass.async_add_executor_job = AsyncMock()
        return hass

    @pytest.fixture
    def mock_request(self, mock_hass):
        """Create mock request."""
        request = MagicMock()
        request.app = {"hass": mock_hass}
        request.headers = {"X-Client-Id": "test_client"}
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        request.read = AsyncMock(return_value=b"")
        request.match_info = {"entity_id": "sensor.power"}
        request.query = {"period": "hour"}
        return request

    @pytest.mark.asyncio
    async def test_invalid_period(self, mock_request, mock_hass):
        """Test invalid period parameter."""
        mock_request.query = {"period": "invalid"}

        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=True)

            with patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ):
                view = SmartlyStatisticsView(mock_request)
                response = await view.get()

                assert response.status == 400
                data = json.loads(response.body)
                assert data["error"] == "invalid_period"

    @pytest.mark.asyncio
    async def test_successful_statistics_query(self, mock_request, mock_hass):
        """Test successful statistics query."""
        import time

        # Mock recorder instance
        mock_recorder = MagicMock()
        mock_recorder.async_add_executor_job = AsyncMock(
            return_value={
                "sensor.power": [
                    {
                        "start": time.time() - 3600,
                        "end": time.time(),
                        "mean": 150.5,
                        "min": 50.0,
                        "max": 300.0,
                        "sum": 3612.0,
                    }
                ]
            }
        )

        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=True)

            with patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ):
                with patch(
                    "homeassistant.helpers.recorder.get_instance",
                    return_value=mock_recorder,
                ):
                    view = SmartlyStatisticsView(mock_request)
                    response = await view.get()

                    assert response.status == 200
                    data = json.loads(response.body)
                    assert data["entity_id"] == "sensor.power"
                    assert data["period"] == "hour"
                assert "statistics" in data
                assert len(data["statistics"]) == 1
                assert data["statistics"][0]["mean"] == 150.5
                assert data["statistics"][0]["min"] == 50.0
                assert data["statistics"][0]["max"] == 300.0


class TestCursorPagination:
    """Tests for cursor-based pagination."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "",
                        "trust_proxy": "off",
                    }
                ),
                "nonce_cache": NonceCache(),
                "rate_limiter": RateLimiter(60, 60),
            }
        }
        hass.async_add_executor_job = AsyncMock()
        return hass

    @pytest.fixture
    def mock_request(self, mock_hass):
        """Create mock request."""
        request = MagicMock()
        request.app = {"hass": mock_hass}
        request.headers = {"X-Client-Id": "test_client"}
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        request.read = AsyncMock(return_value=b"")
        request.match_info = {"entity_id": "sensor.temperature"}
        request.query = {}
        return request

    @pytest.mark.asyncio
    async def test_cursor_encode_decode(self):
        """Test cursor encoding and decoding."""
        from custom_components.smartly_bridge.views.history import _decode_cursor, _encode_cursor

        # Test encoding
        timestamp = "2026-01-10T12:00:00Z"
        last_changed = "2026-01-10T12:00:00.123456Z"
        cursor = _encode_cursor(timestamp, last_changed)

        assert cursor is not None
        assert isinstance(cursor, str)

        # Test decoding
        decoded = _decode_cursor(cursor)
        assert decoded is not None
        assert decoded["ts"] == timestamp
        assert decoded["lc"] == last_changed

    @pytest.mark.asyncio
    async def test_cursor_decode_invalid(self):
        """Test decoding invalid cursor."""
        from custom_components.smartly_bridge.views.history import _decode_cursor

        # Invalid base64
        assert _decode_cursor("invalid!!!") is None

        # Valid base64 but invalid JSON
        assert _decode_cursor("aW52YWxpZCBqc29u") is None

        # Valid JSON but missing fields
        import base64

        invalid_json = base64.urlsafe_b64encode(b'{"ts":"time"}').decode()
        assert _decode_cursor(invalid_json) is None

    @pytest.mark.asyncio
    async def test_history_with_cursor_first_page(self, mock_hass, mock_request):
        """Test history query with cursor pagination - first page."""
        mock_request.app = {"hass": mock_hass}
        mock_request.match_info = {"entity_id": "sensor.temperature"}
        mock_request.query = {
            "start_time": "2026-01-09T00:00:00Z",
            "end_time": "2026-01-10T00:00:00Z",
            "page_size": "5",  # Small page size for testing
        }
        mock_request.path_qs = (
            "/api/smartly/history/sensor.temperature?"
            "start_time=2026-01-09T00:00:00Z&end_time=2026-01-10T00:00:00Z&page_size=5"
        )

        # Create mock states (6 items to trigger has_more)
        mock_states = []
        for i in range(6):
            mock_state = MagicMock()
            mock_state.state = f"{20 + i}.5"
            mock_state.last_changed = datetime(2026, 1, 9, i, 0, 0)
            mock_state.last_updated = datetime(2026, 1, 9, i, 0, 0)
            mock_state.attributes = {
                "device_class": "temperature",
                "unit_of_measurement": "°C",
            }
            mock_states.append(mock_state)

        mock_recorder = MagicMock()
        mock_recorder.async_add_executor_job = AsyncMock(
            return_value={"sensor.temperature": mock_states}
        )

        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=True)

            with patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ):
                with patch(
                    "homeassistant.helpers.recorder.get_instance",
                    return_value=mock_recorder,
                ):
                    view = SmartlyHistoryView(mock_request)
                    response = await view.get()

                    assert response.status == 200
                    data = json.loads(response.body)

                    # Verify pagination fields
                    assert data["page_size"] == 5
                    assert data["has_more"] is True
                    assert "next_cursor" in data
                    assert data["count"] <= 5

                    # Verify cursor is valid
                    from custom_components.smartly_bridge.views.history import _decode_cursor

                    decoded = _decode_cursor(data["next_cursor"])
                    assert decoded is not None
                    assert "ts" in decoded
                    assert "lc" in decoded

    @pytest.mark.asyncio
    async def test_history_with_cursor_last_page(self, mock_hass, mock_request):
        """Test history query with cursor pagination - last page."""
        from custom_components.smartly_bridge.views.history import _encode_cursor

        mock_request.app = {"hass": mock_hass}
        mock_request.match_info = {"entity_id": "sensor.temperature"}

        # Create cursor for testing
        cursor = _encode_cursor("2026-01-09T02:00:00Z", "2026-01-09T02:00:00Z")

        mock_request.query = {
            "start_time": "2026-01-09T00:00:00Z",
            "end_time": "2026-01-10T00:00:00Z",
            "page_size": "5",
            "cursor": cursor,
        }
        mock_request.path_qs = (
            f"/api/smartly/history/sensor.temperature?"
            f"start_time=2026-01-09T00:00:00Z&end_time=2026-01-10T00:00:00Z&"
            f"page_size=5&cursor={cursor}"
        )

        # Create mock states (3 items after cursor position: 03:00, 04:00, 05:00)
        mock_states = []
        for i in range(3, 6):
            mock_state = MagicMock()
            mock_state.state = f"{20 + i}.5"
            mock_state.last_changed = datetime(2026, 1, 9, i, 0, 0)
            mock_state.last_updated = datetime(2026, 1, 9, i, 0, 0)
            mock_state.attributes = {
                "device_class": "temperature",
                "unit_of_measurement": "°C",
            }
            mock_states.append(mock_state)

        mock_recorder = MagicMock()
        mock_recorder.async_add_executor_job = AsyncMock(
            return_value={"sensor.temperature": mock_states}
        )

        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=True)

            with patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ):
                with patch(
                    "homeassistant.helpers.recorder.get_instance",
                    return_value=mock_recorder,
                ):
                    view = SmartlyHistoryView(mock_request)
                    response = await view.get()

                    assert response.status == 200
                    data = json.loads(response.body)

                    # Verify last page
                    assert data["page_size"] == 5
                    assert data["has_more"] is False
                    assert "next_cursor" not in data
                    assert data["count"] == 3

    @pytest.mark.asyncio
    async def test_history_with_invalid_cursor(self, mock_hass, mock_request):
        """Test history query with invalid cursor."""
        mock_request.app = {"hass": mock_hass}
        mock_request.match_info = {"entity_id": "sensor.temperature"}
        mock_request.query = {
            "start_time": "2026-01-09T00:00:00Z",
            "end_time": "2026-01-10T00:00:00Z",
            "cursor": "invalid_cursor_string!!!",
        }
        mock_request.path_qs = (
            "/api/smartly/history/sensor.temperature?"
            "start_time=2026-01-09T00:00:00Z&end_time=2026-01-10T00:00:00Z&"
            "cursor=invalid_cursor_string!!!"
        )

        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=True)

            with patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ):
                view = SmartlyHistoryView(mock_request)
                response = await view.get()

                assert response.status == 400
                data = json.loads(response.body)
                assert data["error"] == "invalid_cursor"
