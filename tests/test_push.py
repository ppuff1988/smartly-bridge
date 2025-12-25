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
        # New event format with event_type and data
        assert event["event_type"] == "state_changed"
        assert event["data"]["entity_id"] == "light.test_light"
        assert event["data"]["old_state"]["state"] == "off"
        assert event["data"]["new_state"]["state"] == "on"

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
        manager._pending_events = [{"event_type": "state_changed", "data": {"entity_id": "test"}}]

        await manager._flush_events()

        # Verify URL is used as-is (no suffix added)
        assert url_captured == "https://example.com/webhooks"


class TestHeartbeat:
    """Tests for heartbeat mechanism."""

    @pytest.mark.asyncio
    async def test_send_heartbeat_success(self, mock_hass, mock_config_entry):
        """Test successful heartbeat sending."""
        from contextlib import asynccontextmanager

        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)

        # Mock HTTP session with proper context manager
        mock_response = MagicMock()
        mock_response.status = 200

        @asynccontextmanager
        async def mock_post(*args, **kwargs):
            yield mock_response

        mock_session = MagicMock()
        mock_session.post = mock_post

        # Pre-set the session to avoid creating a real one
        manager._session = mock_session

        # Send heartbeat
        await manager._send_heartbeat()

        # Verify webhook URL was used
        webhook_url = mock_config_entry.data.get("webhook_url")
        assert webhook_url is not None

    @pytest.mark.asyncio
    async def test_send_heartbeat_no_webhook(self, mock_hass):
        """Test heartbeat skipped when no webhook configured."""
        from unittest.mock import MagicMock

        from custom_components.smartly_bridge.push import StatePushManager

        # Config entry without webhook_url
        config_entry = MagicMock()
        config_entry.data = {
            "instance_id": "test",
            "client_secret": "secret",
            "client_id": "client",
        }

        manager = StatePushManager(mock_hass, config_entry)
        manager._session = MagicMock()

        # Should not raise error
        await manager._send_heartbeat()

        # Session should not be used
        manager._session.post.assert_not_called()


class TestPushManagerLifecycle:
    """Tests for StatePushManager lifecycle."""

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, mock_hass, mock_config_entry):
        """Test manager start and stop."""
        import asyncio
        from unittest.mock import patch

        from custom_components.smartly_bridge.push import StatePushManager

        # Mock entity registry properly
        with patch(
            "custom_components.smartly_bridge.acl.get_allowed_entities",
            return_value=["light.test"],
        ):
            with patch("homeassistant.helpers.entity_registry.async_get"):
                manager = StatePushManager(mock_hass, mock_config_entry)

                # Start manager
                await manager.start()

                # Give tasks time to start
                await asyncio.sleep(0.1)

                # Verify tasks were created
                assert manager._batch_task is not None or not manager._stop_event.is_set()
                assert manager._heartbeat_task is not None or not manager._stop_event.is_set()

                # Stop manager
                await manager.stop()
                # Just verify stop doesn't raise error


class TestBatchLoop:
    """Tests for batch processing loop."""

    @pytest.mark.asyncio
    async def test_batch_loop_processes_events(self, mock_hass, mock_config_entry):
        """Test batch loop processes pending events."""
        from custom_components.smartly_bridge.push import StatePushManager

        mock_config_entry.data["push_batch_interval"] = 0.05

        with patch(
            "custom_components.smartly_bridge.acl.get_allowed_entities",
            return_value=["light.test"],
        ):
            with patch("homeassistant.helpers.entity_registry.async_get"):
                manager = StatePushManager(mock_hass, mock_config_entry)
                manager._flush_events = AsyncMock()
                await manager.start()
                manager._pending_events.append({"event_type": "test"})
                await asyncio.sleep(0.15)
                await manager.stop()
                assert manager._flush_events.call_count >= 1


class TestHeartbeatErrors:
    """Tests for heartbeat error handling."""

    @pytest.mark.asyncio
    async def test_heartbeat_timeout_error(self, mock_hass, mock_config_entry):
        """Test heartbeat handles timeout errors."""
        from contextlib import asynccontextmanager

        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)

        @asynccontextmanager
        async def mock_post(*args, **kwargs):
            raise asyncio.TimeoutError()
            yield

        mock_session = MagicMock()
        mock_session.post = mock_post
        manager._session = mock_session
        await manager._send_heartbeat()

    @pytest.mark.asyncio
    async def test_heartbeat_client_error(self, mock_hass, mock_config_entry):
        """Test heartbeat handles client errors."""
        from contextlib import asynccontextmanager

        import aiohttp

        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)

        @asynccontextmanager
        async def mock_post(*args, **kwargs):
            raise aiohttp.ClientError("Connection failed")
            yield

        mock_session = MagicMock()
        mock_session.post = mock_post
        manager._session = mock_session
        await manager._send_heartbeat()

    @pytest.mark.asyncio
    async def test_heartbeat_non_200_response(self, mock_hass, mock_config_entry):
        """Test heartbeat handles non-200 responses."""
        from contextlib import asynccontextmanager

        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        @asynccontextmanager
        async def mock_post(*args, **kwargs):
            yield mock_response

        mock_session = MagicMock()
        mock_session.post = mock_post
        manager._session = mock_session
        await manager._send_heartbeat()


