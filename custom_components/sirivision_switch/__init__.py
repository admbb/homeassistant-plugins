"""Sirivision SR-S25G3412F Switch integration for Home Assistant."""

from __future__ import annotations

import logging
import os
import shutil

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_PORT_ALIASES,
    CONF_PORT_IFINDEX_MAP,
    DOMAIN,
    FRONTEND_JS_FILENAME,
    FRONTEND_RESOURCE_URL,
    PLATFORMS,
)
from .coordinator import SirivisionSwitchCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_SERVICE_SET_PORT_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Required("physical_port"): cv.string,
        vol.Optional("alias"): vol.Any(None, cv.string),
        vol.Optional("if_index"): vol.Any(None, vol.Coerce(int)),
    }
)


async def _async_install_frontend(hass: HomeAssistant) -> None:
    """Copy bundled Lovelace card JS to /config/www/sirivision_switch/."""

    def _copy() -> None:
        src = hass.config.path("custom_components", DOMAIN, "frontend", FRONTEND_JS_FILENAME)
        dst_dir = hass.config.path("www", DOMAIN)
        dst = os.path.join(dst_dir, FRONTEND_JS_FILENAME)
        if not os.path.exists(src):
            return
        os.makedirs(dst_dir, exist_ok=True)
        shutil.copy2(src, dst)

    await hass.async_add_executor_job(_copy)


async def _async_register_resource(hass: HomeAssistant) -> None:
    """Ensure the Lovelace module resource is registered once in storage mode."""
    lovelace = hass.data.get("lovelace")
    if not lovelace or not getattr(lovelace, "resources", None):
        return
    resources = lovelace.resources
    if not getattr(resources, "loaded", True):
        await resources.async_load()
    existing = [
        item for item in resources.async_items()
        if str(item.get("url", "")).split("?")[0].endswith(f"/{FRONTEND_JS_FILENAME}")
    ]
    if existing or not hasattr(resources, "async_create_item"):
        return
    try:
        await resources.async_create_item({"res_type": "module", "url": FRONTEND_RESOURCE_URL})
    except (HomeAssistantError, KeyError, ValueError) as err:
        _LOGGER.debug("Unable to auto-register Lovelace resource %s: %s", FRONTEND_RESOURCE_URL, err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sirivision SR-S25G3412F from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    try:
        await _async_install_frontend(hass)
        await _async_register_resource(hass)
    except OSError as err:
        _LOGGER.warning("Unable to install the optional Sirivision dashboard card: %s", err)

    coordinator = SirivisionSwitchCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, "set_port_config"):
        async def _handle_set_port_config(call: ServiceCall) -> None:
            entry_id = call.data["entry_id"]
            phys_port = call.data["physical_port"]
            target_entry = hass.config_entries.async_get_entry(entry_id)
            if not target_entry or target_entry.domain != DOMAIN:
                raise HomeAssistantError(f"Unknown sirivision_switch entry_id: {entry_id}")
            new_opts = dict(target_entry.options)
            aliases = dict(new_opts.get(CONF_PORT_ALIASES, {}))
            if_map = dict(new_opts.get(CONF_PORT_IFINDEX_MAP, {}))
            if "alias" in call.data:
                val = (call.data["alias"] or "").strip()
                if val:
                    aliases[phys_port] = val
                else:
                    aliases.pop(phys_port, None)
                new_opts[CONF_PORT_ALIASES] = aliases
            if "if_index" in call.data:
                idx = call.data["if_index"]
                if idx is not None and int(idx) > 0:
                    if_map[phys_port] = int(idx)
                else:
                    if_map.pop(phys_port, None)
                new_opts[CONF_PORT_IFINDEX_MAP] = if_map
            hass.config_entries.async_update_entry(target_entry, options=new_opts)

        hass.services.async_register(
            DOMAIN,
            "set_port_config",
            _handle_set_port_config,
            schema=_SERVICE_SET_PORT_CONFIG_SCHEMA,
        )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
