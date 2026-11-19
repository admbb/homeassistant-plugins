"""Diagnostics expose only non-sensitive capability status."""


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator, stream = entry.runtime_data
    return {
        "online": coordinator.data.get("online"),
        "ready": coordinator.data.get("ready"),
        "version": (coordinator.data.get("health") or {}).get("version"),
        "recorder_configured": bool(stream),
        "stream_connected": bool(stream and stream.connected),
        "stats_available": {key: value is not None for key, value in coordinator.data.get("stats", {}).items()},
    }
