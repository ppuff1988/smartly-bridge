"""Tests for Sync Views."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.adapters.home_assistant import HomeAssistantStateSyncGateway
from custom_components.smartly_bridge.auth import AuthResult, NonceCache, RateLimiter
from custom_components.smartly_bridge.const import DOMAIN
from custom_components.smartly_bridge.views.sync import SmartlySyncStatesView, SmartlySyncView


class TestSmartlySyncView:
    """Tests for SmartlySyncView."""

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
        return request

    @pytest.mark.asyncio
    async def test_integration_not_configured(self, mock_request, mock_hass):
        """Test error when integration not configured."""
        mock_hass.data = {}
        view = SmartlySyncView(mock_request)
        response = await view.get()
        assert response.status == 500

    @pytest.mark.asyncio
    async def test_integration_not_configured_returns_api_vnext_envelope(
        self, mock_request, mock_hass
    ):
        """Test integration-not-configured returns API vNext envelope."""
        mock_hass.data = {}
        view = SmartlySyncView(mock_request)
        response = await view.get()

        assert response.status == 500
        data = json.loads(response.body)
        assert data == {
            "error": "integration_not_configured",
            "schema_version": "2026.06",
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": "INTEGRATION_NOT_CONFIGURED",
                    "message": "integration not configured",
                    "target": "sync.structure.integration",
                    "retryable": False,
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_auth_failure(self, mock_request):
        """Test authentication failure."""
        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=False, error="invalid_signature")

            view = SmartlySyncView(mock_request)
            response = await view.get()

            assert response.status == 401

    @pytest.mark.asyncio
    async def test_auth_failure_returns_api_vnext_envelope(self, mock_request):
        """Test authentication failure returns API vNext envelope."""
        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=False, error="invalid_signature")

            view = SmartlySyncView(mock_request)
            response = await view.get()

            assert response.status == 401
            data = json.loads(response.body)
            assert data == {
                "error": "invalid_signature",
                "schema_version": "2026.06",
                "data": {"status": "rejected"},
                "warnings": [],
                "errors": [
                    {
                        "code": "INVALID_SIGNATURE",
                        "message": "invalid signature",
                        "target": "sync.structure.auth",
                        "retryable": False,
                    }
                ],
            }

    @pytest.mark.asyncio
    async def test_rate_limited(self, mock_request, mock_hass):
        """Test rate limiting."""
        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=False)

            view = SmartlySyncView(mock_request)
            response = await view.get()

            assert response.status == 429

    @pytest.mark.asyncio
    async def test_successful_sync(self, mock_request, mock_hass):
        """Test successful sync request."""
        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.sync.get_allowed_entities",
                return_value=["light.kitchen", "switch.bedroom"],
            ):
                with patch(
                    "custom_components.smartly_bridge.views.sync.get_structure",
                    return_value={
                        "entities": [
                            {"entity_id": "light.kitchen", "name": "Kitchen Light"},
                            {"entity_id": "switch.bedroom", "name": "Bedroom Switch"},
                        ],
                        "areas": [],
                        "devices": [],
                        "floors": [],
                    },
                ), patch(
                    "homeassistant.helpers.entity_registry.async_get",
                    return_value=MagicMock(),
                ), patch(
                    "homeassistant.helpers.device_registry.async_get",
                    return_value=MagicMock(),
                ), patch(
                    "homeassistant.helpers.area_registry.async_get",
                    return_value=MagicMock(),
                ), patch(
                    "homeassistant.helpers.floor_registry.async_get",
                    return_value=MagicMock(),
                ):
                    view = SmartlySyncView(mock_request)
                    response = await view.get()

                    assert response.status == 200
                    import json

                    data = json.loads(response.body)
                    assert "entities" in data
                    assert len(data["entities"]) == 2


class TestSmartlySyncStatesView:
    """Tests for SmartlySyncStatesView."""

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
        return request

    @pytest.mark.asyncio
    async def test_integration_not_configured(self, mock_request, mock_hass):
        """Test error when integration not configured."""
        mock_hass.data = {}
        view = SmartlySyncStatesView(mock_request)
        response = await view.get()
        assert response.status == 500

    @pytest.mark.asyncio
    async def test_auth_failure(self, mock_request):
        """Test authentication failure."""
        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=False, error="invalid_signature")

            view = SmartlySyncStatesView(mock_request)
            response = await view.get()

            assert response.status == 401

    @pytest.mark.asyncio
    async def test_rate_limited(self, mock_request, mock_hass):
        """Test rate limiting."""
        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            rate_limiter = mock_hass.data[DOMAIN]["rate_limiter"]
            rate_limiter.check = AsyncMock(return_value=False)

            view = SmartlySyncStatesView(mock_request)
            response = await view.get()

            assert response.status == 429

    @pytest.mark.asyncio
    async def test_successful_states_sync(self, mock_request, mock_hass):
        """Test successful states sync request."""
        from datetime import datetime, timezone

        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.sync.get_allowed_entities",
                return_value=["light.kitchen", "switch.bedroom"],
            ):
                # Mock entity registry entries with icon info
                mock_entry1 = MagicMock()
                mock_entry1.icon = "mdi:lightbulb"  # Has custom icon
                mock_entry1.original_icon = "mdi:light"

                mock_entry2 = MagicMock()
                mock_entry2.icon = None  # No custom icon, should fallback
                mock_entry2.original_icon = "mdi:toggle-switch"

                # Mock states
                mock_state1 = MagicMock()
                mock_state1.state = "on"
                mock_state1.attributes = {"brightness": 255, "friendly_name": "Kitchen Light"}
                mock_state1.last_changed = datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
                mock_state1.last_updated = datetime(2026, 1, 8, 10, 5, 0, tzinfo=timezone.utc)

                mock_state2 = MagicMock()
                mock_state2.state = "off"
                mock_state2.attributes = {"friendly_name": "Bedroom Switch"}
                mock_state2.last_changed = datetime(2026, 1, 8, 9, 0, 0, tzinfo=timezone.utc)
                mock_state2.last_updated = datetime(2026, 1, 8, 9, 0, 0, tzinfo=timezone.utc)

                def get_state(entity_id):
                    if entity_id == "light.kitchen":
                        return mock_state1
                    elif entity_id == "switch.bedroom":
                        return mock_state2
                    return None

                def async_get_entry(entity_id):
                    if entity_id == "light.kitchen":
                        return mock_entry1
                    elif entity_id == "switch.bedroom":
                        return mock_entry2
                    return None

                mock_hass.states.get = get_state

                # Mock entity registry
                with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get:
                    mock_registry = MagicMock()
                    mock_registry.async_get = async_get_entry
                    mock_er_get.return_value = mock_registry

                    view = SmartlySyncStatesView(mock_request)
                    response = await view.get()

                    assert response.status == 200
                    import json

                    data = json.loads(response.body)
                    assert "states" in data
                    assert data["count"] == 2
                    assert len(data["states"]) == 2

                    # Verify first state with custom icon
                    state1 = next(s for s in data["states"] if s["entity_id"] == "light.kitchen")
                    assert state1["state"] == "on"
                    assert state1["attributes"]["brightness"] == 255
                    assert state1["last_changed"] is not None
                    assert state1["icon"] == "mdi:lightbulb"  # Custom icon is returned

                    # Verify second state with fallback to original_icon
                    state2 = next(s for s in data["states"] if s["entity_id"] == "switch.bedroom")
                    assert state2["state"] == "off"
                    assert state2["icon"] == "mdi:toggle-switch"  # Fallback to original_icon

    @pytest.mark.asyncio
    async def test_states_sync_uses_logical_device_read_path_when_enabled(
        self, mock_request, mock_hass
    ):
        """The sync states endpoint can advertise the logical-device read path."""
        mock_hass.data[DOMAIN]["config_entry"].data["use_logical_devices"] = True

        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.sync.get_allowed_entities",
                return_value=["light.desk"],
            ):
                mock_entry = MagicMock(icon=None, original_icon=None, labels={"smartly"})
                mock_state = MagicMock(
                    state="on",
                    attributes={"friendly_name": "Desk Light", "brightness": 128},
                    last_changed=datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc),
                    last_updated=datetime(2026, 1, 8, 10, 5, 0, tzinfo=timezone.utc),
                )
                mock_hass.states.get = lambda entity_id: (
                    mock_state if entity_id == "light.desk" else None
                )

                with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get:
                    mock_registry = MagicMock()
                    mock_registry.async_get = lambda entity_id: (
                        mock_entry if entity_id == "light.desk" else None
                    )
                    mock_er_get.return_value = mock_registry

                    response = await SmartlySyncStatesView(mock_request).get()

        assert response.status == 200
        data = json.loads(response.body)
        assert data["read_path"] == "logical_devices"
        assert data["device_count"] == 1
        assert data["devices"] == data["logical_devices"]
        assert data["data"]["read_path"] == "logical_devices"
        assert data["data"]["device_count"] == 1
        assert data["data"]["devices"] == data["logical_devices"]
        assert data["states"][0]["entity_id"] == "light.desk"

    @pytest.mark.asyncio
    async def test_states_sync_groups_logical_devices_by_registry_device_id(
        self, mock_request, mock_hass
    ):
        """Shadow logical devices group sibling entities by HA registry device ID."""
        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.sync.get_allowed_entities",
                return_value=["light.desk", "button.desk_scene"],
            ):
                shared_device_id = "ha-device-1"
                mock_light_entry = MagicMock(
                    icon=None,
                    original_icon=None,
                    labels={"smartly"},
                    device_id=shared_device_id,
                )
                mock_button_entry = MagicMock(
                    icon=None,
                    original_icon=None,
                    labels={"smartly"},
                    device_id=shared_device_id,
                )
                mock_light_state = MagicMock(
                    state="on",
                    attributes={
                        "friendly_name": "Desk Light",
                        "brightness": 128,
                    },
                    last_changed=datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc),
                    last_updated=datetime(2026, 1, 8, 10, 5, 0, tzinfo=timezone.utc),
                )
                mock_button_state = MagicMock(
                    state="idle",
                    attributes={"friendly_name": "Desk Scene"},
                    last_changed=datetime(2026, 1, 8, 10, 1, 0, tzinfo=timezone.utc),
                    last_updated=datetime(2026, 1, 8, 10, 1, 0, tzinfo=timezone.utc),
                )

                states = {
                    "light.desk": mock_light_state,
                    "button.desk_scene": mock_button_state,
                }
                entries = {
                    "light.desk": mock_light_entry,
                    "button.desk_scene": mock_button_entry,
                }
                mock_hass.states.get = lambda entity_id: states.get(entity_id)

                with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get:
                    mock_registry = MagicMock()
                    mock_registry.async_get = lambda entity_id: entries.get(entity_id)
                    mock_registry.entities = entries
                    mock_er_get.return_value = mock_registry

                    response = await SmartlySyncStatesView(mock_request).get()

        assert response.status == 200
        data = json.loads(response.body)

        assert [device["id"] for device in data["logical_devices"]] == ["ldev_ha_device_1"]
        logical_device = data["logical_devices"][0]
        assert logical_device["source_entities"] == ["light.desk", "button.desk_scene"]
        assert [capability["type"] for capability in logical_device["capabilities"]] == [
            "power",
            "brightness",
            "button_event",
            "button_press",
        ]
        assert logical_device["capabilities"][2]["source_refs"] == [
            {
                "source": "home_assistant",
                "source_device_id": shared_device_id,
                "source_entity_id": "button.desk_scene",
                "domain": "button",
                "role": "event_source",
                "capability_types": ["button_event"],
            }
        ]
        assert logical_device["capabilities"][3]["source_refs"] == [
            {
                "source": "home_assistant",
                "source_device_id": shared_device_id,
                "source_entity_id": "button.desk_scene",
                "domain": "button",
                "role": "primary_control",
                "capability_types": ["button_press"],
            }
        ]

    @pytest.mark.asyncio
    async def test_states_sync_serializes_datetime_attributes(self, mock_request, mock_hass):
        """Test datetime values in attributes are serialized for JSON responses."""
        from datetime import datetime, timezone

        last_triggered = datetime(2026, 6, 25, 4, 0, 0, tzinfo=timezone.utc)

        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.sync.get_allowed_entities",
                return_value=["automation.wakeup"],
            ):
                mock_state = MagicMock()
                mock_state.state = "on"
                mock_state.attributes = {
                    "friendly_name": "Wakeup",
                    "last_triggered": last_triggered,
                }
                mock_state.last_changed = last_triggered
                mock_state.last_updated = last_triggered

                mock_hass.states.get = MagicMock(return_value=mock_state)

                with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get:
                    mock_registry = MagicMock()
                    mock_registry.async_get = MagicMock(return_value=None)
                    mock_er_get.return_value = mock_registry

                    view = SmartlySyncStatesView(mock_request)
                    response = await view.get()

                    assert response.status == 200
                    import json

                    data = json.loads(response.body)
                    state = data["states"][0]
                    assert state["attributes"]["last_triggered"] == last_triggered.isoformat()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("entity_id", "device_class", "unit", "raw_state", "history_states", "expected_points"),
        [
            (
                "sensor.temperature",
                "temperature",
                "°C",
                "24.567",
                [
                    ("24.1", "2026-06-26T00:00:00Z"),
                    ("24.567", "2026-06-26T06:00:00Z"),
                ],
                [
                    {"at": "2026-06-26T00:00:00Z", "value": 24.1},
                    {"at": "2026-06-26T06:00:00Z", "value": 24.6},
                ],
            ),
            (
                "sensor.humidity",
                "humidity",
                "%",
                "62.345",
                [
                    ("61.1", "2026-06-26T00:00:00Z"),
                    ("62.345", "2026-06-26T06:00:00Z"),
                ],
                [
                    {"at": "2026-06-26T00:00:00Z", "value": 61.1},
                    {"at": "2026-06-26T06:00:00Z", "value": 62.3},
                ],
            ),
            (
                "sensor.co2",
                "carbon_dioxide",
                "ppm",
                "449.789",
                [
                    ("430.2", "2026-06-26T00:00:00Z"),
                    ("449.789", "2026-06-26T06:00:00Z"),
                ],
                [
                    {"at": "2026-06-26T00:00:00Z", "value": 430},
                    {"at": "2026-06-26T06:00:00Z", "value": 450},
                ],
            ),
        ],
    )
    async def test_states_sync_environment_sensor_bridge_chart(
        self,
        mock_request,
        mock_hass,
        entity_id,
        device_class,
        unit,
        raw_state,
        history_states,
        expected_points,
    ):
        """Test environment sensors expose bridge chart metadata."""
        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.sync.get_allowed_entities",
                return_value=[entity_id],
            ):
                mock_state = MagicMock()
                mock_state.state = raw_state
                mock_state.attributes = {
                    "device_class": device_class,
                    "unit_of_measurement": unit,
                    "friendly_name": "Living Room Environment",
                }
                mock_state.last_changed = MagicMock()
                mock_state.last_changed.isoformat = MagicMock(return_value="2026-06-26T06:00:00Z")
                mock_state.last_updated = MagicMock()
                mock_state.last_updated.isoformat = MagicMock(return_value="2026-06-26T06:00:00Z")
                mock_hass.states.get = MagicMock(return_value=mock_state)

                history = []
                for state_value, updated in history_states:
                    history_state = MagicMock()
                    history_state.state = state_value
                    history_state.last_updated.isoformat.return_value = updated
                    history.append(history_state)

                with (
                    patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get,
                    patch(
                        "custom_components.smartly_bridge.adapters.home_assistant."
                        "HomeAssistantHistoryGateway.query_states",
                        new_callable=AsyncMock,
                    ) as mock_query_states,
                ):
                    mock_registry = MagicMock()
                    mock_registry.async_get = MagicMock(return_value=None)
                    mock_er_get.return_value = mock_registry
                    mock_query_states.return_value = history

                    view = SmartlySyncStatesView(mock_request)
                    response = await view.get()

                    assert response.status == 200
                    import json

                    data = json.loads(response.body)
                    sensor_state = data["states"][0]

                    assert sensor_state["device_class"] == "environment_sensor"
                    assert "bridge_chart" not in sensor_state
                    assert sensor_state["attributes"]["unit_of_measurement"] == unit
                    assert sensor_state["attributes"]["bridge_chart"] == {
                        "metric": device_class,
                        "unit": unit,
                        "points": expected_points,
                    }
                    mock_query_states.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_states_sync_bridge_chart_uses_compressed_recorder_history(
        self,
        mock_request,
        mock_hass,
    ):
        """Test sync chart points include compressed recorder states."""
        entity_id = "sensor.temperature"
        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.sync.get_allowed_entities",
                return_value=[entity_id],
            ):
                mock_state = MagicMock()
                mock_state.state = "24.567"
                mock_state.attributes = {
                    "device_class": "temperature",
                    "unit_of_measurement": "°C",
                }
                mock_state.last_changed.isoformat.return_value = "2026-06-26T06:00:00Z"
                mock_state.last_updated.isoformat.return_value = "2026-06-26T06:00:00Z"
                mock_hass.states.get = MagicMock(return_value=mock_state)

                with (
                    patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get,
                    patch(
                        "custom_components.smartly_bridge.adapters.home_assistant."
                        "HomeAssistantHistoryGateway.query_states",
                        new_callable=AsyncMock,
                    ) as mock_query_states,
                ):
                    mock_registry = MagicMock()
                    mock_registry.async_get = MagicMock(return_value=None)
                    mock_er_get.return_value = mock_registry
                    mock_query_states.return_value = [
                        {"s": "24.1", "lu": 1782432000},
                        {"s": "24.567", "lu": 1782453600},
                    ]

                    view = SmartlySyncStatesView(mock_request)
                    response = await view.get()

                    assert response.status == 200
                    import json

                    data = json.loads(response.body)
                    chart = data["states"][0]["attributes"]["bridge_chart"]

                    assert chart["points"] == [
                        {"at": "2026-06-26T00:00:00+00:00", "value": 24.1},
                        {"at": "2026-06-26T06:00:00+00:00", "value": 24.6},
                    ]

    @pytest.mark.asyncio
    async def test_states_sync_bridge_chart_queries_previous_two_hours(
        self,
        mock_request,
        mock_hass,
    ):
        """Test sync chart history is queried from the previous two hours."""
        entity_id = "sensor.temperature"
        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.sync.get_allowed_entities",
                return_value=[entity_id],
            ):
                mock_state = MagicMock()
                mock_state.state = "24.567"
                mock_state.attributes = {
                    "device_class": "temperature",
                    "unit_of_measurement": "°C",
                }
                mock_state.last_changed = datetime(2026, 6, 26, 6, 0, 0, tzinfo=timezone.utc)
                mock_state.last_updated = datetime(2026, 6, 26, 6, 0, 0, tzinfo=timezone.utc)
                mock_hass.states.get = MagicMock(return_value=mock_state)

                with (
                    patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get,
                    patch(
                        "custom_components.smartly_bridge.adapters.home_assistant."
                        "HomeAssistantHistoryGateway.query_states",
                        new_callable=AsyncMock,
                    ) as mock_query_states,
                ):
                    mock_registry = MagicMock()
                    mock_registry.async_get = MagicMock(return_value=None)
                    mock_er_get.return_value = mock_registry
                    mock_query_states.return_value = []

                    view = SmartlySyncStatesView(mock_request)
                    await view.get()

                    _, start_time, end_time = mock_query_states.await_args.args
                    assert start_time == datetime(2026, 6, 26, 4, 0, 0, tzinfo=timezone.utc)
                    assert end_time == datetime(2026, 6, 26, 6, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_states_sync_with_missing_entity(self, mock_request, mock_hass):
        """Test states sync when some entities don't have states."""
        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.sync.get_allowed_entities",
                return_value=["light.kitchen", "light.missing", "switch.bedroom"],
            ):
                # Mock entity registry entries
                mock_entry1 = MagicMock()
                mock_entry1.icon = None
                mock_entry1.original_icon = "mdi:lightbulb"

                mock_entry2 = MagicMock()
                mock_entry2.icon = None
                mock_entry2.original_icon = "mdi:toggle-switch"

                # Mock states - light.missing will return None
                mock_state1 = MagicMock()
                mock_state1.state = "on"
                mock_state1.attributes = {"brightness": 255}
                mock_state1.last_changed = None  # Test None handling
                mock_state1.last_updated = None

                mock_state2 = MagicMock()
                mock_state2.state = "off"
                mock_state2.attributes = {}
                mock_state2.last_changed = None
                mock_state2.last_updated = None

                def get_state(entity_id):
                    if entity_id == "light.kitchen":
                        return mock_state1
                    elif entity_id == "switch.bedroom":
                        return mock_state2
                    return None  # light.missing returns None

                def async_get_entry(entity_id):
                    if entity_id == "light.kitchen":
                        return mock_entry1
                    elif entity_id == "switch.bedroom":
                        return mock_entry2
                    return None

                mock_hass.states.get = get_state

                # Mock entity registry
                with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get:
                    mock_registry = MagicMock()
                    mock_registry.async_get = async_get_entry
                    mock_er_get.return_value = mock_registry

                    view = SmartlySyncStatesView(mock_request)
                    response = await view.get()

                    assert response.status == 200
                    import json

                    data = json.loads(response.body)
                    # Should only include entities with states
                    assert data["count"] == 2
                    assert len(data["states"]) == 2

    @pytest.mark.asyncio
    async def test_states_sync_empty_allowed_entities(self, mock_request, mock_hass):
        """Test states sync with no allowed entities."""
        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.sync.get_allowed_entities",
                return_value=[],
            ):
                view = SmartlySyncStatesView(mock_request)
                response = await view.get()

                assert response.status == 200
                import json

                data = json.loads(response.body)
                assert data["count"] == 0
                assert len(data["states"]) == 0

    @pytest.mark.asyncio
    async def test_states_sync_icon_priority(self, mock_request, mock_hass):
        """Test icon retrieval priority: state > registry custom > registry original."""
        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.sync.get_allowed_entities",
                return_value=["light.state_icon", "light.custom_icon", "light.original_icon"],
            ):
                # Create mock states
                mock_state_1 = MagicMock()
                mock_state_1.state = "on"
                mock_state_1.attributes = {"icon": "mdi:lightbulb-on"}  # Has icon in state
                mock_state_1.last_changed = MagicMock()
                mock_state_1.last_changed.isoformat = MagicMock(return_value="2026-01-10T00:00:00")
                mock_state_1.last_updated = MagicMock()
                mock_state_1.last_updated.isoformat = MagicMock(return_value="2026-01-10T00:00:00")

                mock_state_2 = MagicMock()
                mock_state_2.state = "off"
                mock_state_2.attributes = {}  # No icon in state
                mock_state_2.last_changed = MagicMock()
                mock_state_2.last_changed.isoformat = MagicMock(return_value="2026-01-10T00:00:00")
                mock_state_2.last_updated = MagicMock()
                mock_state_2.last_updated.isoformat = MagicMock(return_value="2026-01-10T00:00:00")

                mock_state_3 = MagicMock()
                mock_state_3.state = "off"
                mock_state_3.attributes = {}  # No icon in state
                mock_state_3.last_changed = MagicMock()
                mock_state_3.last_changed.isoformat = MagicMock(return_value="2026-01-10T00:00:00")
                mock_state_3.last_updated = MagicMock()
                mock_state_3.last_updated.isoformat = MagicMock(return_value="2026-01-10T00:00:00")

                def get_state(entity_id):
                    if entity_id == "light.state_icon":
                        return mock_state_1
                    elif entity_id == "light.custom_icon":
                        return mock_state_2
                    elif entity_id == "light.original_icon":
                        return mock_state_3
                    return None

                # Mock entity registry entries
                mock_entry_1 = MagicMock()
                mock_entry_1.icon = "mdi:custom-should-not-use"  # Should not use this
                mock_entry_1.original_icon = "mdi:original-should-not-use"

                mock_entry_2 = MagicMock()
                mock_entry_2.icon = "mdi:custom-icon"  # Should use this
                mock_entry_2.original_icon = "mdi:original-icon"

                mock_entry_3 = MagicMock()
                mock_entry_3.icon = None  # No custom icon
                mock_entry_3.original_icon = "mdi:original-icon"  # Should use this

                def async_get_entry(entity_id):
                    if entity_id == "light.state_icon":
                        return mock_entry_1
                    elif entity_id == "light.custom_icon":
                        return mock_entry_2
                    elif entity_id == "light.original_icon":
                        return mock_entry_3
                    return None

                mock_hass.states.get = get_state

                # Mock entity registry
                with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get:
                    mock_registry = MagicMock()
                    mock_registry.async_get = async_get_entry
                    mock_er_get.return_value = mock_registry

                    view = SmartlySyncStatesView(mock_request)
                    response = await view.get()

                    assert response.status == 200
                    import json

                    data = json.loads(response.body)
                    assert data["count"] == 3
                    assert len(data["states"]) == 3

                    # Check priority 1: state icon
                    state_1 = next(
                        s for s in data["states"] if s["entity_id"] == "light.state_icon"
                    )
                    assert state_1["icon"] == "mdi:lightbulb-on"

                    # Check priority 2: custom registry icon
                    state_2 = next(
                        s for s in data["states"] if s["entity_id"] == "light.custom_icon"
                    )
                    assert state_2["icon"] == "mdi:custom-icon"

                    # Check priority 3: original registry icon
                    state_3 = next(
                        s for s in data["states"] if s["entity_id"] == "light.original_icon"
                    )
                    assert state_3["icon"] == "mdi:original-icon"

    @pytest.mark.asyncio
    async def test_states_sync_default_icon(self, mock_request, mock_hass):
        """Test that default domain icons are used when no other icon is available."""
        with patch(
            "custom_components.smartly_bridge.views.sync.verify_request",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = AuthResult(success=True, client_id="test")

            with patch(
                "custom_components.smartly_bridge.views.sync.get_allowed_entities",
                return_value=["switch.test", "light.test", "camera.test"],
            ):
                # Create mock states without icon
                mock_state_switch = MagicMock()
                mock_state_switch.state = "on"
                mock_state_switch.attributes = {}  # No icon
                mock_state_switch.last_changed = MagicMock()
                mock_state_switch.last_changed.isoformat = MagicMock(
                    return_value="2026-01-10T00:00:00"
                )
                mock_state_switch.last_updated = MagicMock()
                mock_state_switch.last_updated.isoformat = MagicMock(
                    return_value="2026-01-10T00:00:00"
                )

                mock_state_light = MagicMock()
                mock_state_light.state = "off"
                mock_state_light.attributes = {}
                mock_state_light.last_changed = MagicMock()
                mock_state_light.last_changed.isoformat = MagicMock(
                    return_value="2026-01-10T00:00:00"
                )
                mock_state_light.last_updated = MagicMock()
                mock_state_light.last_updated.isoformat = MagicMock(
                    return_value="2026-01-10T00:00:00"
                )

                mock_state_camera = MagicMock()
                mock_state_camera.state = "idle"
                mock_state_camera.attributes = {}
                mock_state_camera.last_changed = MagicMock()
                mock_state_camera.last_changed.isoformat = MagicMock(
                    return_value="2026-01-10T00:00:00"
                )
                mock_state_camera.last_updated = MagicMock()
                mock_state_camera.last_updated.isoformat = MagicMock(
                    return_value="2026-01-10T00:00:00"
                )

                def get_state(entity_id):
                    if entity_id == "switch.test":
                        return mock_state_switch
                    elif entity_id == "light.test":
                        return mock_state_light
                    elif entity_id == "camera.test":
                        return mock_state_camera
                    return None

                # Mock entity registry - no entry (returns None)
                mock_entity_registry = MagicMock()
                mock_entity_registry.async_get = MagicMock(return_value=None)

                mock_hass.states.get = get_state

                with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get:
                    mock_er_get.return_value = mock_entity_registry

                    view = SmartlySyncStatesView(mock_request)
                    response = await view.get()

                    assert response.status == 200
                    import json

                    data = json.loads(response.body)
                    assert data["count"] == 3

                    # Check default icons
                    switch_state = next(
                        s for s in data["states"] if s["entity_id"] == "switch.test"
                    )
                    assert switch_state["icon"] == "mdi:toggle-switch-outline"

                    light_state = next(s for s in data["states"] if s["entity_id"] == "light.test")
                    assert light_state["icon"] == "mdi:lightbulb-outline"

                    camera_state = next(
                        s for s in data["states"] if s["entity_id"] == "camera.test"
                    )
                    assert camera_state["icon"] == "mdi:camera"

    @pytest.mark.asyncio
    async def test_states_sync_sensor_decimal_formatting(self, mock_request, mock_hass):
        """Test sensor state values are formatted with correct decimal places."""
        with (
            patch("custom_components.smartly_bridge.views.sync.verify_request") as mock_verify,
            patch(
                "custom_components.smartly_bridge.views.sync.get_allowed_entities"
            ) as mock_allowed,
        ):
            # Setup auth success
            mock_verify.return_value = AuthResult(success=True, client_id="test_client")

            # Mock allowed entities - various sensors
            mock_allowed.return_value = [
                "sensor.voltage",
                "sensor.current_ma",
                "sensor.current_a",
                "sensor.power",
                "sensor.temperature",
            ]

            # Create mock states with high precision values
            mock_state_voltage = MagicMock()
            mock_state_voltage.state = "115.699996948242"
            mock_state_voltage.attributes = {
                "device_class": "voltage",
                "unit_of_measurement": "V",
            }
            mock_state_voltage.last_changed = MagicMock()
            mock_state_voltage.last_changed.isoformat = MagicMock(
                return_value="2026-01-11T00:00:00"
            )
            mock_state_voltage.last_updated = MagicMock()
            mock_state_voltage.last_updated.isoformat = MagicMock(
                return_value="2026-01-11T00:00:00"
            )

            mock_state_current_ma = MagicMock()
            mock_state_current_ma.state = "35.0000001490116"
            mock_state_current_ma.attributes = {
                "device_class": "current",
                "unit_of_measurement": "mA",
            }
            mock_state_current_ma.last_changed = MagicMock()
            mock_state_current_ma.last_changed.isoformat = MagicMock(
                return_value="2026-01-11T00:00:00"
            )
            mock_state_current_ma.last_updated = MagicMock()
            mock_state_current_ma.last_updated.isoformat = MagicMock(
                return_value="2026-01-11T00:00:00"
            )

            mock_state_current_a = MagicMock()
            mock_state_current_a.state = "0.456789123456"
            mock_state_current_a.attributes = {
                "device_class": "current",
                "unit_of_measurement": "A",
            }
            mock_state_current_a.last_changed = MagicMock()
            mock_state_current_a.last_changed.isoformat = MagicMock(
                return_value="2026-01-11T00:00:00"
            )
            mock_state_current_a.last_updated = MagicMock()
            mock_state_current_a.last_updated.isoformat = MagicMock(
                return_value="2026-01-11T00:00:00"
            )

            mock_state_power = MagicMock()
            mock_state_power.state = "0.800000011920929"
            mock_state_power.attributes = {
                "device_class": "power",
                "unit_of_measurement": "W",
            }
            mock_state_power.last_changed = MagicMock()
            mock_state_power.last_changed.isoformat = MagicMock(return_value="2026-01-11T00:00:00")
            mock_state_power.last_updated = MagicMock()
            mock_state_power.last_updated.isoformat = MagicMock(return_value="2026-01-11T00:00:00")

            mock_state_temp = MagicMock()
            mock_state_temp.state = "25.56789"
            mock_state_temp.attributes = {
                "device_class": "temperature",
                "unit_of_measurement": "°C",
            }
            mock_state_temp.last_changed = MagicMock()
            mock_state_temp.last_changed.isoformat = MagicMock(return_value="2026-01-11T00:00:00")
            mock_state_temp.last_updated = MagicMock()
            mock_state_temp.last_updated.isoformat = MagicMock(return_value="2026-01-11T00:00:00")

            def get_state(entity_id):
                if entity_id == "sensor.voltage":
                    return mock_state_voltage
                elif entity_id == "sensor.current_ma":
                    return mock_state_current_ma
                elif entity_id == "sensor.current_a":
                    return mock_state_current_a
                elif entity_id == "sensor.power":
                    return mock_state_power
                elif entity_id == "sensor.temperature":
                    return mock_state_temp
                return None

            mock_entity_registry = MagicMock()
            mock_entity_registry.async_get = MagicMock(return_value=None)
            mock_hass.states.get = get_state

            with (
                patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get,
                patch(
                    "custom_components.smartly_bridge.adapters.home_assistant."
                    "HomeAssistantHistoryGateway.query_states",
                    new_callable=AsyncMock,
                ) as mock_query_states,
            ):
                mock_er_get.return_value = mock_entity_registry
                mock_query_states.return_value = []

                view = SmartlySyncStatesView(mock_request)
                response = await view.get()

                assert response.status == 200
                import json

                data = json.loads(response.body)
                assert data["count"] == 5

                # Check voltage: 2 decimal places (V)
                voltage_state = next(
                    s for s in data["states"] if s["entity_id"] == "sensor.voltage"
                )
                assert voltage_state["state"] == "115.7"

                # Check current (mA): 1 decimal place
                current_ma_state = next(
                    s for s in data["states"] if s["entity_id"] == "sensor.current_ma"
                )
                assert current_ma_state["state"] == "35.0"

                # Check current (A): 3 decimal places
                current_a_state = next(
                    s for s in data["states"] if s["entity_id"] == "sensor.current_a"
                )
                assert current_a_state["state"] == "0.457"

                # Check power: 2 decimal places (W)
                power_state = next(s for s in data["states"] if s["entity_id"] == "sensor.power")
                assert power_state["state"] == "0.8"

                # Check temperature: 1 decimal place
                temp_state = next(
                    s for s in data["states"] if s["entity_id"] == "sensor.temperature"
                )
                assert temp_state["state"] == "25.6"


def _state(
    state: str,
    attributes: dict,
    *,
    changed: str = "2026-06-26T10:00:00+00:00",
    updated: str = "2026-06-26T10:00:00+00:00",
):
    mock_state = MagicMock()
    mock_state.state = state
    mock_state.attributes = attributes
    mock_state.last_changed.isoformat.return_value = changed
    mock_state.last_updated.isoformat.return_value = updated
    return mock_state


async def _state_payload(mock_hass, entity_id: str, state, entry=None):
    if entry is None:
        entry = MagicMock(icon=None, original_icon=None, labels=set())

    mock_hass.states.get = MagicMock(return_value=state)
    mock_registry = MagicMock()
    mock_registry.async_get.return_value = entry

    with (
        patch("homeassistant.helpers.entity_registry.async_get", return_value=mock_registry),
        patch(
            "custom_components.smartly_bridge.adapters.home_assistant."
            "HomeAssistantHistoryGateway.query_states",
            new_callable=AsyncMock,
        ) as mock_query_states,
    ):
        mock_query_states.return_value = []
        snapshots = await HomeAssistantStateSyncGateway(
            mock_hass,
            allowed_entities_fn=MagicMock(return_value=[entity_id]),
        ).list_states()
        snapshot = snapshots[0]

    return snapshot.to_sync_dict()


async def _state_payloads(
    mock_hass,
    states_by_entity: dict[str, object],
    entries_by_entity: dict,
    allowed_entity_ids: list[str] | None = None,
):
    def get_state(entity_id):
        return states_by_entity.get(entity_id)

    def get_entry(entity_id):
        return entries_by_entity.get(entity_id)

    mock_hass.states.get = MagicMock(side_effect=get_state)
    mock_registry = MagicMock()
    mock_registry.entities = entries_by_entity
    mock_registry.async_get = MagicMock(side_effect=get_entry)

    with (
        patch("homeassistant.helpers.entity_registry.async_get", return_value=mock_registry),
        patch(
            "custom_components.smartly_bridge.adapters.home_assistant."
            "HomeAssistantHistoryGateway.query_states",
            new_callable=AsyncMock,
        ) as mock_query_states,
    ):
        mock_query_states.return_value = []
        snapshots = await HomeAssistantStateSyncGateway(
            mock_hass,
            allowed_entities_fn=MagicMock(
                return_value=allowed_entity_ids or list(states_by_entity)
            ),
        ).list_states()

    return [snapshot.to_sync_dict() for snapshot in snapshots]


@pytest.mark.asyncio
async def test_state_sync_includes_light_card_capability_metadata(mock_hass):
    """Advanced lights expose normalized capabilities and light presentation."""
    payload = await _state_payload(
        mock_hass,
        "light.living_room",
        _state(
            "on",
            {
                "friendly_name": "Living Light",
                "brightness": 128,
                "supported_color_modes": ["brightness", "color_temp"],
            },
        ),
    )

    assert payload["domain"] == "light"
    assert payload["device_class"] == "smart_light"
    assert payload["capabilities"] == ["on_off", "brightness", "color_temp"]
    assert payload["presentation"]["card_template"] == "light_card"
    assert payload["presentation"]["primary_metric"] == "brightness"


@pytest.mark.asyncio
async def test_state_sync_includes_cover_tilt_capability_metadata(mock_hass):
    """Covers with tilt metadata expose tilt position as a control capability."""
    payload = await _state_payload(
        mock_hass,
        "cover.living_blind",
        _state(
            "open",
            {
                "friendly_name": "Living Blind",
                "current_position": 80,
                "current_tilt_position": 35,
            },
        ),
    )

    assert payload["domain"] == "cover"
    assert payload["device_class"] == "cover_control"
    assert payload["capabilities"] == [
        "open_close",
        "position",
        "tilt_position",
        "stop",
    ]
    assert payload["presentation"]["card_template"] == "cover_card"


@pytest.mark.asyncio
async def test_state_sync_includes_climate_preset_mode_capability_metadata(mock_hass):
    """Climate preset metadata is exposed as a canonical preset mode capability."""
    payload = await _state_payload(
        mock_hass,
        "climate.living_room",
        _state(
            "cool",
            {
                "friendly_name": "Living Room AC",
                "temperature": 24,
                "hvac_mode": "cool",
                "hvac_modes": ["off", "cool", "heat"],
                "preset_mode": "eco",
                "preset_modes": ["eco", "comfort", "sleep"],
            },
        ),
    )

    assert payload["domain"] == "climate"
    assert payload["device_class"] == "climate_control"
    assert payload["capabilities"] == [
        "target_temperature",
        "hvac_mode",
        "preset_mode",
    ]
    assert payload["presentation"]["card_template"] == "climate_card"


@pytest.mark.asyncio
async def test_state_sync_includes_climate_swing_mode_capability_metadata(mock_hass):
    """Climate swing metadata is exposed as a canonical swing mode capability."""
    payload = await _state_payload(
        mock_hass,
        "climate.living_room",
        _state(
            "cool",
            {
                "friendly_name": "Living Room AC",
                "temperature": 24,
                "hvac_mode": "cool",
                "hvac_modes": ["off", "cool", "heat"],
                "swing_mode": "vertical",
                "swing_modes": ["off", "vertical", "horizontal"],
            },
        ),
    )

    assert payload["domain"] == "climate"
    assert payload["device_class"] == "climate_control"
    assert payload["capabilities"] == [
        "target_temperature",
        "hvac_mode",
        "swing_mode",
    ]
    assert payload["presentation"]["card_template"] == "climate_card"


@pytest.mark.asyncio
async def test_state_sync_includes_climate_temperature_range_capability_metadata(mock_hass):
    """Climate heat/cool range metadata is exposed as a canonical range capability."""
    payload = await _state_payload(
        mock_hass,
        "climate.living_room",
        _state(
            "heat_cool",
            {
                "friendly_name": "Living Room AC",
                "target_temp_low": 22,
                "target_temp_high": 26,
                "hvac_mode": "heat_cool",
                "hvac_modes": ["off", "cool", "heat", "heat_cool"],
            },
        ),
    )

    assert payload["domain"] == "climate"
    assert payload["device_class"] == "climate_control"
    assert payload["capabilities"] == [
        "target_temperature_range",
        "hvac_mode",
    ]
    assert payload["presentation"]["card_template"] == "climate_card"


@pytest.mark.asyncio
async def test_state_sync_includes_fan_direction_capability_metadata(mock_hass):
    """Fan direction metadata is exposed as a canonical direction capability."""
    payload = await _state_payload(
        mock_hass,
        "fan.bedroom",
        _state(
            "on",
            {
                "friendly_name": "Bedroom Fan",
                "direction": "forward",
            },
        ),
    )

    assert payload["domain"] == "fan"
    assert payload["device_class"] == "fan_control"
    assert payload["capabilities"] == ["on_off", "fan_direction"]
    assert payload["presentation"]["card_template"] == "control_card"


@pytest.mark.asyncio
async def test_state_sync_includes_fan_oscillation_capability_metadata(mock_hass):
    """Fan oscillation metadata is exposed as a canonical oscillation capability."""
    payload = await _state_payload(
        mock_hass,
        "fan.bedroom",
        _state(
            "on",
            {
                "friendly_name": "Bedroom Fan",
                "oscillating": True,
            },
        ),
    )

    assert payload["domain"] == "fan"
    assert payload["device_class"] == "fan_control"
    assert payload["capabilities"] == ["on_off", "fan_oscillation"]
    assert payload["presentation"]["card_template"] == "control_card"


@pytest.mark.asyncio
async def test_state_sync_includes_environment_sensor_card_metadata(mock_hass):
    """Environmental sensors expose metric-card metadata."""
    payload = await _state_payload(
        mock_hass,
        "sensor.living_temperature",
        _state(
            "24.6",
            {
                "friendly_name": "Living Temperature",
                "device_class": "temperature",
                "unit_of_measurement": "°C",
                "humidity": 61,
                "battery": 84,
            },
        ),
    )

    assert payload["domain"] == "sensor"
    assert payload["device_class"] == "environment_sensor"
    assert payload["capabilities"] == ["temperature", "humidity", "battery"]
    assert payload["presentation"] == {
        "card_template": "metric_card",
        "primary_metric": "temperature",
        "secondary_metrics": ["humidity", "battery"],
        "dashboard_priority": 40,
        "favorite": False,
    }


@pytest.mark.asyncio
async def test_state_sync_normalizes_linkquality_signal_metadata(mock_hass):
    """Linkquality is exposed as normalized signal strength metadata."""
    payload = await _state_payload(
        mock_hass,
        "sensor.living_temperature",
        _state(
            "24.6",
            {
                "friendly_name": "Living Temperature",
                "device_class": "temperature",
                "unit_of_measurement": "°C",
                "humidity": 61,
                "battery": 84,
                "linkquality": 236,
            },
        ),
    )

    assert payload["attributes"]["linkquality"] == 236
    assert payload["attributes"]["signal_strength"] == 236
    assert payload["attributes"]["signal_unit"] == "lqi"
    assert payload["capabilities"] == [
        "temperature",
        "humidity",
        "battery",
        "signal_strength",
    ]
    assert payload["presentation"]["secondary_metrics"] == [
        "humidity",
        "battery",
    ]


@pytest.mark.asyncio
async def test_state_sync_merges_sibling_linkquality_signal_metadata(mock_hass):
    """Unlabelled sibling Zigbee linkquality sensors are exposed on the primary card."""
    device_id = "zigbee-device-1"
    payloads = await _state_payloads(
        mock_hass,
        {
            "sensor.living_temperature": _state(
                "24.6",
                {
                    "friendly_name": "Living Temperature",
                    "device_class": "temperature",
                    "unit_of_measurement": "°C",
                    "humidity": 61,
                    "battery": 84,
                },
            ),
            "sensor.living_linkquality": _state(
                "236",
                {
                    "friendly_name": "Living Linkquality",
                    "unit_of_measurement": "lqi",
                },
            ),
        },
        {
            "sensor.living_temperature": MagicMock(
                icon=None,
                original_icon=None,
                labels={"smartly"},
                device_id=device_id,
            ),
            "sensor.living_linkquality": MagicMock(
                icon=None,
                original_icon=None,
                labels=set(),
                device_id=device_id,
            ),
        },
        allowed_entity_ids=["sensor.living_temperature"],
    )

    assert [item["entity_id"] for item in payloads] == ["sensor.living_temperature"]
    payload = next(item for item in payloads if item["entity_id"] == "sensor.living_temperature")

    assert payload["attributes"]["linkquality"] == 236
    assert payload["attributes"]["signal_strength"] == 236
    assert payload["attributes"]["signal_unit"] == "lqi"
    assert payload["capabilities"] == [
        "temperature",
        "humidity",
        "battery",
        "signal_strength",
    ]


@pytest.mark.asyncio
async def test_state_sync_exposes_presence_sibling_setting_controls(mock_hass):
    """Presence cards expose sibling number/select entities as editable settings."""
    device_id = "zigbee-presence-1"
    payloads = await _state_payloads(
        mock_hass,
        {
            "binary_sensor.presence": _state(
                "on",
                {
                    "friendly_name": "人體存在感應器",
                    "device_class": "occupancy",
                    "illuminance": "bright",
                },
            ),
            "number.presence_detection_delay": _state(
                "15",
                {
                    "friendly_name": "觸發維持秒數",
                    "min": 1,
                    "max": 120,
                    "step": 1,
                    "unit_of_measurement": "s",
                },
            ),
            "select.presence_occupancy_sensitivity": _state(
                "low",
                {
                    "friendly_name": "感應強度",
                    "options": ["low", "medium", "high"],
                },
            ),
        },
        {
            "binary_sensor.presence": MagicMock(
                icon=None,
                original_icon=None,
                labels={"smartly"},
                device_id=device_id,
            ),
            "number.presence_detection_delay": MagicMock(
                icon=None,
                original_icon=None,
                labels=set(),
                device_id=device_id,
            ),
            "select.presence_occupancy_sensitivity": MagicMock(
                icon=None,
                original_icon=None,
                labels=set(),
                device_id=device_id,
            ),
        },
        allowed_entity_ids=["binary_sensor.presence"],
    )

    payload = next(item for item in payloads if item["entity_id"] == "binary_sensor.presence")

    assert payload["device_class"] == "presence_sensor"
    assert payload["presentation"]["setting_controls"] == [
        {
            "key": "trigger_hold_seconds",
            "entity_id": "number.presence_detection_delay",
            "domain": "number",
            "name": "觸發維持秒數",
            "action": "set_value",
            "value": 15,
            "min": 1,
            "max": 120,
            "step": 1,
            "unit": "s",
        },
        {
            "key": "occupancy_sensitivity",
            "entity_id": "select.presence_occupancy_sensitivity",
            "domain": "select",
            "name": "感應強度",
            "action": "select_option",
            "value": "low",
            "options": ["low", "medium", "high"],
        },
    ]


@pytest.mark.asyncio
async def test_state_sync_keeps_high_risk_camera_read_only(mock_hass):
    """High-risk domains fall back to unknown read-only cards."""
    payload = await _state_payload(
        mock_hass,
        "camera.porch",
        _state("idle", {"friendly_name": "Porch Cam"}),
    )

    assert payload["domain"] == "camera"
    assert payload["device_class"] == "unknown_device"
    assert payload["capabilities"] == []
    assert payload["presentation"]["card_template"] == "unknown_card"


@pytest.mark.asyncio
async def test_state_sync_respects_safe_smartly_class_label_override(mock_hass):
    """smartly.class labels can safely refine switch presentation."""
    payload = await _state_payload(
        mock_hass,
        "switch.fan",
        _state("off", {"friendly_name": "Fan Switch"}),
        MagicMock(
            icon=None,
            original_icon=None,
            labels={"smartly", "smartly.class.fan_control"},
        ),
    )

    assert payload["domain"] == "switch"
    assert payload["device_class"] == "fan_control"
    assert payload["capabilities"] == ["on_off"]
    assert payload["presentation"]["card_template"] == "control_card"
