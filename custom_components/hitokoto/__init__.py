"""Home Assistant integration for a daily Hitokoto sentence."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import HitokotoCoordinator, RequestGate
from .storage import HitokotoStorage

PLATFORM_LIST = [Platform.SENSOR]
SERVICE_REFRESH = "refresh"
SERVICE_ADD_FAVORITE = "add_favorite"
SERVICE_REMOVE_FAVORITE = "remove_favorite"
SERVICE_CLEAR_HISTORY = "clear_history"
SERVICE_GET_HISTORY = "get_history"
SERVICE_GET_FAVORITES = "get_favorites"

type HitokotoConfigEntry = ConfigEntry[HitokotoCoordinator]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the integration domain data."""
    hass.data.setdefault(
        DOMAIN, {"entries": {}, "gate": RequestGate(), "services": False}
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HitokotoConfigEntry) -> bool:
    """Set up a config entry without making network availability fatal."""
    runtime = hass.data.setdefault(
        DOMAIN, {"entries": {}, "gate": RequestGate(), "services": False}
    )
    coordinator = HitokotoCoordinator(
        hass=hass,
        entry=entry,
        storage=HitokotoStorage(hass, entry.entry_id),
        gate=runtime["gate"],
    )
    entry.runtime_data = coordinator
    runtime["entries"][entry.entry_id] = coordinator
    await coordinator.async_initialize()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORM_LIST)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HitokotoConfigEntry) -> bool:
    """Unload a config entry and cancel its timers."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORM_LIST)
    if not unloaded:
        return False

    entry.runtime_data.async_shutdown()
    runtime = hass.data.get(DOMAIN)
    if runtime is None:
        return True
    runtime["entries"].pop(entry.entry_id, None)
    runtime.get("apply_now", set()).discard(entry.entry_id)
    if not runtime["entries"]:
        _unregister_services(hass)
        hass.data.pop(DOMAIN, None)
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: HitokotoConfigEntry
) -> None:
    """Reload settings and optionally fetch a sentence after an options change."""
    runtime = hass.data.get(DOMAIN)
    apply_now = runtime is not None and entry.entry_id in runtime.get(
        "apply_now", set()
    )
    if apply_now:
        runtime["apply_now"].discard(entry.entry_id)

    await hass.config_entries.async_reload(entry.entry_id)
    if apply_now:
        coordinator = hass.data.get(DOMAIN, {}).get("entries", {}).get(entry.entry_id)
        if coordinator is not None:
            await coordinator.async_refresh_quote(
                reason="options", manual=True, force=True
            )


def _register_services(hass: HomeAssistant) -> None:
    """Register integration-wide actions once for all config entries."""
    runtime = hass.data[DOMAIN]
    if runtime["services"]:
        return

    async def target(call: ServiceCall) -> HitokotoCoordinator:
        """Resolve the requested entry or the only configured entry."""
        entries: dict[str, HitokotoCoordinator] = hass.data[DOMAIN]["entries"]
        entry_id = call.data.get("entry_id")
        if entry_id is not None:
            coordinator = entries.get(entry_id)
            if coordinator is None:
                raise ServiceValidationError(
                    f"No active Hitokoto Daily entry named {entry_id}"
                )
            return coordinator
        if len(entries) == 1:
            return next(iter(entries.values()))
        if not entries:
            raise ServiceValidationError("No active Hitokoto Daily entries")
        raise ServiceValidationError(
            "entry_id is required when multiple Hitokoto Daily entries are set up"
        )

    async def handle_refresh(call: ServiceCall) -> None:
        coordinator = await target(call)
        await coordinator.async_refresh_quote(reason="manual", manual=True, force=True)

    async def handle_add_favorite(call: ServiceCall) -> None:
        coordinator = await target(call)
        await coordinator.async_add_favorite(call.data.get("uuid"))

    async def handle_remove_favorite(call: ServiceCall) -> None:
        coordinator = await target(call)
        await coordinator.async_remove_favorite(call.data.get("uuid"))

    async def handle_clear_history(call: ServiceCall) -> None:
        if not call.data.get("confirm", False):
            raise ServiceValidationError("confirm must be true to clear history")
        coordinator = await target(call)
        await coordinator.async_clear_history()

    async def handle_get_history(call: ServiceCall) -> dict[str, Any]:
        coordinator = await target(call)
        return {"history": coordinator.get_history(call.data.get("limit"))}

    async def handle_get_favorites(call: ServiceCall) -> dict[str, Any]:
        coordinator = await target(call)
        return {"favorites": coordinator.get_favorites()}

    action_handlers: dict[str, tuple[Callable[..., Any], bool]] = {
        SERVICE_REFRESH: (handle_refresh, False),
        SERVICE_ADD_FAVORITE: (handle_add_favorite, False),
        SERVICE_REMOVE_FAVORITE: (handle_remove_favorite, False),
        SERVICE_CLEAR_HISTORY: (handle_clear_history, False),
        SERVICE_GET_HISTORY: (handle_get_history, True),
        SERVICE_GET_FAVORITES: (handle_get_favorites, True),
    }

    schemas = {
        SERVICE_REFRESH: vol.Schema({vol.Optional("entry_id"): cv.string}),
        SERVICE_ADD_FAVORITE: vol.Schema(
            {vol.Optional("entry_id"): cv.string, vol.Optional("uuid"): cv.string}
        ),
        SERVICE_REMOVE_FAVORITE: vol.Schema(
            {vol.Optional("entry_id"): cv.string, vol.Optional("uuid"): cv.string}
        ),
        SERVICE_CLEAR_HISTORY: vol.Schema(
            {
                vol.Optional("entry_id"): cv.string,
                vol.Required("confirm"): cv.boolean,
            }
        ),
        SERVICE_GET_HISTORY: vol.Schema(
            {
                vol.Optional("entry_id"): cv.string,
                vol.Optional("limit"): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        ),
        SERVICE_GET_FAVORITES: vol.Schema({vol.Optional("entry_id"): cv.string}),
    }
    for service, (handler, returns_response) in action_handlers.items():
        hass.services.async_register(
            DOMAIN,
            service,
            handler,
            schema=schemas[service],
            supports_response=(
                SupportsResponse.ONLY if returns_response else SupportsResponse.NONE
            ),
        )
    runtime["services"] = True


def _unregister_services(hass: HomeAssistant) -> None:
    """Remove integration actions when the last entry unloads."""
    for service in (
        SERVICE_REFRESH,
        SERVICE_ADD_FAVORITE,
        SERVICE_REMOVE_FAVORITE,
        SERVICE_CLEAR_HISTORY,
        SERVICE_GET_HISTORY,
        SERVICE_GET_FAVORITES,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
