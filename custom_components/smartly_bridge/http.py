"""HTTP API endpoints for Smartly Bridge."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .acl import (
    get_allowed_entities,
    get_entity_domain,
    get_structure,
    is_entity_allowed,
    is_service_allowed,
)
from .audit import log_control, log_deny
from .auth import RateLimiter, verify_request
from .const import (
    API_PATH_CONTROL,
    API_PATH_SYNC,
    API_PATH_SYNC_STATES,
    CONF_ALLOWED_CIDRS,
    CONF_CLIENT_SECRET,
    DOMAIN,
    RATE_WINDOW,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# 基礎配置：attribute/device_class -> decimal places
NUMERIC_PRECISION_CONFIG = {
    "voltage": 2,  # 電壓：220.12V
    "current": 3,  # 電流：0.456A (預設安培)
    "power": 2,  # 功率：100.99W
    "energy": 2,  # 能量：1.23kWh
    "active_power": 2,  # 有效功率：100.99W
    "reactive_power": 2,  # 無效功率：50.12VAR
    "apparent_power": 2,  # 視在功率：111.80VA
    "power_factor": 3,  # 功率因數：0.905
    "frequency": 2,  # 頻率：50.00Hz
    "temperature": 1,  # 溫度：25.5°C
    "humidity": 1,  # 濕度：65.5%
    "battery": 0,  # 電池：85%
    "illuminance": 0,  # 照度：500lx
    "pressure": 1,  # 氣壓：1013.2hPa
    "co2": 0,  # CO2：450ppm
    "pm25": 1,  # PM2.5：12.5
    "pm10": 1,  # PM10：25.5
}

# 根據單位調整小數點位數：(attribute/device_class, unit) -> decimal places
UNIT_SPECIFIC_PRECISION_CONFIG = {
    ("current", "mA"): 1,  # 毫安培：456.5mA
    ("current", "A"): 3,  # 安培：0.456A
    ("voltage", "mV"): 0,  # 毫伏特：1234mV
    ("voltage", "V"): 2,  # 伏特：220.12V
    ("power", "mW"): 0,  # 毫瓦：1234mW
    ("power", "W"): 2,  # 瓦特：100.99W
    ("power", "kW"): 3,  # 千瓦：1.234kW
    ("energy", "Wh"): 1,  # 瓦時：123.4Wh
    ("energy", "kWh"): 3,  # 千瓦時：1.234kWh
}


def get_decimal_places(key: str, unit: str = "") -> int | None:
    """Get decimal places for formatting based on attribute/device_class and unit.

    Args:
        key: Attribute name or device_class (e.g., 'voltage', 'current', 'power')
        unit: Unit of measurement (e.g., 'V', 'mA', 'W', 'kW')

    Returns:
        Number of decimal places, or None if no configuration found
    """
    # Check unit-specific config first
    if key and unit:
        if (key, unit) in UNIT_SPECIFIC_PRECISION_CONFIG:
            return UNIT_SPECIFIC_PRECISION_CONFIG[(key, unit)]

    # Fall back to base config
    if key in NUMERIC_PRECISION_CONFIG:
        return NUMERIC_PRECISION_CONFIG[key]

    return None


def format_numeric_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """Format numeric attributes with configurable decimal places.

    Formats common electrical measurements (voltage, current, power, etc.)
    with appropriate decimal places based on units for cleaner API responses.
    """
    unit = attributes.get("unit_of_measurement", "")

    formatted = attributes.copy()

    for attr in NUMERIC_PRECISION_CONFIG:
        if attr in formatted and isinstance(formatted[attr], (int, float)):
            try:
                decimal_places = get_decimal_places(attr, unit)
                if decimal_places is not None:
                    formatted[attr] = round(float(formatted[attr]), decimal_places)
            except (ValueError, TypeError):
                pass  # Keep original value if conversion fails

    return formatted


class SmartlyControlView(web.View):
    """Handle POST /api/smartly/control requests."""

    def __init__(self, request: web.Request) -> None:
        """Initialize the view."""
        super().__init__(request)
        self.hass: HomeAssistant = request.app["hass"]

    async def post(self) -> web.Response:
        """Handle control request from Platform."""
        # Get integration data
        data = self._get_integration_data()
        if data is None:
            return web.json_response(
                {"error": "integration_not_configured"},
                status=500,
            )

        client_secret = data.get(CONF_CLIENT_SECRET)
        allowed_cidrs = data.get(CONF_ALLOWED_CIDRS, "")
        nonce_cache = self.hass.data[DOMAIN]["nonce_cache"]
        rate_limiter: RateLimiter = self.hass.data[DOMAIN]["rate_limiter"]

        # Verify authentication
        auth_result = await verify_request(
            self.request,
            client_secret,
            nonce_cache,
            allowed_cidrs,
        )

        if not auth_result.success:
            log_deny(
                _LOGGER,
                client_id=self.request.headers.get("X-Client-Id", "unknown"),
                entity_id="",
                service="",
                reason=auth_result.error or "auth_failed",
            )
            return web.json_response(
                {"error": auth_result.error},
                status=401,
            )

        # Check rate limit
        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id="",
                service="",
                reason="rate_limited",
            )
            return web.json_response(
                {"error": "rate_limited"},
                status=429,
                headers={
                    "Retry-After": str(RATE_WINDOW),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Parse request body
        try:
            body = await self.request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"error": "invalid_json"},
                status=400,
            )

        entity_id = body.get("entity_id")
        action = body.get("action")
        service_data = body.get("service_data", {})
        actor = body.get("actor", {})

        if not entity_id or not action:
            return web.json_response(
                {"error": "missing_required_fields"},
                status=400,
            )

        # Get entity registry
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self.hass)

        # Check entity is allowed
        if not is_entity_allowed(self.hass, entity_id, entity_registry):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service=action,
                reason="entity_not_allowed",
                actor=actor,
            )
            return web.json_response(
                {"error": "entity_not_allowed"},
                status=403,
            )

        # Check service is allowed
        domain = get_entity_domain(entity_id)
        if not is_service_allowed(domain, action):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service=action,
                reason="service_not_allowed",
                actor=actor,
            )
            return web.json_response(
                {"error": "service_not_allowed"},
                status=403,
            )

        # Call the service
        try:
            # Prepare service data, excluding parameters that are not for the service itself
            # Remove any parameters that might be passed to async_call incorrectly
            service_call_data = {"entity_id": entity_id, **service_data}

            await self.hass.services.async_call(
                domain,
                action,
                service_call_data,
                blocking=True,
            )

            # Wait a short moment for state to propagate
            await asyncio.sleep(0.1)

            log_control(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service=action,
                result="success",
                actor=actor,
            )

            # Get new state after service call
            new_state = self.hass.states.get(entity_id)

            return web.json_response(
                {
                    "success": True,
                    "entity_id": entity_id,
                    "action": action,
                    "new_state": new_state.state if new_state else None,
                    "new_attributes": (
                        format_numeric_attributes(dict(new_state.attributes)) if new_state else None
                    ),
                },
                status=200,
            )

        except Exception as err:
            _LOGGER.error("Service call failed: %s", err)
            log_control(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id=entity_id,
                service=action,
                result=f"error: {type(err).__name__}",
                actor=actor,
            )
            return web.json_response(
                {"error": "service_call_failed"},
                status=500,
            )

    def _get_integration_data(self) -> dict[str, Any] | None:
        """Get integration config entry data."""
        if DOMAIN not in self.hass.data:
            return None

        config_entry = self.hass.data[DOMAIN].get("config_entry")
        if config_entry:
            return config_entry.data

        return None


class SmartlySyncView(web.View):
    """Handle GET /api/smartly/sync/structure requests."""

    def __init__(self, request: web.Request) -> None:
        """Initialize the view."""
        super().__init__(request)
        self.hass: HomeAssistant = request.app["hass"]

    async def get(self) -> web.Response:
        """Handle sync request from Platform."""
        # Get integration data
        data = self._get_integration_data()
        if data is None:
            return web.json_response(
                {"error": "integration_not_configured"},
                status=500,
            )

        client_secret = data.get(CONF_CLIENT_SECRET)
        allowed_cidrs = data.get(CONF_ALLOWED_CIDRS, "")
        nonce_cache = self.hass.data[DOMAIN]["nonce_cache"]
        rate_limiter: RateLimiter = self.hass.data[DOMAIN]["rate_limiter"]

        # Verify authentication
        auth_result = await verify_request(
            self.request,
            client_secret,
            nonce_cache,
            allowed_cidrs,
        )

        if not auth_result.success:
            log_deny(
                _LOGGER,
                client_id=self.request.headers.get("X-Client-Id", "unknown"),
                entity_id="",
                service="sync",
                reason=auth_result.error or "auth_failed",
            )
            return web.json_response(
                {"error": auth_result.error},
                status=401,
            )

        # Check rate limit
        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id="",
                service="sync",
                reason="rate_limited",
            )
            return web.json_response(
                {"error": "rate_limited"},
                status=429,
                headers={
                    "Retry-After": str(RATE_WINDOW),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Get registries
        from homeassistant.helpers import area_registry as ar
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er
        from homeassistant.helpers import floor_registry as fr

        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)
        area_registry = ar.async_get(self.hass)
        floor_registry = fr.async_get(self.hass)

        # Get allowed entities
        allowed_entities = get_allowed_entities(self.hass, entity_registry)

        # Build structure
        structure = get_structure(
            self.hass,
            allowed_entities,
            entity_registry,
            device_registry,
            area_registry,
            floor_registry,
        )

        return web.json_response(structure, status=200)

    def _get_integration_data(self) -> dict[str, Any] | None:
        """Get integration config entry data."""
        if DOMAIN not in self.hass.data:
            return None

        config_entry = self.hass.data[DOMAIN].get("config_entry")
        if config_entry:
            return config_entry.data

        return None


class SmartlySyncStatesView(web.View):
    """Handle GET /api/smartly/sync/states requests."""

    def __init__(self, request: web.Request) -> None:
        """Initialize the view."""
        super().__init__(request)
        self.hass: HomeAssistant = request.app["hass"]

    async def get(self) -> web.Response:
        """Handle sync states request from Platform."""
        # Get integration data
        data = self._get_integration_data()
        if data is None:
            return web.json_response(
                {"error": "integration_not_configured"},
                status=500,
            )

        client_secret = data.get(CONF_CLIENT_SECRET)
        allowed_cidrs = data.get(CONF_ALLOWED_CIDRS, "")
        nonce_cache = self.hass.data[DOMAIN]["nonce_cache"]
        rate_limiter: RateLimiter = self.hass.data[DOMAIN]["rate_limiter"]

        # Verify authentication
        auth_result = await verify_request(
            self.request,
            client_secret,
            nonce_cache,
            allowed_cidrs,
        )

        if not auth_result.success:
            log_deny(
                _LOGGER,
                client_id=self.request.headers.get("X-Client-Id", "unknown"),
                entity_id="",
                service="sync_states",
                reason=auth_result.error or "auth_failed",
            )
            return web.json_response(
                {"error": auth_result.error},
                status=401,
            )

        # Check rate limit
        if not await rate_limiter.check(auth_result.client_id or ""):
            log_deny(
                _LOGGER,
                client_id=auth_result.client_id or "unknown",
                entity_id="",
                service="sync_states",
                reason="rate_limited",
            )
            return web.json_response(
                {"error": "rate_limited"},
                status=429,
                headers={
                    "Retry-After": str(RATE_WINDOW),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Get entity registry
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self.hass)
        allowed_entities = get_allowed_entities(self.hass, entity_registry)

        # Build states list
        states = []
        for entity_id in allowed_entities:
            state = self.hass.states.get(entity_id)
            if state:
                states.append(
                    {
                        "entity_id": entity_id,
                        "state": state.state,
                        "attributes": format_numeric_attributes(dict(state.attributes)),
                        "last_changed": (
                            state.last_changed.isoformat() if state.last_changed else None
                        ),
                        "last_updated": (
                            state.last_updated.isoformat() if state.last_updated else None
                        ),
                    }
                )

        return web.json_response(
            {"states": states, "count": len(states)},
            status=200,
        )

    def _get_integration_data(self) -> dict[str, Any] | None:
        """Get integration config entry data."""
        if DOMAIN not in self.hass.data:
            return None

        config_entry = self.hass.data[DOMAIN].get("config_entry")
        if config_entry:
            return config_entry.data

        return None


def register_views(hass: HomeAssistant) -> None:
    """Register HTTP views."""
    hass.http.register_view(SmartlyControlViewWrapper)
    hass.http.register_view(SmartlySyncViewWrapper)
    hass.http.register_view(SmartlySyncStatesViewWrapper)


class SmartlyControlViewWrapper(HomeAssistantView):
    """Wrapper for SmartlyControlView to work with HA's view registration."""

    url = API_PATH_CONTROL
    name = "api:smartly:control"
    requires_auth = False  # We handle auth ourselves via HMAC

    async def post(self, request: web.Request) -> web.Response:
        """Handle POST request."""
        view = SmartlyControlView(request)
        return await view.post()


class SmartlySyncViewWrapper(HomeAssistantView):
    """Wrapper for SmartlySyncView to work with HA's view registration."""

    url = API_PATH_SYNC
    name = "api:smartly:sync"
    requires_auth = False  # We handle auth ourselves via HMAC

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request."""
        view = SmartlySyncView(request)
        return await view.get()


class SmartlySyncStatesViewWrapper(HomeAssistantView):
    """Wrapper for SmartlySyncStatesView to work with HA's view registration."""

    url = API_PATH_SYNC_STATES
    name = "api:smartly:sync:states"
    requires_auth = False  # We handle auth ourselves via HMAC

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request."""
        view = SmartlySyncStatesView(request)
        return await view.get()
