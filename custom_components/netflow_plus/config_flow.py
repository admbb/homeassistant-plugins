"""Config flow for NetFlow Plus."""

from __future__ import annotations

from urllib.parse import urlsplit

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.helpers import aiohttp_client, selector

from .api import AuthenticationError, NetFlowClient, NetFlowError, PermissionDenied
from .const import CONF_URL, DEFAULT_SCAN_INTERVAL, DEFAULT_URL, DOMAIN, MAX_SCAN_INTERVAL, MIN_SCAN_INTERVAL


def _schema(defaults: dict) -> vol.Schema:
    """Build the integration form."""
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=defaults.get(CONF_URL, DEFAULT_URL)): vol.All(
                str, str.strip, vol.Length(min=1)
            ),
            vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Required("scan_interval", default=defaults.get("scan_interval", DEFAULT_SCAN_INTERVAL)): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
            ),
        }
    )


def _normalize_url(value: str) -> str:
    """Validate and normalize a base URL."""
    parts = urlsplit(value.strip())
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Invalid base URL")
    return value.strip().rstrip("/")


class NetFlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a NetFlow Plus server."""

    VERSION = 1

    async def _submit(self, step: str, user_input: dict):
        errors = {}
        data = dict(user_input)
        try:
            data[CONF_URL] = _normalize_url(data[CONF_URL])
            client = NetFlowClient(aiohttp_client.async_get_clientsession(self.hass), data)
            await client.authenticate()
            status = await client.status()
            if not isinstance(status.get("engine"), dict):
                raise NetFlowError("Unsupported NetFlow Plus API")
        except AuthenticationError:
            errors["base"] = "invalid_auth"
        except PermissionDenied:
            errors["base"] = "forbidden"
        except (NetFlowError, ValueError):
            errors["base"] = "cannot_connect"
        else:
            if step == "user":
                await self.async_set_unique_id(data[CONF_URL].lower())
                self._abort_if_unique_id_configured()
                host = urlsplit(data[CONF_URL]).hostname
                return self.async_create_entry(title=f"NetFlow Plus ({host})", data=data)
            entry = self._get_reauth_entry() if step == "reauth_confirm" else self._get_reconfigure_entry()
            return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(step_id=step, data_schema=_schema(user_input), errors=errors)

    async def async_step_user(self, user_input=None):
        """Set up a new server."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=_schema({}))
        return await self._submit("user", user_input)

    async def async_step_reconfigure(self, user_input=None):
        """Reconfigure an existing server."""
        entry = self._get_reconfigure_entry()
        if user_input is None:
            return self.async_show_form(step_id="reconfigure", data_schema=_schema(entry.data))
        return await self._submit("reconfigure", user_input)

    async def async_step_reauth(self, entry_data):
        """Ask for the updated password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Validate and store an updated password."""
        entry = self._get_reauth_entry()
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm", data_schema=_schema(entry.data))
        return await self._submit("reauth_confirm", user_input)
