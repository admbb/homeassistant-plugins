"""Home Assistant integration for NetFlow Plus."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NetFlowClient
from .const import DOMAIN
from .coordinator import NetFlowCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass, entry) -> bool:
    """Set up a NetFlow Plus config entry."""
    client = NetFlowClient(async_get_clientsession(hass), entry.data)
    coordinator = NetFlowCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry) -> bool:
    """Unload a NetFlow Plus config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
