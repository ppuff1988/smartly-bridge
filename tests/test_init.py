"""Tests for integration setup and teardown."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smartly_bridge.const import DOMAIN


class TestSetup:
    """Tests for async_setup and async_setup_entry."""

    @pytest.mark.asyncio
    async def test_async_setup(self, mock_hass):
        """Test async_setup returns True."""
        from custom_components.smartly_bridge import async_setup

        result = await async_setup(mock_hass, {})

        assert result is True

    @pytest.mark.asyncio
    async def test_async_setup_entry(self, mock_hass, mock_config_entry):
        """Test async_setup_entry initializes correctly."""
        from custom_components.smartly_bridge import async_setup_entry
        from custom_components.smartly_bridge.auth import NonceCache
        from custom_components.smartly_bridge.push import StatePushManager

        with (
            patch.object(NonceCache, "start", new_callable=AsyncMock),
            patch.object(StatePushManager, "start", new_callable=AsyncMock),
            patch("custom_components.smartly_bridge.register_views"),
        ):

            result = await async_setup_entry(mock_hass, mock_config_entry)

        assert result is True
        assert DOMAIN in mock_hass.data
        assert "config_entry" in mock_hass.data[DOMAIN]
        assert "nonce_cache" in mock_hass.data[DOMAIN]
        assert "rate_limiter" in mock_hass.data[DOMAIN]
        assert "push_manager" in mock_hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_async_setup_entry_registers_views(self, mock_hass, mock_config_entry):
        """Test async_setup_entry registers HTTP views."""
        from custom_components.smartly_bridge import async_setup_entry
        from custom_components.smartly_bridge.auth import NonceCache
        from custom_components.smartly_bridge.push import StatePushManager

        with (
            patch.object(NonceCache, "start", new_callable=AsyncMock),
            patch.object(StatePushManager, "start", new_callable=AsyncMock),
            patch("custom_components.smartly_bridge.register_views") as mock_register,
        ):

            await async_setup_entry(mock_hass, mock_config_entry)

        mock_register.assert_called_once_with(mock_hass)


class TestUnload:
    """Tests for async_unload_entry."""

    @pytest.mark.asyncio
    async def test_async_unload_entry(self, mock_hass, mock_config_entry):
        """Test async_unload_entry cleans up correctly."""
        from custom_components.smartly_bridge import async_unload_entry
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        from custom_components.smartly_bridge.push import StatePushManager

        # Setup mock data
        mock_nonce_cache = MagicMock(spec=NonceCache)
        mock_nonce_cache.stop = AsyncMock()

        mock_push_manager = MagicMock(spec=StatePushManager)
        mock_push_manager.stop = AsyncMock()

        mock_hass.data[DOMAIN] = {
            "config_entry": mock_config_entry,
            "nonce_cache": mock_nonce_cache,
            "rate_limiter": MagicMock(spec=RateLimiter),
            "push_manager": mock_push_manager,
        }

        result = await async_unload_entry(mock_hass, mock_config_entry)

        assert result is True
        mock_push_manager.stop.assert_called_once()
        mock_nonce_cache.stop.assert_called_once()
        assert DOMAIN not in mock_hass.data

    @pytest.mark.asyncio
    async def test_async_unload_entry_no_data(self, mock_hass, mock_config_entry):
        """Test async_unload_entry handles missing data."""
        from custom_components.smartly_bridge import async_unload_entry

        # Ensure DOMAIN not in hass.data
        mock_hass.data = {}

        result = await async_unload_entry(mock_hass, mock_config_entry)

        assert result is True


class TestOptionsUpdate:
    """Tests for async_update_options."""

    @pytest.mark.asyncio
    async def test_async_update_options(self, mock_hass, mock_config_entry):
        """Test async_update_options refreshes entities."""
        from custom_components.smartly_bridge import async_update_options
        from custom_components.smartly_bridge.push import StatePushManager

        mock_push_manager = MagicMock(spec=StatePushManager)
        mock_push_manager.refresh_tracked_entities = AsyncMock()

        mock_hass.data[DOMAIN] = {
            "push_manager": mock_push_manager,
        }

        await async_update_options(mock_hass, mock_config_entry)

        mock_push_manager.refresh_tracked_entities.assert_called_once()


class TestRemoveEntry:
    """Tests for async_remove_entry."""

    @pytest.mark.asyncio
    async def test_async_remove_entry(self, mock_hass, mock_config_entry):
        """Test async_remove_entry logs removal."""
        from custom_components.smartly_bridge import async_remove_entry

        with patch("custom_components.smartly_bridge.log_integration_event") as mock_log:
            await async_remove_entry(mock_hass, mock_config_entry)

        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert "remove" in call_args[0]
