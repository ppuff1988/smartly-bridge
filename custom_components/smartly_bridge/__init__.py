"""Smartly Bridge integration for Home Assistant."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .audit import log_integration_event
from .const import CONF_CLIENT_ID, CONF_INSTANCE_ID, DOMAIN, RATE_LIMIT, RATE_WINDOW

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .auth import NonceCache, RateLimiter
    from .camera import CameraManager
    from .push import StatePushManager
    from .webrtc import WebRTCTokenManager

_LOGGER = logging.getLogger(__name__)


def register_views(hass: HomeAssistant) -> None:
    """Register HTTP views without importing the HTTP layer at module load."""
    from .http import register_views as register_http_views

    register_http_views(hass)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Platform Bridge from YAML configuration.

    This integration only supports config flow, not YAML configuration.
    """
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Platform Bridge from a config entry."""
    from .auth import NonceCache, RateLimiter
    from .camera import CameraManager
    from .push import StatePushManager
    from .webrtc import WebRTCTokenManager

    log_integration_event(_LOGGER, "setup_start", f"instance={entry.data.get(CONF_INSTANCE_ID)}")

    # Initialize domain data
    hass.data.setdefault(DOMAIN, {})

    # Create nonce cache
    nonce_cache = NonceCache()
    await nonce_cache.start()

    # Create rate limiter
    rate_limiter = RateLimiter(max_requests=RATE_LIMIT, window_seconds=RATE_WINDOW)

    # Create push manager
    push_manager = StatePushManager(hass, entry)

    # Create camera manager
    camera_manager = CameraManager(hass)
    await camera_manager.start()

    # Create WebRTC token manager
    webrtc_manager = WebRTCTokenManager(hass)
    await webrtc_manager.start()

    # Store in hass.data
    hass.data[DOMAIN] = {
        "config_entry": entry,
        "nonce_cache": nonce_cache,
        "rate_limiter": rate_limiter,
        "push_manager": push_manager,
        "camera_manager": camera_manager,
        "webrtc_manager": webrtc_manager,
    }

    # Register HTTP views
    register_views(hass)

    # Start push manager
    await push_manager.start()

    # Register update listener for config entry changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    log_integration_event(
        _LOGGER,
        "setup_complete",
        f"instance={entry.data.get(CONF_INSTANCE_ID)}, client_id={entry.data.get(CONF_CLIENT_ID)}",
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    log_integration_event(_LOGGER, "unload_start", f"instance={entry.data.get(CONF_INSTANCE_ID)}")

    if DOMAIN not in hass.data:
        return True

    # Stop push manager
    push_manager = hass.data[DOMAIN].get("push_manager")
    if push_manager:
        await push_manager.stop()

    # Stop camera manager
    camera_manager = hass.data[DOMAIN].get("camera_manager")
    if camera_manager:
        await camera_manager.stop()

    # Stop WebRTC token manager
    webrtc_manager = hass.data[DOMAIN].get("webrtc_manager")
    if webrtc_manager:
        await webrtc_manager.stop()

    # Stop nonce cache cleanup
    nonce_cache = hass.data[DOMAIN].get("nonce_cache")
    if nonce_cache:
        await nonce_cache.stop()

    # Clear domain data
    hass.data.pop(DOMAIN, None)

    log_integration_event(
        _LOGGER, "unload_complete", f"instance={entry.data.get(CONF_INSTANCE_ID)}"
    )

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    log_integration_event(_LOGGER, "reload_start", f"instance={entry.data.get(CONF_INSTANCE_ID)}")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
    log_integration_event(
        _LOGGER, "reload_complete", f"instance={entry.data.get(CONF_INSTANCE_ID)}"
    )


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    log_integration_event(_LOGGER, "options_update", f"instance={entry.data.get(CONF_INSTANCE_ID)}")

    # Refresh tracked entities in push manager
    push_manager = hass.data[DOMAIN].get("push_manager")
    if push_manager:
        await push_manager.refresh_tracked_entities()


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    log_integration_event(
        _LOGGER,
        "remove",
        f"instance={entry.data.get(CONF_INSTANCE_ID)}, client_id={entry.data.get(CONF_CLIENT_ID)}",
    )
