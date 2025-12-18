"""Tests for config flow module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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
    DOMAIN,
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
