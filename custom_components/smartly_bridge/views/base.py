"""Base classes and utilities for HTTP API views."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..const import CONF_CLIENT_SECRET, DOMAIN

if TYPE_CHECKING:
    from aiohttp import web


class BaseView:
    """Base class for all Smartly Bridge views."""

    def __init__(self, request: web.Request) -> None:
        """Initialize the base view."""
        self.request = request
        self.hass = request.app["hass"]

    def _get_integration_data(self) -> dict[str, Any] | None:
        """Get integration config entry data."""
        if DOMAIN not in self.hass.data:
            return None

        config_entry = self.hass.data[DOMAIN].get("config_entry")
        if config_entry:
            return config_entry.data

        return None

    def _get_client_secret(self) -> str | None:
        """Get client secret from integration data."""
        data = self._get_integration_data()
        if data:
            return data.get(CONF_CLIENT_SECRET)
        return None
