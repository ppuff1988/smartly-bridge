"""Tests for config flow module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.smartly_bridge.config_flow import (
    SmartlyBridgeConfigFlow,
    generate_client_id,
    generate_client_secret,
)
from custom_components.smartly_bridge.const import (
    CONF_ALLOWED_CIDRS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_INSTANCE_ID,
    CONF_PUSH_BATCH_INTERVAL,
    CONF_WEBHOOK_URL,
)


class TestGenerateCredentials:
    """Tests for credential generation functions."""

    def test_generate_client_id_format(self):
        """Test client_id has correct format."""
        client_id = generate_client_id()

        assert client_id.startswith("ha_")
        assert len(client_id) > 10

    def test_generate_client_id_unique(self):
        """Test client_id is unique each time."""
        ids = [generate_client_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All unique

    def test_generate_client_secret_length(self):
        """Test client_secret has sufficient length."""
        secret = generate_client_secret()

        assert len(secret) >= 32  # At least 32 characters

    def test_generate_client_secret_unique(self):
        """Test client_secret is unique each time."""
        secrets = [generate_client_secret() for _ in range(100)]
        assert len(set(secrets)) == 100  # All unique


class TestConfigFlowValidation:
    """Tests for config flow validation."""

    def test_validate_cidrs_empty(self):
        """Test empty CIDR string is valid."""
        flow = SmartlyBridgeConfigFlow()

        assert flow._validate_cidrs("") is True
        assert flow._validate_cidrs("  ") is True

    def test_validate_cidrs_single_valid(self):
        """Test single valid CIDR."""
        flow = SmartlyBridgeConfigFlow()

        assert flow._validate_cidrs("10.0.0.0/8") is True
        assert flow._validate_cidrs("192.168.1.0/24") is True
        assert flow._validate_cidrs("172.16.0.0/12") is True

    def test_validate_cidrs_multiple_valid(self):
        """Test multiple valid CIDRs."""
        flow = SmartlyBridgeConfigFlow()

        assert flow._validate_cidrs("10.0.0.0/8,192.168.0.0/16") is True
        assert flow._validate_cidrs("10.0.0.0/8, 192.168.0.0/16, 172.16.0.0/12") is True

    def test_validate_cidrs_invalid(self):
        """Test invalid CIDR strings."""
        flow = SmartlyBridgeConfigFlow()

        assert flow._validate_cidrs("not_a_cidr") is False
        assert flow._validate_cidrs("10.0.0.0/33") is False  # Invalid prefix
        assert flow._validate_cidrs("256.0.0.0/8") is False  # Invalid IP
        assert flow._validate_cidrs("10.0.0.0/abc") is False  # Invalid prefix format


class TestConfigFlowSteps:
    """Tests for config flow steps."""

    @pytest.mark.asyncio
    async def test_step_user_show_form(self):
        """Test initial step shows form."""
        flow = SmartlyBridgeConfigFlow()
        flow.hass = MagicMock()

        result = await flow.async_step_user(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert CONF_INSTANCE_ID in result["data_schema"].schema

    @pytest.mark.asyncio
    async def test_step_user_invalid_cidr(self):
        """Test error on invalid CIDR."""
        flow = SmartlyBridgeConfigFlow()
        flow.hass = MagicMock()

        user_input = {
            CONF_INSTANCE_ID: "test_instance",
            CONF_WEBHOOK_URL: "https://example.com/webhook",
            CONF_ALLOWED_CIDRS: "invalid_cidr",
            CONF_PUSH_BATCH_INTERVAL: 0.5,
        }

        result = await flow.async_step_user(user_input=user_input)

        assert result["type"] == "form"
        assert CONF_ALLOWED_CIDRS in result["errors"]

    @pytest.mark.asyncio
    async def test_step_user_invalid_url(self):
        """Test error on invalid URL."""
        flow = SmartlyBridgeConfigFlow()
        flow.hass = MagicMock()

        user_input = {
            CONF_INSTANCE_ID: "test_instance",
            CONF_WEBHOOK_URL: "not_a_url",
            CONF_ALLOWED_CIDRS: "",
            CONF_PUSH_BATCH_INTERVAL: 0.5,
        }

        result = await flow.async_step_user(user_input=user_input)

        assert result["type"] == "form"
        assert CONF_WEBHOOK_URL in result["errors"]

    @pytest.mark.asyncio
    async def test_step_user_success(self):
        """Test successful config entry creation."""
        flow = SmartlyBridgeConfigFlow()
        flow.hass = MagicMock()

        user_input = {
            CONF_INSTANCE_ID: "test_instance",
            CONF_WEBHOOK_URL: "https://example.com/webhook",
            CONF_ALLOWED_CIDRS: "10.0.0.0/8",
            CONF_PUSH_BATCH_INTERVAL: 0.5,
        }

        result = await flow.async_step_user(user_input=user_input)

        assert result["type"] == "create_entry"
        assert result["title"] == "Smartly Bridge (test_instance)"
        assert CONF_CLIENT_ID in result["data"]
        assert CONF_CLIENT_SECRET in result["data"]
        assert result["data"][CONF_INSTANCE_ID] == "test_instance"

    @pytest.mark.asyncio
    async def test_step_user_empty_webhook_allowed(self):
        """Test empty webhook URL is allowed."""
        flow = SmartlyBridgeConfigFlow()
        flow.hass = MagicMock()

        user_input = {
            CONF_INSTANCE_ID: "test_instance",
            CONF_WEBHOOK_URL: "",
            CONF_ALLOWED_CIDRS: "",
            CONF_PUSH_BATCH_INTERVAL: 0.5,
        }

        result = await flow.async_step_user(user_input=user_input)

        assert result["type"] == "create_entry"


class TestOptionsFlow:
    """Tests for options flow."""

    @pytest.mark.asyncio
    async def test_async_get_options_flow(self):
        """Test getting options flow."""
        from homeassistant.config_entries import OptionsFlowWithConfigEntry

        from custom_components.smartly_bridge.config_flow import SmartlyBridgeOptionsFlow

        config_entry = MagicMock()
        config_entry.entry_id = "test_entry_id"

        # Patch OptionsFlowWithConfigEntry.__init__ to bypass report_usage
        def mock_init(self, config_entry):
            self.__dict__["_config_entry"] = config_entry

        with patch.object(OptionsFlowWithConfigEntry, "__init__", mock_init):
            options_flow = SmartlyBridgeConfigFlow.async_get_options_flow(config_entry)

            assert isinstance(options_flow, SmartlyBridgeOptionsFlow)

    @pytest.mark.asyncio
    async def test_options_step_init_show_form(self):
        """Test options flow initial step shows form."""
        from unittest.mock import PropertyMock

        from homeassistant.config_entries import OptionsFlowWithConfigEntry

        from custom_components.smartly_bridge.config_flow import SmartlyBridgeOptionsFlow

        mock_hass = MagicMock()
        mock_config_entry = MagicMock()
        mock_config_entry.entry_id = "test_entry_id"
        mock_config_entry.data = {
            CONF_WEBHOOK_URL: "https://example.com/webhook",
            CONF_ALLOWED_CIDRS: "10.0.0.0/8",
            CONF_PUSH_BATCH_INTERVAL: 1.0,
            CONF_CLIENT_ID: "test_client",
            CONF_CLIENT_SECRET: "test_secret",
        }

        # Patch OptionsFlowWithConfigEntry.__init__ to bypass report_usage
        def mock_init(self, config_entry):
            self.__dict__["_config_entry"] = config_entry

        with (
            patch.object(OptionsFlowWithConfigEntry, "__init__", mock_init),
            patch.object(
                SmartlyBridgeOptionsFlow,
                "config_entry",
                new_callable=PropertyMock,
                return_value=mock_config_entry,
            ),
        ):
            options_flow = SmartlyBridgeOptionsFlow(mock_config_entry)
            options_flow.hass = mock_hass

            result = await options_flow.async_step_init(user_input=None)

            assert result["type"] == "form"
            assert result["step_id"] == "init"
            assert "client_id" in result["description_placeholders"]
            assert "client_secret" in result["description_placeholders"]

    @pytest.mark.asyncio
    async def test_options_step_init_invalid_cidr(self):
        """Test options flow error on invalid CIDR."""
        from unittest.mock import PropertyMock

        from homeassistant.config_entries import OptionsFlowWithConfigEntry

        from custom_components.smartly_bridge.config_flow import SmartlyBridgeOptionsFlow

        mock_hass = MagicMock()
        mock_config_entry = MagicMock()
        mock_config_entry.entry_id = "test_entry_id"
        mock_config_entry.data = {
            CONF_WEBHOOK_URL: "https://example.com/webhook",
            CONF_ALLOWED_CIDRS: "10.0.0.0/8",
            CONF_PUSH_BATCH_INTERVAL: 1.0,
        }

        # Patch OptionsFlowWithConfigEntry.__init__ to bypass report_usage
        def mock_init(self, config_entry):
            self.__dict__["_config_entry"] = config_entry

        with (
            patch.object(OptionsFlowWithConfigEntry, "__init__", mock_init),
            patch.object(
                SmartlyBridgeOptionsFlow,
                "config_entry",
                new_callable=PropertyMock,
                return_value=mock_config_entry,
            ),
        ):
            options_flow = SmartlyBridgeOptionsFlow(mock_config_entry)
            options_flow.hass = mock_hass

            user_input = {
                CONF_WEBHOOK_URL: "https://example.com/webhook",
                CONF_ALLOWED_CIDRS: "invalid_cidr",
                CONF_PUSH_BATCH_INTERVAL: 1.0,
            }

            result = await options_flow.async_step_init(user_input=user_input)

            assert result["type"] == "form"
            assert CONF_ALLOWED_CIDRS in result["errors"]

    @pytest.mark.asyncio
    async def test_options_step_init_invalid_url(self):
        """Test options flow error on invalid URL."""
        from unittest.mock import PropertyMock

        from homeassistant.config_entries import OptionsFlowWithConfigEntry

        from custom_components.smartly_bridge.config_flow import SmartlyBridgeOptionsFlow

        mock_hass = MagicMock()
        mock_config_entry = MagicMock()
        mock_config_entry.entry_id = "test_entry_id"
        mock_config_entry.data = {
            CONF_WEBHOOK_URL: "https://example.com/webhook",
            CONF_ALLOWED_CIDRS: "10.0.0.0/8",
            CONF_PUSH_BATCH_INTERVAL: 1.0,
        }

        # Patch OptionsFlowWithConfigEntry.__init__ to bypass report_usage
        def mock_init(self, config_entry):
            self.__dict__["_config_entry"] = config_entry

        with (
            patch.object(OptionsFlowWithConfigEntry, "__init__", mock_init),
            patch.object(
                SmartlyBridgeOptionsFlow,
                "config_entry",
                new_callable=PropertyMock,
                return_value=mock_config_entry,
            ),
        ):
            options_flow = SmartlyBridgeOptionsFlow(mock_config_entry)
            options_flow.hass = mock_hass

            user_input = {
                CONF_WEBHOOK_URL: "not_a_url",
                CONF_ALLOWED_CIDRS: "10.0.0.0/8",
                CONF_PUSH_BATCH_INTERVAL: 1.0,
            }

            result = await options_flow.async_step_init(user_input=user_input)

            assert result["type"] == "form"
            assert CONF_WEBHOOK_URL in result["errors"]

    @pytest.mark.asyncio
    async def test_options_step_init_success(self):
        """Test successful options update."""
        from unittest.mock import PropertyMock

        from homeassistant.config_entries import OptionsFlowWithConfigEntry

        from custom_components.smartly_bridge.config_flow import SmartlyBridgeOptionsFlow

        mock_hass = MagicMock()
        mock_config_entry = MagicMock()
        mock_config_entry.entry_id = "test_entry_id"
        mock_config_entry.data = {
            CONF_INSTANCE_ID: "test_instance",
            CONF_CLIENT_ID: "test_client",
            CONF_CLIENT_SECRET: "test_secret",
            CONF_WEBHOOK_URL: "https://example.com/old",
            CONF_ALLOWED_CIDRS: "10.0.0.0/8",
            CONF_PUSH_BATCH_INTERVAL: 1.0,
        }

        # Patch OptionsFlowWithConfigEntry.__init__ to bypass report_usage
        def mock_init(self, config_entry):
            self.__dict__["_config_entry"] = config_entry

        with (
            patch.object(OptionsFlowWithConfigEntry, "__init__", mock_init),
            patch.object(
                SmartlyBridgeOptionsFlow,
                "config_entry",
                new_callable=PropertyMock,
                return_value=mock_config_entry,
            ),
        ):
            options_flow = SmartlyBridgeOptionsFlow(mock_config_entry)
            options_flow.hass = mock_hass

            user_input = {
                CONF_WEBHOOK_URL: "https://example.com/new",
                CONF_ALLOWED_CIDRS: "192.168.0.0/16",
                CONF_PUSH_BATCH_INTERVAL: 2.0,
            }

            result = await options_flow.async_step_init(user_input=user_input)

            assert result["type"] == "create_entry"
            mock_hass.config_entries.async_update_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_options_validate_cidrs(self):
        """Test options flow CIDR validation."""

        from homeassistant.config_entries import OptionsFlowWithConfigEntry

        from custom_components.smartly_bridge.config_flow import SmartlyBridgeOptionsFlow

        mock_config_entry = MagicMock()
        mock_config_entry.data = {}

        # Patch OptionsFlowWithConfigEntry.__init__ to bypass report_usage
        def mock_init(self, config_entry):
            object.__setattr__(self, "_config_entry", config_entry)

        with patch.object(OptionsFlowWithConfigEntry, "__init__", mock_init):
            options_flow = SmartlyBridgeOptionsFlow(mock_config_entry)
            options_flow.hass = MagicMock()

            # Valid cases
            assert options_flow._validate_cidrs("") is True
            assert options_flow._validate_cidrs("10.0.0.0/8") is True
            assert options_flow._validate_cidrs("10.0.0.0/8,192.168.0.0/16") is True

            # Invalid cases
            assert options_flow._validate_cidrs("invalid") is False
            assert options_flow._validate_cidrs("256.0.0.0/8") is False
