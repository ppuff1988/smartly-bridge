"""Tests for HTTP API endpoints."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from custom_components.smartly_bridge.const import (
    API_PATH_CONTROL,
    API_PATH_SYNC,
    DOMAIN,
    HEADER_CLIENT_ID,
    HEADER_NONCE,
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
)


class TestControlEndpoint:
    """Tests for /api/smartly/control endpoint."""

    @pytest.mark.asyncio
    async def test_control_missing_headers(self):
        """Test control endpoint rejects request without auth headers."""
        from custom_components.smartly_bridge.http import SmartlyControlView
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        
        # Create mock request without headers
        request = MagicMock()
        request.headers = {}
        request.method = "POST"
        request.path = API_PATH_CONTROL
        request.app = {"hass": MagicMock()}
        request.read = AsyncMock(return_value=b'{}')
        
        # Setup hass.data
        hass = request.app["hass"]
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(data={
                    "client_secret": "test_secret",
                    "allowed_cidrs": "",
                }),
                "nonce_cache": NonceCache(),
                "rate_limiter": RateLimiter(60, 60),
            }
        }
        
        view = SmartlyControlView(request)
        response = await view.post()
        
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_control_invalid_signature(self):
        """Test control endpoint rejects invalid signature."""
        from custom_components.smartly_bridge.http import SmartlyControlView
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        import time
        import uuid
        
        # Create mock request with invalid signature
        request = MagicMock()
        request.headers = {
            HEADER_CLIENT_ID: "test_client",
            HEADER_TIMESTAMP: str(int(time.time())),
            HEADER_NONCE: str(uuid.uuid4()),
            HEADER_SIGNATURE: "invalid_signature",
        }
        request.method = "POST"
        request.path = API_PATH_CONTROL
        request.app = {"hass": MagicMock()}
        request.read = AsyncMock(return_value=b'{}')
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        
        # Setup hass.data
        hass = request.app["hass"]
        nonce_cache = NonceCache()
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(data={
                    "client_secret": "test_secret",
                    "allowed_cidrs": "",
                }),
                "nonce_cache": nonce_cache,
                "rate_limiter": RateLimiter(60, 60),
            }
        }
        
        view = SmartlyControlView(request)
        response = await view.post()
        
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_control_rate_limited(self):
        """Test control endpoint enforces rate limiting."""
        from custom_components.smartly_bridge.http import SmartlyControlView
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        
        # Create rate limiter that's exhausted
        rate_limiter = RateLimiter(max_requests=0, window_seconds=60)
        
        # Create mock request
        request = MagicMock()
        request.headers = {
            HEADER_CLIENT_ID: "test_client",
            HEADER_TIMESTAMP: "0",
            HEADER_NONCE: "nonce",
            HEADER_SIGNATURE: "sig",
        }
        request.method = "POST"
        request.path = API_PATH_CONTROL
        request.app = {"hass": MagicMock()}
        request.read = AsyncMock(return_value=b'{}')
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        
        # Setup hass.data with mock that passes auth
        hass = request.app["hass"]
        nonce_cache = NonceCache()
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(data={
                    "client_secret": "test_secret",
                    "allowed_cidrs": "",
                }),
                "nonce_cache": nonce_cache,
                "rate_limiter": rate_limiter,
            }
        }
        
        # Mock verify_request to return success
        with patch("custom_components.smartly_bridge.http.verify_request") as mock_verify:
            mock_verify.return_value = MagicMock(
                success=True,
                client_id="test_client"
            )
            
            view = SmartlyControlView(request)
            response = await view.post()
        
        assert response.status == 429


class TestSyncEndpoint:
    """Tests for /api/smartly/sync/structure endpoint."""

    @pytest.mark.asyncio
    async def test_sync_returns_structure(self):
        """Test sync endpoint returns floor/area/device/entity structure."""
        from custom_components.smartly_bridge.http import SmartlySyncView
        from custom_components.smartly_bridge.auth import NonceCache, RateLimiter
        
        # Create mock request
        request = MagicMock()
        request.headers = {
            HEADER_CLIENT_ID: "test_client",
        }
        request.method = "GET"
        request.path = API_PATH_SYNC
        request.app = {"hass": MagicMock()}
        request.read = AsyncMock(return_value=b'')
        request.transport = MagicMock()
        request.transport.get_extra_info.return_value = ("192.168.1.1", 12345)
        
        # Setup hass.data
        hass = request.app["hass"]
        nonce_cache = NonceCache()
        rate_limiter = RateLimiter(60, 60)
        
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(data={
                    "client_secret": "test_secret",
                    "allowed_cidrs": "",
                }),
                "nonce_cache": nonce_cache,
                "rate_limiter": rate_limiter,
            }
        }
        
        # Mock verify_request and get_structure
        with patch("custom_components.smartly_bridge.http.verify_request") as mock_verify, \
             patch("custom_components.smartly_bridge.http.get_structure") as mock_structure:
            
            mock_verify.return_value = MagicMock(
                success=True,
                client_id="test_client"
            )
            mock_structure.return_value = {
                "floors": [
                    {
                        "id": "floor_1",
                        "name": "First Floor",
                        "areas": []
                    }
                ]
            }
            
            # Also mock the registry imports inside the get method
            with patch("homeassistant.helpers.entity_registry.async_get"), \
                 patch("homeassistant.helpers.device_registry.async_get"), \
                 patch("homeassistant.helpers.area_registry.async_get"), \
                 patch("homeassistant.helpers.floor_registry.async_get"):
                
                view = SmartlySyncView(request)
                response = await view.get()
        
        assert response.status == 200
        body = json.loads(response.body)
        assert "floors" in body


class TestApiPaths:
    """Tests for API path constants."""

    def test_control_path(self):
        """Test control API path."""
        assert API_PATH_CONTROL == "/api/smartly/control"

    def test_sync_path(self):
        """Test sync API path."""
        assert API_PATH_SYNC == "/api/smartly/sync/structure"


class TestViewRegistration:
    """Tests for HTTP view registration."""

    def test_register_views(self, mock_hass):
        """Test views are registered correctly."""
        from custom_components.smartly_bridge.http import register_views
        
        register_views(mock_hass)
        
        assert mock_hass.http.register_view.call_count == 2
