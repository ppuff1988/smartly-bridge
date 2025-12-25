"""Tests for push module."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.const import (
    CONF_CLIENT_SECRET,
    CONF_INSTANCE_ID,
    CONF_WEBHOOK_URL,
)


class TestStatePushManager:
    """Tests for StatePushManager class."""

    @pytest.fixture
    def push_manager(self, mock_hass, mock_config_entry):
        """Create a StatePushManager instance."""
        from custom_components.smartly_bridge.push import StatePushManager

        return StatePushManager(mock_hass, mock_config_entry)

    def test_init(self, push_manager, mock_hass, mock_config_entry):
        """Test StatePushManager initialization."""
        assert push_manager.hass == mock_hass
        assert push_manager.config_entry == mock_config_entry
        assert push_manager._pending_events == []
        assert push_manager._batch_task is None

    @pytest.mark.asyncio
    async def test_state_to_dict(self, push_manager):
        """Test state object to dict conversion."""
        mock_state = MagicMock()
        mock_state.state = "on"
        mock_state.attributes = {"brightness": 255}
        mock_state.last_changed = datetime(2025, 12, 17, 10, 0, 0)
        mock_state.last_updated = datetime(2025, 12, 17, 10, 0, 0)

        result = push_manager._state_to_dict(mock_state)

        assert result["state"] == "on"
        assert result["attributes"] == {"brightness": 255}
        assert "last_changed" in result
        assert "last_updated" in result

    @pytest.mark.asyncio
    async def test_queue_event(self, push_manager):
        """Test queueing state change events."""
        mock_old_state = MagicMock()
        mock_old_state.state = "off"
        mock_old_state.attributes = {}
        mock_old_state.last_changed = datetime(2025, 12, 17, 9, 0, 0)
        mock_old_state.last_updated = datetime(2025, 12, 17, 9, 0, 0)

        mock_new_state = MagicMock()
        mock_new_state.state = "on"
        mock_new_state.attributes = {"brightness": 255}
        mock_new_state.last_changed = datetime(2025, 12, 17, 10, 0, 0)
        mock_new_state.last_updated = datetime(2025, 12, 17, 10, 0, 0)

        await push_manager._queue_event("light.test_light", mock_old_state, mock_new_state)

        assert len(push_manager._pending_events) == 1
        event = push_manager._pending_events[0]
        assert event["entity_id"] == "light.test_light"
        assert event["old_state"]["state"] == "off"
        assert event["new_state"]["state"] == "on"

    @pytest.mark.asyncio
    async def test_stop_flushes_events(self, push_manager):
        """Test that stop flushes pending events."""
        push_manager._session = AsyncMock()
        push_manager._session.close = AsyncMock()
        push_manager._pending_events = [{"entity_id": "test"}]

        with patch.object(push_manager, "_flush_events", new_callable=AsyncMock) as mock_flush:
            await push_manager.stop()
            mock_flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_events_no_webhook(self, push_manager):
        """Test flush does nothing without webhook URL."""
        push_manager.config_entry.data = {
            CONF_WEBHOOK_URL: "",
            CONF_CLIENT_SECRET: "secret",
            CONF_INSTANCE_ID: "test",
        }
        push_manager._pending_events = [{"entity_id": "test"}]

        await push_manager._flush_events()

        # Events should be cleared but not sent
        assert len(push_manager._pending_events) == 0


class TestPushRetry:
    """Tests for push retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, mock_hass, mock_config_entry):
        """Test retry behavior on timeout."""
        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)
        manager._session = MagicMock()

        # Mock session.post to raise timeout
        mock_response = AsyncMock()
        mock_response.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        manager._session.post = MagicMock(return_value=mock_response)

        events = [{"entity_id": "light.test", "new_state": {"state": "on"}}]

        # Should not raise, just log and give up after retries
        with patch("custom_components.smartly_bridge.push._LOGGER") as mock_logger:
            await manager._send_with_retry("https://example.com/events", events)
            # Should have logged warnings for timeouts
            assert mock_logger.warning.called

    @pytest.mark.asyncio
    async def test_retry_on_429(self, mock_hass, mock_config_entry):
        """Test retry behavior on rate limit (429)."""
        from contextlib import asynccontextmanager
        from unittest.mock import MagicMock

        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)

        # Track call count
        call_count = 0

        # Create mock responses
        mock_response_429 = MagicMock()
        mock_response_429.status = 429
        mock_response_429.headers = {"Retry-After": "0"}

        mock_response_200 = MagicMock()
        mock_response_200.status = 200

        @asynccontextmanager
        async def mock_context_manager(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield mock_response_429
            else:
                yield mock_response_200

        # Create mock session
        mock_session = MagicMock()
        mock_session.post = mock_context_manager
        manager._session = mock_session

        events = [{"entity_id": "light.test"}]

        await manager._send_with_retry("https://example.com/events", events)

        assert call_count == 2  # Should have retried once


class TestWebhookUrlHandling:
    """Tests for webhook URL handling."""

    @pytest.mark.asyncio
    async def test_adds_events_suffix(self, mock_hass, mock_config_entry):
        """Test that /events is added to webhook URL if missing."""
        from contextlib import asynccontextmanager

        from custom_components.smartly_bridge.push import StatePushManager

        mock_config_entry.data[CONF_WEBHOOK_URL] = "https://example.com/webhooks"
        manager = StatePushManager(mock_hass, mock_config_entry)

        mock_response = MagicMock()
        mock_response.status = 200

        url_captured = None

        @asynccontextmanager
        async def mock_post(url, *args, **kwargs):
            nonlocal url_captured
            url_captured = url
            yield mock_response

        mock_session = MagicMock()
        mock_session.post = mock_post
        manager._session = mock_session
        manager._pending_events = [{"entity_id": "test"}]

        await manager._flush_events()

        # Verify URL has /events suffix
        assert url_captured.endswith("/events")
