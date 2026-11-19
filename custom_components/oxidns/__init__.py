"""OxiDNS integration setup and teardown."""

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OxiDNSClient
from .const import CONF_RECORDER_TAG, CONF_SCHEME
from .coordinator import OxiDNSCoordinator
from .event_stream import EventStream

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass, entry):
    data = entry.data
    client = OxiDNSClient(
        async_get_clientsession(hass),
        data[CONF_HOST],
        data[CONF_PORT],
        data[CONF_SCHEME],
        data.get(CONF_USERNAME, ""),
        data.get(CONF_PASSWORD, ""),
    )
    coordinator = OxiDNSCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()
    stream = EventStream(hass, client, data[CONF_RECORDER_TAG], entry.entry_id) if data.get(CONF_RECORDER_TAG) else None
    entry.runtime_data = (coordinator, stream)
    if stream:
        stream.task = entry.async_create_background_task(hass, stream.run(), "oxidns stream")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        stream = entry.runtime_data[1]
        if stream and stream.task:
            stream.task.cancel()
        return True
    return False
