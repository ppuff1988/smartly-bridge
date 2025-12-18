"""Config flow for Smartly Bridge integration."""
from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ALLOWED_CIDRS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_INSTANCE_ID,
    CONF_PUSH_BATCH_INTERVAL,
    CONF_WEBHOOK_URL,
    DEFAULT_PUSH_BATCH_INTERVAL,
    DOMAIN,
)


def generate_client_id() -> str:
    """Generate a unique client ID."""
    return f"ha_{secrets.token_urlsafe(16)}"


def generate_client_secret() -> str:
    """Generate a secure client secret."""
    return secrets.token_urlsafe(32)


class SmartlyBridgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smartly Bridge."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate CIDR format if provided
            if user_input.get(CONF_ALLOWED_CIDRS):
                cidrs = user_input[CONF_ALLOWED_CIDRS]
                if not self._validate_cidrs(cidrs):
                    errors[CONF_ALLOWED_CIDRS] = "invalid_cidr"

            # Validate webhook URL
            webhook_url = user_input.get(CONF_WEBHOOK_URL, "")
            if webhook_url and not webhook_url.startswith(("http://", "https://")):
                errors[CONF_WEBHOOK_URL] = "invalid_url"

            if not errors:
                # Generate credentials
                client_id = generate_client_id()
                client_secret = generate_client_secret()

                # Create config entry
                return self.async_create_entry(
                    title=f"Smartly Bridge ({user_input[CONF_INSTANCE_ID]})",
                    data={
                        CONF_INSTANCE_ID: user_input[CONF_INSTANCE_ID],
                        CONF_CLIENT_ID: client_id,
                        CONF_CLIENT_SECRET: client_secret,
                        CONF_WEBHOOK_URL: user_input.get(CONF_WEBHOOK_URL, ""),
                        CONF_ALLOWED_CIDRS: user_input.get(CONF_ALLOWED_CIDRS, ""),
                        CONF_PUSH_BATCH_INTERVAL: user_input.get(
                            CONF_PUSH_BATCH_INTERVAL, DEFAULT_PUSH_BATCH_INTERVAL
                        ),
                    },
                )

        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INSTANCE_ID): str,
                    vol.Optional(CONF_WEBHOOK_URL, default=""): str,
                    vol.Optional(CONF_ALLOWED_CIDRS, default=""): str,
                    vol.Optional(
                        CONF_PUSH_BATCH_INTERVAL,
                        default=DEFAULT_PUSH_BATCH_INTERVAL,
                    ): vol.Coerce(float),
                }
            ),
            errors=errors,
        )

    def _validate_cidrs(self, cidrs_str: str) -> bool:
        """Validate CIDR format."""
        import ipaddress

        if not cidrs_str.strip():
            return True

        cidrs = [c.strip() for c in cidrs_str.split(",") if c.strip()]
        for cidr in cidrs:
            try:
                ipaddress.ip_network(cidr, strict=False)
            except ValueError:
                return False
        return True

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SmartlyBridgeOptionsFlow:
        """Get the options flow for this handler."""
        return SmartlyBridgeOptionsFlow()


class SmartlyBridgeOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Smartly Bridge."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate CIDR format if provided
            if user_input.get(CONF_ALLOWED_CIDRS):
                cidrs = user_input[CONF_ALLOWED_CIDRS]
                if not self._validate_cidrs(cidrs):
                    errors[CONF_ALLOWED_CIDRS] = "invalid_cidr"

            # Validate webhook URL
            webhook_url = user_input.get(CONF_WEBHOOK_URL, "")
            if webhook_url and not webhook_url.startswith(("http://", "https://")):
                errors[CONF_WEBHOOK_URL] = "invalid_url"

            if not errors:
                # Update config entry data
                new_data = {**self.config_entry.data, **user_input}
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                return self.async_create_entry(title="", data={})

        # Current values
        current_webhook = self.config_entry.data.get(CONF_WEBHOOK_URL, "")
        current_cidrs = self.config_entry.data.get(CONF_ALLOWED_CIDRS, "")
        current_batch = self.config_entry.data.get(
            CONF_PUSH_BATCH_INTERVAL, DEFAULT_PUSH_BATCH_INTERVAL
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_WEBHOOK_URL, default=current_webhook): str,
                    vol.Optional(CONF_ALLOWED_CIDRS, default=current_cidrs): str,
                    vol.Optional(CONF_PUSH_BATCH_INTERVAL, default=current_batch): vol.Coerce(float),
                }
            ),
            errors=errors,
            description_placeholders={
                "client_id": self.config_entry.data.get(CONF_CLIENT_ID, ""),
                "client_secret": self.config_entry.data.get(CONF_CLIENT_SECRET, ""),
            },
        )

    def _validate_cidrs(self, cidrs_str: str) -> bool:
        """Validate CIDR format."""
        import ipaddress

        if not cidrs_str.strip():
            return True

        cidrs = [c.strip() for c in cidrs_str.split(",") if c.strip()]
        for cidr in cidrs:
            try:
                ipaddress.ip_network(cidr, strict=False)
            except ValueError:
                return False
        return True
