"""Tests for Sync Views."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
