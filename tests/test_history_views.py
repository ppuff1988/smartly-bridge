"""Tests for History Views."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.adapters.home_assistant import (
    HomeAssistantHistoryGateway,
    _home_assistant_history_gateway,
)
from custom_components.smartly_bridge.application.history import (
    BatchHistoryQuery,
    SingleHistoryQuery,
    StatisticsQuery,
)
from custom_components.smartly_bridge.auth import AuthResult, NonceCache, RateLimiter
from custom_components.smartly_bridge.const import (
    DOMAIN,
    HISTORY_MAX_ENTITIES_BATCH,
    RATE_WINDOW,
)
from custom_components.smartly_bridge.domain.models import BridgeResponse
from custom_components.smartly_bridge.views.history import (
    SmartlyHistoryBatchView,
    SmartlyHistoryView,
    SmartlyStatisticsView,
    _format_state,
    _parse_datetime,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api-vnext"


def _api_vnext_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


class FakeRuntimeHistoryGateway:
    """History gateway used to verify setup runtime wiring."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.states = [
            {
                "s": "10",
                "lc": 1767225600,
                "lu": 1767225600,
                "a": {"device_class": "temperature", "unit_of_measurement": "°C"},
            },
            {"s": "11", "lc": 1767229200, "lu": 1767229200, "a": {}},
        ]

    async def query_states(
        self,
        entity_id: str,
        start_time: datetime,
        end_time: datetime,
        significant_changes_only: bool,
    ) -> list[dict]:
        self.calls.append("query_states")
        return self.states

    async def query_batch_states(
        self,
        entity_ids: list[str],
        start_time: datetime,
        end_time: datetime,
        significant_changes_only: bool,
    ) -> dict[str, list[dict]]:
        self.calls.append("query_batch_states")
        return {entity_id: self.states for entity_id in entity_ids}

    async def first_state_with_attributes(
        self,
        entity_id: str,
        start_time: datetime,
    ) -> dict | None:
        self.calls.append("first_state_with_attributes")
        return self.states[0]

    async def count_states(
        self,
        entity_id: str,
        start_time: datetime,
        end_time: datetime,
        significant_changes_only: bool,
    ) -> int:
        self.calls.append("count_states")
        return len(self.states)

    def get_current_attributes(self, entity_id: str) -> dict | None:
        self.calls.append("get_current_attributes")
        return {"device_class": "temperature", "unit_of_measurement": "°C"}

    async def query_statistics(
        self,
        entity_id: str,
        start_time: datetime,
        end_time: datetime,
        period: str,
    ) -> list[dict]:
        self.calls.append("query_statistics")
        return [
            {
                "start": 1767225600,
                "end": 1767229200,
                "mean": 150.5,
                "min": 50.0,
                "max": 300.0,
                "sum": 3612.0,
            }
        ]


def test_home_assistant_history_gateway_factory_builds_runtime_gateway(mock_hass) -> None:
    """Home Assistant history gateway factory builds the runtime adapter type."""
    gateway = _home_assistant_history_gateway(mock_hass, MagicMock())

    assert isinstance(gateway, HomeAssistantHistoryGateway)


def test_history_read_gateway_resolver_uses_runtime_gateway(mock_hass) -> None:
    """History read gateway resolver returns the setup-created runtime port."""
    from custom_components.smartly_bridge.views.history import _history_read_gateway

    gateway = FakeRuntimeHistoryGateway()
    mock_hass.data[DOMAIN] = {"runtime_adapters": {"history_gateway": gateway}}

    result = _history_read_gateway(mock_hass)

    assert result is gateway


def test_history_read_gateway_resolver_requires_runtime_gateway(mock_hass) -> None:
    """History read gateway resolver requires a setup-created runtime gateway."""
    from custom_components.smartly_bridge.views.history import _history_read_gateway

    mock_hass.data[DOMAIN] = {"runtime_adapters": {}}

    result = _history_read_gateway(mock_hass)

    assert result is None
    assert "history_gateway" not in mock_hass.data[DOMAIN]["runtime_adapters"]


