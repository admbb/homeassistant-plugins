"""API connectivity and DNS readiness."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator, _ = entry.runtime_data
    async_add_entities(OxiDNSBinary(coordinator, entry, key) for key in ("api_online", "dns_ready"))


class OxiDNSBinary(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key):
        super().__init__(coordinator)
        self.key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name="OxiDNS", manufacturer="OxiDNS"
        )
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY if key == "api_online" else None

    @property
    def is_on(self):
        return self.coordinator.data.get("online" if self.key == "api_online" else "ready")
