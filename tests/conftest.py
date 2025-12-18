"""Pytest configuration and fixtures for Smartly Bridge tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.http = MagicMock()
    hass.http.register_view = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = {
        "instance_id": "test_instance",
        "client_id": "ha_test_client_id",
        "client_secret": "test_secret_key_for_hmac_signing",
        "webhook_url": "https://platform.example.com/webhooks/ha-events",
        "allowed_cidrs": "10.0.0.0/8,192.168.0.0/16",
        "push_batch_interval": 0.5,
    }
    entry.entry_id = "test_entry_id"
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    entry.async_on_unload = MagicMock()
    return entry


@pytest.fixture
def mock_entity_registry():
    """Create a mock entity registry."""
    registry = MagicMock()

    # Create mock entity entries
    mock_entry_allowed = MagicMock()
    mock_entry_allowed.labels = {"smartly_control"}
    mock_entry_allowed.device_id = "device_1"
    mock_entry_allowed.area_id = "area_1"
    mock_entry_allowed.name = "Test Light"
    mock_entry_allowed.original_name = "Test Light Original"

    mock_entry_not_allowed = MagicMock()
    mock_entry_not_allowed.labels = set()
    mock_entry_not_allowed.device_id = "device_2"
    mock_entry_not_allowed.area_id = "area_2"
    mock_entry_not_allowed.name = "Hidden Light"

    registry.entities = {
        "light.test_light": mock_entry_allowed,
        "light.hidden_light": mock_entry_not_allowed,
        "switch.test_switch": mock_entry_allowed,
    }

    def async_get(entity_id):
        return registry.entities.get(entity_id)

    registry.async_get = async_get
    return registry


@pytest.fixture
def sample_hmac_headers():
    """Generate sample HMAC headers for testing."""
    import hashlib
    import hmac
    import time
    import uuid

    secret = "test_secret_key_for_hmac_signing"
    timestamp = str(int(time.time()))
    nonce = str(uuid.uuid4())
    method = "POST"
    path = "/api/smartly/control"
    body = b'{"entity_id": "light.test_light", "action": "turn_on"}'

    body_hash = hashlib.sha256(body).hexdigest()
    message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
    signature = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {
        "X-Client-Id": "ha_test_client_id",
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": signature,
    }