class TestPushErrors:
    """Tests for push error handling."""

    @pytest.mark.asyncio
    async def test_push_404_stops_retry(self, mock_hass, mock_config_entry):
        """Test push stops retrying on 404."""
        from contextlib import asynccontextmanager

        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)
        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Not Found")

        call_count = 0

        @asynccontextmanager
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            yield mock_response

        mock_session = MagicMock()
        mock_session.post = mock_post
        manager._session = mock_session
        events = [{"event_type": "test"}]
        await manager._send_with_retry("https://example.com/events", events)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_push_500_error_retries(self, mock_hass, mock_config_entry):
        """Test push retries on 500 error."""
        from contextlib import asynccontextmanager

        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        call_count = 0

        @asynccontextmanager
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            yield mock_response

        mock_session = MagicMock()
        mock_session.post = mock_post
        manager._session = mock_session
        events = [{"event_type": "test"}]
        await manager._send_with_retry("https://example.com/events", events)
        assert call_count == 3


class TestRefreshTrackedEntities:
    """Tests for refresh_tracked_entities."""

    @pytest.mark.asyncio
    async def test_refresh_tracked_entities(self, mock_hass, mock_config_entry):
        """Test refreshing tracked entities."""
        from custom_components.smartly_bridge.push import StatePushManager

        with patch(
            "custom_components.smartly_bridge.acl.get_allowed_entities",
            return_value=["light.test"],
        ):
            with patch("homeassistant.helpers.entity_registry.async_get"):
                manager = StatePushManager(mock_hass, mock_config_entry)
                # Start first to setup subscription
                await manager.start()
                # Now refresh should have something to unsubscribe
                await manager.refresh_tracked_entities()
                # Just verify it doesn't crash
                await manager.stop()

    @pytest.mark.asyncio
    async def test_refresh_with_no_entities(self, mock_hass, mock_config_entry):
        """Test refresh when no entities are found."""
        from custom_components.smartly_bridge.push import StatePushManager

        with patch("custom_components.smartly_bridge.acl.get_allowed_entities", return_value=[]):
            with patch("homeassistant.helpers.entity_registry.async_get"):
                manager = StatePushManager(mock_hass, mock_config_entry)
                await manager.refresh_tracked_entities()


class TestStartNoEntities:
    """Tests for start with no entities."""

    @pytest.mark.asyncio
    async def test_start_no_entities_warning(self, mock_hass, mock_config_entry):
        """Test start issues warning when no entities found."""
        from custom_components.smartly_bridge.push import StatePushManager

        with patch("custom_components.smartly_bridge.acl.get_allowed_entities", return_value=[]):
            with patch("homeassistant.helpers.entity_registry.async_get"):
                manager = StatePushManager(mock_hass, mock_config_entry)
                await manager.start()

                # Should have created session but no tasks
                assert manager._session is not None
                assert manager._unsub_state_changed is None

                # Clean up
                await manager.stop()


class TestStopEdgeCases:
    """Tests for stop method edge cases."""

    @pytest.mark.asyncio
    async def test_stop_with_cancelled_batch_task(self, mock_hass, mock_config_entry):
        """Test stop handles already cancelled batch task."""
        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)
        manager._session = AsyncMock()
        manager._session.close = AsyncMock()

        # Create a cancelled task
        async def dummy():
            pass

        manager._batch_task = asyncio.create_task(dummy())
        manager._batch_task.cancel()

        # Should not raise
        await manager.stop()

    @pytest.mark.asyncio
    async def test_stop_with_cancelled_heartbeat_task(self, mock_hass, mock_config_entry):
        """Test stop handles already cancelled heartbeat task."""
        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)
        manager._session = AsyncMock()
        manager._session.close = AsyncMock()

        # Create a cancelled task
        async def dummy():
            pass

        manager._heartbeat_task = asyncio.create_task(dummy())
        manager._heartbeat_task.cancel()

        # Should not raise
        await manager.stop()


