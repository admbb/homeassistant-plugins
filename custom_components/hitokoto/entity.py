"""Shared base entity for Hitokoto Daily sensors."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import HitokotoCoordinator


class HitokotoEntity(CoordinatorEntity[HitokotoCoordinator]):
    """Base class that groups entities under one device per config entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HitokotoCoordinator, entry_id: str) -> None:
        """Initialize the entity and its device information."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer=MANUFACTURER,
            name=NAME,
        )
