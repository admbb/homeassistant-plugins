"""Config flow and Options flow for Sirivision SR-S25G3412F Switch."""

from __future__ import annotations

import json
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_COMMUNITY,
    CONF_DEVICE_NAME,
    CONF_HOST,
    CONF_POLL_DEVICE_INFO,
    CONF_POLL_STATUS,
    CONF_POLL_TRAFFIC,
    CONF_POLL_VLAN_MAC,
    CONF_PORT_ALIASES,
    CONF_PORT_IFINDEX_MAP,
    CONF_SNMP_PORT,
    CONF_SNMP_VERSION,
    DEFAULT_NAME,
    DEFAULT_POLL_DEVICE_INFO,
    DEFAULT_POLL_STATUS,
    DEFAULT_POLL_TRAFFIC,
    DEFAULT_POLL_VLAN_MAC,
    DEFAULT_SNMP_PORT,
    DEFAULT_SNMP_VERSION,
    DOMAIN,
    OID_SYS_DESCR,
    OID_SYS_NAME,
)
from .snmp_client import SirivisionSnmpClient

_LOGGER = logging.getLogger(__name__)


class SirivisionSwitchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Sirivision SR-S25G3412F."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_SNMP_PORT])
            community = user_input[CONF_COMMUNITY].strip()
            version = user_input[CONF_SNMP_VERSION]
            device_name = user_input[CONF_DEVICE_NAME].strip() or DEFAULT_NAME

            await self.async_set_unique_id(f"sirivision_{host.lower()}_{port}")
            self._abort_if_unique_id_configured()

            client = SirivisionSnmpClient(
                hass=self.hass,
                host=host,
                port=port,
                community=community,
                snmp_version=version,
                timeout=3.0,
                retries=1,
            )
            try:
                scalars = await client.get_scalars([OID_SYS_DESCR, OID_SYS_NAME])
                if not scalars:
                    errors["base"] = "cannot_connect"
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("SNMP connection test failed for %s:%s (%s)", host, port, err)
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(
                    title=device_name,
                    data={
                        CONF_HOST: host,
                        CONF_SNMP_PORT: port,
                        CONF_COMMUNITY: community,
                        CONF_SNMP_VERSION: version,
                        CONF_DEVICE_NAME: device_name,
                    },
                    options={
                        CONF_POLL_TRAFFIC: DEFAULT_POLL_TRAFFIC,
                        CONF_POLL_STATUS: DEFAULT_POLL_STATUS,
                        CONF_POLL_VLAN_MAC: DEFAULT_POLL_VLAN_MAC,
                        CONF_POLL_DEVICE_INFO: DEFAULT_POLL_DEVICE_INFO,
                        CONF_PORT_ALIASES: {},
                        CONF_PORT_IFINDEX_MAP: {},
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_SNMP_PORT, default=DEFAULT_SNMP_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Required(CONF_COMMUNITY): str,
                vol.Required(CONF_SNMP_VERSION, default=DEFAULT_SNMP_VERSION): vol.In({"v2c": "SNMP v2c", "v1": "SNMP v1"}),
                vol.Required(CONF_DEVICE_NAME, default=DEFAULT_NAME): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SirivisionSwitchOptionsFlow:
        return SirivisionSwitchOptionsFlow(config_entry)


class SirivisionSwitchOptionsFlow(config_entries.OptionsFlow):
    """Manage Sirivision Switch options (polling intervals, port aliases, ifIndex mapping)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        current = self._entry.options

        if user_input is not None:
            try:
                aliases_obj = json.loads(user_input.get("port_aliases_json") or "{}")
                if not isinstance(aliases_obj, dict):
                    raise ValueError("port_aliases_json must be a JSON object")
                map_obj = json.loads(user_input.get("port_ifindex_json") or "{}")
                if not isinstance(map_obj, dict):
                    raise ValueError("port_ifindex_json must be a JSON object")
                clean_map = {str(k): int(v) for k, v in map_obj.items() if v is not None}
                clean_aliases = {str(k): str(v) for k, v in aliases_obj.items() if v is not None}
            except Exception:  # noqa: BLE001
                errors["base"] = "invalid_json"
            else:
                new_opts = {
                    **current,
                    CONF_DEVICE_NAME: user_input[CONF_DEVICE_NAME].strip() or DEFAULT_NAME,
                    CONF_HOST: user_input[CONF_HOST].strip(),
                    CONF_POLL_TRAFFIC: int(user_input[CONF_POLL_TRAFFIC]),
                    CONF_POLL_STATUS: int(user_input[CONF_POLL_STATUS]),
                    CONF_POLL_VLAN_MAC: int(user_input[CONF_POLL_VLAN_MAC]),
                    CONF_POLL_DEVICE_INFO: int(user_input[CONF_POLL_DEVICE_INFO]),
                    CONF_PORT_ALIASES: clean_aliases,
                    CONF_PORT_IFINDEX_MAP: clean_map,
                }
                return self.async_create_entry(title="", data=new_opts)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEVICE_NAME,
                    default=current.get(CONF_DEVICE_NAME, self._entry.data.get(CONF_DEVICE_NAME, DEFAULT_NAME)),
                ): str,
                vol.Required(
                    CONF_HOST,
                    default=current.get(CONF_HOST, self._entry.data.get(CONF_HOST, "")),
                ): str,
                vol.Required(
                    CONF_POLL_TRAFFIC,
                    default=current.get(CONF_POLL_TRAFFIC, DEFAULT_POLL_TRAFFIC),
                ): vol.All(vol.Coerce(int), vol.Range(min=3, max=300)),
                vol.Required(
                    CONF_POLL_STATUS,
                    default=current.get(CONF_POLL_STATUS, DEFAULT_POLL_STATUS),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=600)),
                vol.Required(
                    CONF_POLL_VLAN_MAC,
                    default=current.get(CONF_POLL_VLAN_MAC, DEFAULT_POLL_VLAN_MAC),
                ): vol.All(vol.Coerce(int), vol.Range(min=15, max=1800)),
                vol.Required(
                    CONF_POLL_DEVICE_INFO,
                    default=current.get(CONF_POLL_DEVICE_INFO, DEFAULT_POLL_DEVICE_INFO),
                ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
                vol.Optional(
                    "port_aliases_json",
                    default=json.dumps(current.get(CONF_PORT_ALIASES, {}), ensure_ascii=False),
                ): str,
                vol.Optional(
                    "port_ifindex_json",
                    default=json.dumps(current.get(CONF_PORT_IFINDEX_MAP, {}), ensure_ascii=False),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