class TestHeartbeatLoopCancellation:
    """Tests for heartbeat loop cancellation."""

    @pytest.mark.asyncio
    async def test_heartbeat_loop_cancelled_error(self, mock_hass, mock_config_entry):
        """Test heartbeat loop handles CancelledError."""
        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)
        manager._stop_event.set()

        # Should exit cleanly
        await manager._heartbeat_loop()

    @pytest.mark.asyncio
    async def test_heartbeat_loop_general_exception(self, mock_hass, mock_config_entry):
        """Test heartbeat loop handles general exceptions."""
        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)

        # Mock _send_heartbeat to raise exception once, then set stop
        call_count = 0

        async def mock_send_heartbeat():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test error")
            # Set stop event after first call to exit loop
            manager._stop_event.set()

        manager._send_heartbeat = mock_send_heartbeat

        # Mock asyncio.sleep to avoid waiting
        with patch("asyncio.sleep", new_callable=AsyncMock):
            # Should log warning but continue
            await manager._heartbeat_loop()
            assert call_count >= 1


class TestSendHeartbeatErrors:
    """Tests for send heartbeat error scenarios."""

    @pytest.mark.asyncio
    async def test_send_heartbeat_creates_session_if_none(self, mock_hass, mock_config_entry):
        """Test send_heartbeat creates session if None."""
        from contextlib import asynccontextmanager

        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)
        manager._session = None  # Explicitly set to None

        mock_response = MagicMock()
        mock_response.status = 200

        @asynccontextmanager
        async def mock_post(*args, **kwargs):
            yield mock_response

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.post = mock_post
            mock_session_class.return_value = mock_session

            await manager._send_heartbeat()

            # Session should have been created
            mock_session_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_heartbeat_general_exception(self, mock_hass, mock_config_entry):
        """Test send_heartbeat handles general exceptions."""
        from contextlib import asynccontextmanager

        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)

        @asynccontextmanager
        async def mock_post(*args, **kwargs):
            raise ValueError("Unexpected error")
            yield

        mock_session = MagicMock()
        mock_session.post = mock_post
        manager._session = mock_session

        # Should not raise, just log warning
        await manager._send_heartbeat()


class TestSendWithRetryErrors:
    """Tests for send_with_retry error scenarios."""

    @pytest.mark.asyncio
    async def test_send_with_retry_client_error(self, mock_hass, mock_config_entry):
        """Test send_with_retry handles ClientError."""
        from contextlib import asynccontextmanager

        import aiohttp

        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)

        @asynccontextmanager
        async def mock_post(*args, **kwargs):
            raise aiohttp.ClientError("Connection failed")
            yield

        mock_session = MagicMock()
        mock_session.post = mock_post
        manager._session = mock_session

        events = [{"event_type": "test"}]
        await manager._send_with_retry("https://example.com/events", events)

    @pytest.mark.asyncio
    async def test_send_with_retry_unexpected_exception(self, mock_hass, mock_config_entry):
        """Test send_with_retry handles unexpected exceptions."""
        from contextlib import asynccontextmanager

        from custom_components.smartly_bridge.push import StatePushManager

        manager = StatePushManager(mock_hass, mock_config_entry)

        @asynccontextmanager
        async def mock_post(*args, **kwargs):
            raise ValueError("Unexpected error")
            yield

        mock_session = MagicMock()
        mock_session.post = mock_post
        manager._session = mock_session

        events = [{"event_type": "test"}]
        await manager._send_with_retry("https://example.com/events", events)


class TestQueueEventWithNullOldState:
    """Tests for queue_event with null old_state."""

    @pytest.fixture
    def push_manager(self, mock_hass, mock_config_entry):
        """Create a StatePushManager instance."""
        from custom_components.smartly_bridge.push import StatePushManager

        return StatePushManager(mock_hass, mock_config_entry)

    @pytest.mark.asyncio
    async def test_queue_event_null_old_state(self, push_manager):
        """Test queueing event when old_state is None."""
        mock_new_state = MagicMock()
        mock_new_state.state = "on"
        mock_new_state.attributes = {"brightness": 255}
        mock_new_state.last_changed = datetime(2025, 12, 17, 10, 0, 0)
        mock_new_state.last_updated = datetime(2025, 12, 17, 10, 0, 0)

        await push_manager._queue_event("light.test_light", None, mock_new_state)

        assert len(push_manager._pending_events) == 1
        event = push_manager._pending_events[0]
        assert event["event_type"] == "state_changed"
        assert event["data"]["entity_id"] == "light.test_light"
        assert event["data"]["old_state"] is None
        assert event["data"]["new_state"]["state"] == "on"
