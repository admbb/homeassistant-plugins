"""UI configuration and credential renewal."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers import aiohttp_client, selector

from .api import AuthenticationError, NotFound, OxiDNSClient, OxiDNSError, PermissionDenied
from .const import CONF_METRICS_TAG, CONF_RECORDER_TAG, CONF_SCHEME, DEFAULT_HOST, DEFAULT_PORT, DOMAIN


def schema(defaults):
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, DEFAULT_HOST)): vol.All(
                str, str.strip, vol.Length(min=1)
            ),
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required(CONF_SCHEME, default=defaults.get(CONF_SCHEME, "http")): vol.In(["http", "https"]),
            vol.Optional(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
            vol.Optional(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional(CONF_RECORDER_TAG, default=defaults.get(CONF_RECORDER_TAG, "")): str,
            vol.Optional(CONF_METRICS_TAG, default=defaults.get(CONF_METRICS_TAG, "")): str,
        }
    )


class OxiDNSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a single OxiDNS endpoint."""

    VERSION = 1

    async def _validate(self, data):
        client = OxiDNSClient(
            aiohttp_client.async_get_clientsession(self.hass),
            data[CONF_HOST],
            data[CONF_PORT],
            data[CONF_SCHEME],
            data.get(CONF_USERNAME, ""),
            data.get(CONF_PASSWORD, ""),
        )
        discovery = await client.discover()
        for key, kind in ((CONF_RECORDER_TAG, "query_recorder"), (CONF_METRICS_TAG, "metrics_collector")):
            if not data.get(key) and len(discovery["tags"][kind]) == 1:
                data[key] = discovery["tags"][kind][0]
        if data.get(CONF_RECORDER_TAG):
            try:
                await client.get(client.recorder_path(data[CONF_RECORDER_TAG], "records"), {"limit": 1})
            except NotFound:
                # A configured but inactive optional recorder must not block setup.
                pass
        return discovery

    async def _form(self, step, user_input, defaults):
        errors = {}
        if user_input is not None:
            try:
                await self._validate(user_input)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except PermissionDenied:
                errors["base"] = "forbidden"
            except NotFound:
                errors["base"] = "not_found"
            except (OxiDNSError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                if step == "user":
                    await self.async_set_unique_id(
                        f"{user_input[CONF_SCHEME]}://{user_input[CONF_HOST].lower()}:{user_input[CONF_PORT]}"
                    )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=f"OxiDNS {user_input[CONF_HOST]}", data=user_input)
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry() if step == "reconfigure" else self._get_reauth_entry(),
                    data=user_input,
                )
            defaults = user_input
        return self.async_show_form(step_id=step, data_schema=schema(defaults), errors=errors)

    async def async_step_user(self, user_input=None):
        return await self._form("user", user_input, {})

    async def async_step_reconfigure(self, user_input=None):
        return await self._form("reconfigure", user_input, self._get_reconfigure_entry().data)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._form("reauth_confirm", user_input, self._get_reauth_entry().data)