@pytest.mark.asyncio
async def test_query_single_history_forwards_query_to_application_use_case() -> None:
    """Single history invocation adapter forwards query to the recorder gateway."""
    from custom_components.smartly_bridge.views.history import _query_single_history

    gateway = FakeRuntimeHistoryGateway()
    query = SingleHistoryQuery(
        entity_id="sensor.temperature",
        start_time=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        end_time=datetime.fromisoformat("2026-01-01T02:00:00+00:00"),
        significant_changes_only=True,
        limit=100,
        page_size=100,
        use_pagination=False,
    )

    result = await _query_single_history(gateway, query)

    assert result.status == 200
    assert result.body["data"]["entity_id"] == "sensor.temperature"
    assert "query_states" in gateway.calls


@pytest.mark.asyncio
async def test_query_single_history_uses_injected_use_case_factory() -> None:
    """Single history invocation adapter accepts an injected use-case factory."""
    from custom_components.smartly_bridge.views.history import _query_single_history

    class FakeSingleHistoryUseCase:
        def __init__(self) -> None:
            self.queries = []

        async def execute(self, query: SingleHistoryQuery) -> BridgeResponse:
            self.queries.append(query)
            return BridgeResponse(
                {
                    "schema_version": "2026.06",
                    "data": {"entity_id": query.entity_id},
                    "warnings": [],
                    "errors": [],
                },
                status=200,
            )

    gateway = FakeRuntimeHistoryGateway()
    use_case = FakeSingleHistoryUseCase()
    factory_calls = []
    query = SingleHistoryQuery(
        entity_id="sensor.temperature",
        start_time=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        end_time=datetime.fromisoformat("2026-01-01T02:00:00+00:00"),
        significant_changes_only=True,
        limit=100,
        page_size=100,
        use_pagination=False,
    )

    def use_case_factory(received_gateway):
        factory_calls.append(received_gateway)
        return use_case

    result = await _query_single_history(
        gateway,
        query,
        use_case_factory=use_case_factory,
    )

    assert result.status == 200
    assert result.body["data"]["entity_id"] == "sensor.temperature"
    assert factory_calls == [gateway]
    assert use_case.queries == [query]


@pytest.mark.asyncio
async def test_query_batch_history_forwards_query_to_application_use_case() -> None:
    """Batch history invocation adapter forwards query to the recorder gateway."""
    from custom_components.smartly_bridge.views.history import _query_batch_history

    gateway = FakeRuntimeHistoryGateway()
    query = BatchHistoryQuery(
        entity_ids=["sensor.temperature", "sensor.humidity"],
        denied_entity_ids=["sensor.private"],
        start_time=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        end_time=datetime.fromisoformat("2026-01-01T02:00:00+00:00"),
        limit=100,
        significant_changes_only=True,
    )

    result = await _query_batch_history(gateway, query)

    assert result.status == 200
    assert set(result.body["data"]["history"]) == {"sensor.temperature", "sensor.humidity"}
    assert result.body["data"]["denied_entities"] == ["sensor.private"]
    assert "query_batch_states" in gateway.calls


@pytest.mark.asyncio
async def test_query_batch_history_uses_injected_use_case_factory() -> None:
    """Batch history invocation adapter accepts an injected use-case factory."""
    from custom_components.smartly_bridge.views.history import _query_batch_history

    class FakeBatchHistoryUseCase:
        def __init__(self) -> None:
            self.queries = []

        async def execute(self, query: BatchHistoryQuery) -> BridgeResponse:
            self.queries.append(query)
            return BridgeResponse(
                {
                    "schema_version": "2026.06",
                    "data": {"entity_ids": query.entity_ids},
                    "warnings": [],
                    "errors": [],
                },
                status=200,
            )

    gateway = FakeRuntimeHistoryGateway()
    use_case = FakeBatchHistoryUseCase()
    factory_calls = []
    query = BatchHistoryQuery(
        entity_ids=["sensor.temperature", "sensor.humidity"],
        denied_entity_ids=["sensor.private"],
        start_time=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        end_time=datetime.fromisoformat("2026-01-01T02:00:00+00:00"),
        limit=100,
        significant_changes_only=True,
    )

    def use_case_factory(received_gateway):
        factory_calls.append(received_gateway)
        return use_case

    result = await _query_batch_history(
        gateway,
        query,
        use_case_factory=use_case_factory,
    )

    assert result.status == 200
    assert result.body["data"]["entity_ids"] == [
        "sensor.temperature",
        "sensor.humidity",
    ]
    assert factory_calls == [gateway]
    assert use_case.queries == [query]


