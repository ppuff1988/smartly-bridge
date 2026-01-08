"""Tests for Base View."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.smartly_bridge.const import DOMAIN
from custom_components.smartly_bridge.views.base import BaseView


class TestBaseView:
    """Tests for BaseView class."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "config_entry": MagicMock(
                    data={
                        "client_secret": "test_secret",
                        "allowed_cidrs": "192.168.1.0/24",
                    }
                ),
            }
        }
        return hass

    @pytest.fixture
    def mock_request(self, mock_hass):
        """Create mock request."""
        request = MagicMock()
        request.app = {"hass": mock_hass}
        return request

    def test_init(self, mock_request, mock_hass):
        """Test BaseView initialization."""
        view = BaseView(mock_request)
        assert view.request == mock_request
        assert view.hass == mock_hass

    def test_get_integration_data_success(self, mock_request, mock_hass):
        """Test getting integration data successfully."""
        view = BaseView(mock_request)
        data = view._get_integration_data()

        assert data is not None
        assert "client_secret" in data
        assert data["client_secret"] == "test_secret"

    def test_get_integration_data_no_domain(self, mock_request, mock_hass):
        """Test getting integration data when domain not in hass.data."""
        mock_hass.data = {}
        view = BaseView(mock_request)
        data = view._get_integration_data()

        assert data is None

    def test_get_integration_data_no_config_entry(self, mock_request, mock_hass):
        """Test getting integration data when config_entry is None."""
        mock_hass.data = {DOMAIN: {}}
        view = BaseView(mock_request)
        data = view._get_integration_data()

        assert data is None

    def test_get_client_secret_success(self, mock_request):
        """Test getting client secret successfully."""
        view = BaseView(mock_request)
        secret = view._get_client_secret()

        assert secret == "test_secret"

    def test_get_client_secret_no_data(self, mock_request, mock_hass):
        """Test getting client secret when no integration data."""
        mock_hass.data = {}
        view = BaseView(mock_request)
        secret = view._get_client_secret()

        assert secret is None

    def test_get_client_secret_no_secret_in_data(self, mock_request, mock_hass):
        """Test getting client secret when secret not in data."""
        mock_hass.data[DOMAIN]["config_entry"].data = {}
        view = BaseView(mock_request)
        secret = view._get_client_secret()

        assert secret is None