@pytest.mark.asyncio
async def test_query_statistics_forwards_query_to_application_use_case() -> None:
    """Statistics invocation adapter forwards query to the recorder gateway."""
    from custom_components.smartly_bridge.views.history import _query_statistics

    gateway = FakeRuntimeHistoryGateway()
    query = StatisticsQuery(
        entity_id="sensor.energy",
        start_time=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        end_time=datetime.fromisoformat("2026-01-02T00:00:00+00:00"),
        period="hour",
    )

    result = await _query_statistics(gateway, query)

    assert result.status == 200
    assert result.body["data"]["entity_id"] == "sensor.energy"
    assert result.body["data"]["period"] == "hour"
    assert result.body["data"]["statistics"][0]["mean"] == 150.5
    assert "query_statistics" in gateway.calls


@pytest.mark.asyncio
async def test_query_statistics_uses_injected_use_case_factory() -> None:
    """Statistics invocation adapter accepts an injected use-case factory."""
    from custom_components.smartly_bridge.views.history import _query_statistics

    class FakeStatisticsUseCase:
        def __init__(self) -> None:
            self.queries = []

        async def execute(self, query: StatisticsQuery) -> BridgeResponse:
            self.queries.append(query)
            return BridgeResponse(
                {
                    "schema_version": "2026.06",
                    "data": {"entity_id": query.entity_id, "period": query.period},
                    "warnings": [],
                    "errors": [],
                },
                status=200,
            )

    gateway = FakeRuntimeHistoryGateway()
    use_case = FakeStatisticsUseCase()
    factory_calls = []
    query = StatisticsQuery(
        entity_id="sensor.energy",
        start_time=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        end_time=datetime.fromisoformat("2026-01-02T00:00:00+00:00"),
        period="hour",
    )

    def use_case_factory(received_gateway):
        factory_calls.append(received_gateway)
        return use_case

    result = await _query_statistics(
        gateway,
        query,
        use_case_factory=use_case_factory,
    )

    assert result.status == 200
    assert result.body["data"]["entity_id"] == "sensor.energy"
    assert result.body["data"]["period"] == "hour"
    assert factory_calls == [gateway]
    assert use_case.queries == [query]


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
        hass.data[DOMAIN]["runtime_adapters"] = {
            "history_gateway": _home_assistant_history_gateway(hass, MagicMock())
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
        assert data["errors"][0]["code"] == "INTEGRATION_NOT_CONFIGURED"

    @pytest.mark.asyncio
    async def test_integration_not_configured_returns_api_vnext_envelope(
        self, mock_request, mock_hass
    ):
        """Test integration-not-configured failure returns API vNext envelope."""
        mock_hass.data = {}

        view = SmartlyHistoryView(mock_request)
        response = await view.get()

        assert response.status == 500
        data = json.loads(response.body)
        assert data == _api_vnext_fixture("history-integration-not-configured.json")

    @pytest.mark.asyncio
    async def test_client_secret_not_configured(self, mock_request, mock_hass):
        """Test error when client_secret not configured."""
        mock_hass.data[DOMAIN]["config_entry"].data = {"allowed_cidrs": ""}
        view = SmartlyHistoryView(mock_request)
        response = await view.get()
        assert response.status == 500
        data = json.loads(response.body)
        assert data["errors"][0]["code"] == "CLIENT_SECRET_NOT_CONFIGURED"

    @pytest.mark.asyncio
    async def test_client_secret_not_configured_returns_api_vnext_envelope(
        self, mock_request, mock_hass
    ):
        """Test missing client secret failure returns API vNext envelope."""
        mock_hass.data[DOMAIN]["config_entry"].data = {"allowed_cidrs": ""}

        view = SmartlyHistoryView(mock_request)
        response = await view.get()

        assert response.status == 500
        data = json.loads(response.body)
        assert data == _api_vnext_fixture("history-client-secret-not-configured.json")

    @pytest.mark.asyncio
    async def test_auth_helper_client_secret_missing_returns_api_vnext_envelope(self, mock_request):
        """Test defensive auth helper client-secret failure returns API vNext envelope."""
        view = SmartlyHistoryView(mock_request)

        auth_result, response = await view._verify_auth_and_rate_limit({"allowed_cidrs": ""})

        assert auth_result.success is False
        assert auth_result.error == "client_secret_not_configured"
        assert response is not None
        assert response.status == 500
        data = json.loads(response.body)
        assert data == _api_vnext_fixture("history-client-secret-not-configured.json")

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
            assert data["errors"][0]["code"] == "INVALID_SIGNATURE"

    @pytest.mark.asyncio
    async def test_auth_failure_returns_api_vnext_envelope(self, mock_request):
        """Test authentication failure returns API vNext envelope."""
        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=False, error="invalid_signature")

            view = SmartlyHistoryView(mock_request)
            response = await view.get()

            assert response.status == 401
            data = json.loads(response.body)
            assert data == _api_vnext_fixture("history-auth-failure.json")

    @pytest.mark.asyncio
    async def test_rate_limited(self, mock_request, mock_hass):
        """Test rate limiting returns API vNext envelope."""
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
            assert response.headers["Retry-After"] == str(RATE_WINDOW)
            assert response.headers["X-RateLimit-Remaining"] == "0"
            data = json.loads(response.body)
            assert data == _api_vnext_fixture("history-rate-limit.json")

    @pytest.mark.asyncio
    async def test_entity_id_required(self, mock_request, mock_hass):
        """Test missing entity_id returns API vNext envelope."""
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
            assert data == _api_vnext_fixture("history-entity-id-required.json")

    @pytest.mark.asyncio
    async def test_entity_not_allowed(self, mock_request, mock_hass):
        """Test entity access denied returns API vNext envelope."""
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
                assert data == _api_vnext_fixture("history-entity-not-allowed.json")

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
                assert data["errors"][0]["code"] == "TIME_RANGE_TOO_LARGE"

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
                    assert data["data"]["entity_id"] == "sensor.temperature"
                    assert "history" in data["data"]
                    # 24 小時查詢會添加邊界點，所以數量會大於等於原始數據
                    assert data["data"]["count"] >= 1
                    assert data["data"]["truncated"] is False
                    # 驗證包含 metadata
                    assert "metadata" in data["data"]
                    assert data["data"]["metadata"]["is_numeric"] is True

    @pytest.mark.asyncio
    async def test_single_history_uses_setup_runtime_gateway(self, mock_request, mock_hass):
        """Single history requests execute through the setup-created history gateway."""
        gateway = FakeRuntimeHistoryGateway()
        mock_hass.data[DOMAIN]["runtime_adapters"] = {"history_gateway": gateway}

        with (
            patch(
                "custom_components.smartly_bridge.views.history.verify_request",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ),
        ):
            mock_verify.return_value = AuthResult(success=True, client_id="test")
            mock_hass.data[DOMAIN]["rate_limiter"].check = AsyncMock(return_value=True)

            response = await SmartlyHistoryView(mock_request).get()

        assert response.status == 200
        data = json.loads(response.body)
        assert data["data"]["entity_id"] == "sensor.temperature"
        assert data["data"]["history"][0]["state"] == 11.0
        assert gateway.calls == ["query_states", "get_current_attributes"]

    @pytest.mark.asyncio
    async def test_single_history_requires_setup_runtime_gateway(
        self,
        mock_request,
        mock_hass,
    ):
        """Single history requests fail when setup did not create the gateway."""
        mock_hass.data[DOMAIN]["runtime_adapters"] = {}

        with (
            patch(
                "custom_components.smartly_bridge.views.history.verify_request",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ),
        ):
            mock_verify.return_value = AuthResult(success=True, client_id="test")
            mock_hass.data[DOMAIN]["rate_limiter"].check = AsyncMock(return_value=True)

            response = await SmartlyHistoryView(mock_request).get()

        assert response.status == 500
        assert json.loads(response.body) == _api_vnext_fixture("history-gateway-unavailable.json")
        assert "history_gateway" not in mock_hass.data[DOMAIN]["runtime_adapters"]

    @pytest.mark.asyncio
    async def test_single_history_response_includes_request_context_headers(
        self, mock_request, mock_hass
    ):
        """Single history responses echo optional request correlation headers."""
        gateway = FakeRuntimeHistoryGateway()
        mock_hass.data[DOMAIN]["runtime_adapters"] = {"history_gateway": gateway}
        mock_request.headers["X-Request-Id"] = "req-history-001"
        mock_request.headers["X-Correlation-Id"] = "corr-history-001"

        with (
            patch(
                "custom_components.smartly_bridge.views.history.verify_request",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ),
        ):
            mock_verify.return_value = AuthResult(success=True, client_id="test")
            mock_hass.data[DOMAIN]["rate_limiter"].check = AsyncMock(return_value=True)

            response = await SmartlyHistoryView(mock_request).get()

        assert response.status == 200
        data = json.loads(response.body)
        assert data["request_id"] == "req-history-001"
        assert data["correlation_id"] == "corr-history-001"
        assert data["data"]["entity_id"] == "sensor.temperature"
        assert data["data"]["history"][0]["state"] == 11.0

    @pytest.mark.asyncio
    async def test_query_timeout_returns_api_vnext_envelope(self, mock_request, mock_hass):
        """Test history query timeout returns API vNext envelope."""
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
                    "custom_components.smartly_bridge.views.history.SingleHistoryUseCase.execute",
                    new_callable=AsyncMock,
                ) as mock_execute:
                    mock_execute.side_effect = asyncio.TimeoutError

                    view = SmartlyHistoryView(mock_request)
                    response = await view.get()

                    assert response.status == 504
                    data = json.loads(response.body)
                    assert data == _api_vnext_fixture("history-query-timeout.json")

    @pytest.mark.asyncio
    async def test_query_failure_returns_api_vnext_envelope(self, mock_request, mock_hass):
        """Test history query failure returns API vNext envelope."""
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
                    "custom_components.smartly_bridge.views.history.SingleHistoryUseCase.execute",
                    new_callable=AsyncMock,
                ) as mock_execute:
                    mock_execute.side_effect = RuntimeError("recorder unavailable")

                    view = SmartlyHistoryView(mock_request)
                    response = await view.get()

                    assert response.status == 500
                    data = json.loads(response.body)
                    assert data == _api_vnext_fixture("history-query-failure.json")


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
        hass.data[DOMAIN]["runtime_adapters"] = {
            "history_gateway": _home_assistant_history_gateway(hass, MagicMock())
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
    async def test_integration_not_configured_returns_api_vnext_envelope(
        self, mock_request, mock_hass
    ):
        """Test missing integration data returns API vNext envelope."""
        mock_hass.data = {}

        view = SmartlyHistoryBatchView(mock_request)
        response = await view.post()

        assert response.status == 500
        data = json.loads(response.body)
        assert data == _api_vnext_fixture("history-batch-integration-not-configured.json")

    @pytest.mark.asyncio
    async def test_client_secret_not_configured_returns_api_vnext_envelope(
        self, mock_request, mock_hass
    ):
        """Test missing client secret returns API vNext envelope."""
        mock_hass.data[DOMAIN]["config_entry"].data = {
            "allowed_cidrs": "",
            "trust_proxy": "off",
        }

        view = SmartlyHistoryBatchView(mock_request)
        response = await view.post()

        assert response.status == 500
        data = json.loads(response.body)
        assert data == _api_vnext_fixture("history-batch-client-secret-not-configured.json")

    @pytest.mark.asyncio
    async def test_auth_failure_returns_api_vnext_envelope(self, mock_request):
        """Test authentication failure returns API vNext envelope."""
        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=False, error="invalid_signature")

            view = SmartlyHistoryBatchView(mock_request)
            response = await view.post()

            assert response.status == 401
            data = json.loads(response.body)
            assert data == _api_vnext_fixture("history-batch-auth-failure.json")

    @pytest.mark.asyncio
    async def test_rate_limited_returns_api_vnext_envelope(self, mock_request, mock_hass):
        """Test rate limiting returns API vNext envelope."""
        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=False)

            view = SmartlyHistoryBatchView(mock_request)
            response = await view.post()

            assert response.status == 429
            assert response.headers["Retry-After"] == str(RATE_WINDOW)
            assert response.headers["X-RateLimit-Remaining"] == "0"
            data = json.loads(response.body)
            assert data == _api_vnext_fixture("history-batch-rate-limit.json")

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
            assert data["errors"][0]["code"] == "INVALID_JSON"

    @pytest.mark.asyncio
    async def test_invalid_json_returns_api_vnext_envelope(self, mock_request, mock_hass):
        """Test invalid JSON body returns API vNext envelope."""
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
            assert data == _api_vnext_fixture("history-batch-invalid-json.json")

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
            assert data["errors"][0]["code"] == "ENTITY_IDS_REQUIRED"

    @pytest.mark.asyncio
    async def test_entity_ids_required_returns_api_vnext_envelope(self, mock_request, mock_hass):
        """Test missing entity IDs returns API vNext envelope."""
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
            assert data == _api_vnext_fixture("history-batch-entity-ids-required.json")

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
            assert data["errors"][0]["code"] == "TOO_MANY_ENTITIES"

    @pytest.mark.asyncio
    async def test_too_many_entities_returns_api_vnext_envelope(self, mock_request, mock_hass):
        """Test too many entity IDs returns API vNext envelope."""
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
            assert data == _api_vnext_fixture("history-batch-too-many-entities.json")

    @pytest.mark.asyncio
    async def test_no_allowed_entities_returns_api_vnext_envelope(self, mock_request, mock_hass):
        """Test denied batch entities returns API vNext envelope."""
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
                view = SmartlyHistoryBatchView(mock_request)
                response = await view.post()

                assert response.status == 403
                data = json.loads(response.body)
                assert data == _api_vnext_fixture("history-batch-no-allowed-entities.json")

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
                    assert "history" in data["data"]
                    assert "sensor.temp1" in data["data"]["history"]
                    assert "sensor.temp2" in data["data"]["history"]
                    # 24 小時查詢會添加邊界點，所以數量會大於等於原始數據
                    assert data["data"]["count"]["sensor.temp1"] >= 1
                    assert data["data"]["count"]["sensor.temp2"] >= 2
                    # 驗證包含 metadata
                    assert "metadata" in data["data"]
                    assert "sensor.temp1" in data["data"]["metadata"]
                    assert data["data"]["metadata"]["sensor.temp1"]["is_numeric"] is True

    @pytest.mark.asyncio
    async def test_batch_history_uses_setup_runtime_gateway(self, mock_request, mock_hass):
        """Batch history requests execute through the setup-created history gateway."""
        gateway = FakeRuntimeHistoryGateway()
        mock_hass.data[DOMAIN]["runtime_adapters"] = {"history_gateway": gateway}

        with (
            patch(
                "custom_components.smartly_bridge.views.history.verify_request",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ),
        ):
            mock_verify.return_value = AuthResult(success=True, client_id="test")
            mock_hass.data[DOMAIN]["rate_limiter"].check = AsyncMock(return_value=True)

            response = await SmartlyHistoryBatchView(mock_request).post()

        assert response.status == 200
        data = json.loads(response.body)
        assert sorted(data["data"]["history"]) == ["sensor.temp1", "sensor.temp2"]
        assert data["data"]["history"]["sensor.temp1"][0]["state"] == 11.0
        assert gateway.calls == [
            "query_batch_states",
            "get_current_attributes",
            "get_current_attributes",
        ]

    @pytest.mark.asyncio
    async def test_batch_history_requires_setup_runtime_gateway(
        self,
        mock_request,
        mock_hass,
    ):
        """Batch history requests fail when setup did not create the gateway."""
        mock_hass.data[DOMAIN]["runtime_adapters"] = {}

        with (
            patch(
                "custom_components.smartly_bridge.views.history.verify_request",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ),
        ):
            mock_verify.return_value = AuthResult(success=True, client_id="test")
            mock_hass.data[DOMAIN]["rate_limiter"].check = AsyncMock(return_value=True)

            response = await SmartlyHistoryBatchView(mock_request).post()

        assert response.status == 500
        assert json.loads(response.body) == _api_vnext_fixture(
            "history-batch-gateway-unavailable.json"
        )
        assert "history_gateway" not in mock_hass.data[DOMAIN]["runtime_adapters"]

    @pytest.mark.asyncio
    async def test_batch_query_timeout_returns_api_vnext_envelope(self, mock_request, mock_hass):
        """Test batch history timeout returns API vNext envelope."""
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
                    "custom_components.smartly_bridge.views.history.BatchHistoryUseCase.execute",
                    new_callable=AsyncMock,
                ) as mock_execute:
                    mock_execute.side_effect = asyncio.TimeoutError

                    view = SmartlyHistoryBatchView(mock_request)
                    response = await view.post()

                    assert response.status == 504
                    data = json.loads(response.body)
                    assert data == _api_vnext_fixture("history-batch-query-timeout.json")

    @pytest.mark.asyncio
    async def test_batch_query_failure_returns_api_vnext_envelope(self, mock_request, mock_hass):
        """Test batch history failure returns API vNext envelope."""
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
                    "custom_components.smartly_bridge.views.history.BatchHistoryUseCase.execute",
                    new_callable=AsyncMock,
                ) as mock_execute:
                    mock_execute.side_effect = RuntimeError("batch recorder unavailable")

                    view = SmartlyHistoryBatchView(mock_request)
                    response = await view.post()

                    assert response.status == 500
                    data = json.loads(response.body)
                    assert data == _api_vnext_fixture("history-batch-query-failure.json")


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
        hass.data[DOMAIN]["runtime_adapters"] = {
            "history_gateway": _home_assistant_history_gateway(hass, MagicMock())
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
    async def test_integration_not_configured_returns_api_vnext_envelope(
        self, mock_request, mock_hass
    ):
        """Test missing integration data returns API vNext envelope."""
        mock_hass.data = {}

        view = SmartlyStatisticsView(mock_request)
        response = await view.get()

        assert response.status == 500
        data = json.loads(response.body)
        assert data == _api_vnext_fixture("statistics-integration-not-configured.json")

    @pytest.mark.asyncio
    async def test_client_secret_not_configured_returns_api_vnext_envelope(
        self, mock_request, mock_hass
    ):
        """Test missing client secret returns API vNext envelope."""
        mock_hass.data[DOMAIN]["config_entry"].data = {
            "allowed_cidrs": "",
            "trust_proxy": "off",
        }

        view = SmartlyStatisticsView(mock_request)
        response = await view.get()

        assert response.status == 500
        data = json.loads(response.body)
        assert data == _api_vnext_fixture("statistics-client-secret-not-configured.json")

    @pytest.mark.asyncio
    async def test_auth_failure_returns_api_vnext_envelope(self, mock_request, mock_hass):
        """Test authentication failure returns API vNext envelope."""
        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=False, error="invalid_signature")

            view = SmartlyStatisticsView(mock_request)
            response = await view.get()

            assert response.status == 401
            data = json.loads(response.body)
            assert data == _api_vnext_fixture("statistics-auth-failure.json")

    @pytest.mark.asyncio
    async def test_rate_limited_returns_api_vnext_envelope(self, mock_request, mock_hass):
        """Test rate limit failure returns API vNext envelope."""
        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=False)

            view = SmartlyStatisticsView(mock_request)
            response = await view.get()

            assert response.status == 429
            assert response.headers["Retry-After"] == "60"
            assert response.headers["X-RateLimit-Remaining"] == "0"
            data = json.loads(response.body)
            assert data == _api_vnext_fixture("statistics-rate-limit.json")

    @pytest.mark.asyncio
    async def test_entity_id_required_returns_api_vnext_envelope(self, mock_request, mock_hass):
        """Test missing entity_id returns API vNext envelope."""
        mock_request.match_info = {}

        with patch(
            "custom_components.smartly_bridge.views.history.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=True)

            view = SmartlyStatisticsView(mock_request)
            response = await view.get()

            assert response.status == 400
            data = json.loads(response.body)
            assert data == _api_vnext_fixture("statistics-entity-id-required.json")

    @pytest.mark.asyncio
    async def test_entity_not_allowed_returns_api_vnext_envelope(self, mock_request, mock_hass):
        """Test denied entity returns API vNext envelope."""
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
                view = SmartlyStatisticsView(mock_request)
                response = await view.get()

                assert response.status == 403
                data = json.loads(response.body)
                assert data == _api_vnext_fixture("statistics-entity-not-allowed.json")

    @pytest.mark.asyncio
    async def test_invalid_period_returns_api_vnext_envelope(self, mock_request, mock_hass):
        """Test invalid period returns API vNext envelope."""
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
                assert data == _api_vnext_fixture("statistics-invalid-period.json")

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
                    assert data["data"]["entity_id"] == "sensor.power"
                    assert data["data"]["period"] == "hour"
                assert "statistics" in data["data"]
                assert len(data["data"]["statistics"]) == 1
                assert data["data"]["statistics"][0]["mean"] == 150.5
                assert data["data"]["statistics"][0]["min"] == 50.0
                assert data["data"]["statistics"][0]["max"] == 300.0

    @pytest.mark.asyncio
    async def test_statistics_uses_setup_runtime_gateway(self, mock_request, mock_hass):
        """Statistics requests execute through the setup-created history gateway."""
        gateway = FakeRuntimeHistoryGateway()
        mock_hass.data[DOMAIN]["runtime_adapters"] = {"history_gateway": gateway}

        with (
            patch(
                "custom_components.smartly_bridge.views.history.verify_request",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ),
        ):
            mock_verify.return_value = AuthResult(success=True, client_id="test")
            mock_hass.data[DOMAIN]["rate_limiter"].check = AsyncMock(return_value=True)

            response = await SmartlyStatisticsView(mock_request).get()

        assert response.status == 200
        data = json.loads(response.body)
        assert data["data"]["entity_id"] == "sensor.power"
        assert data["data"]["statistics"][0]["mean"] == 150.5
        assert gateway.calls == ["query_statistics"]

    @pytest.mark.asyncio
    async def test_statistics_requires_setup_runtime_gateway(
        self,
        mock_request,
        mock_hass,
    ):
        """Statistics requests fail when setup did not create the gateway."""
        mock_hass.data[DOMAIN]["runtime_adapters"] = {}

        with (
            patch(
                "custom_components.smartly_bridge.views.history.verify_request",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "custom_components.smartly_bridge.views.history.is_entity_allowed",
                return_value=True,
            ),
        ):
            mock_verify.return_value = AuthResult(success=True, client_id="test")
            mock_hass.data[DOMAIN]["rate_limiter"].check = AsyncMock(return_value=True)

            response = await SmartlyStatisticsView(mock_request).get()

        assert response.status == 500
        assert json.loads(response.body) == _api_vnext_fixture(
            "statistics-gateway-unavailable.json"
        )
        assert "history_gateway" not in mock_hass.data[DOMAIN]["runtime_adapters"]

    @pytest.mark.asyncio
    async def test_statistics_query_failure_returns_api_vnext_envelope(
        self, mock_request, mock_hass
    ):
        """Test statistics failure returns API vNext envelope."""
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
                    "custom_components.smartly_bridge.views.history.StatisticsUseCase.execute",
                    new_callable=AsyncMock,
                ) as mock_execute:
                    mock_execute.side_effect = RuntimeError("statistics recorder unavailable")

                    view = SmartlyStatisticsView(mock_request)
                    response = await view.get()

                    assert response.status == 500
                    data = json.loads(response.body)
                    assert data == _api_vnext_fixture("statistics-query-failure.json")


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
        hass.data[DOMAIN]["runtime_adapters"] = {
            "history_gateway": _home_assistant_history_gateway(hass, MagicMock())
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
                    assert data["data"]["page_size"] == 5
                    assert data["data"]["has_more"] is True
                    assert "next_cursor" in data["data"]
                    assert data["data"]["count"] <= 5

                    # Verify cursor is valid
                    from custom_components.smartly_bridge.views.history import _decode_cursor

                    decoded = _decode_cursor(data["data"]["next_cursor"])
                    assert decoded is not None
                    assert "ts" in decoded
                    assert "lc" in decoded

    @pytest.mark.asyncio
    async def test_history_with_cursor_last_page(self, mock_hass, mock_request):
        """Test history query with cursor pagination - last page."""
        from custom_components.smartly_bridge.views.history import _encode_cursor

        mock_request.app = {"hass": mock_hass}
        mock_request.match_info = {"entity_id": "sensor.temperature"}

        # Create cursor for testing (反序：游標指向較舊的時間點)
        cursor = _encode_cursor("2026-01-09T03:00:00Z", "2026-01-09T03:00:00Z")

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

        # Create mock states (反序：3 items before cursor position: 00:00, 01:00, 02:00)
        mock_states = []
        for i in range(0, 3):
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
                    assert data["data"]["page_size"] == 5
                    assert data["data"]["has_more"] is False
                    assert "next_cursor" not in data
                    assert data["data"]["count"] == 3

    @pytest.mark.asyncio
    async def test_history_with_invalid_cursor(self, mock_hass, mock_request):
        """Test invalid cursor returns API vNext envelope."""
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
                assert data == _api_vnext_fixture("history-invalid-cursor.json")
