"""Sensors provided by NetFlow Plus."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


def _status(data: dict) -> dict:
    return data.get("status") or {}


def _engine(data: dict) -> dict:
    return _status(data).get("engine") or {}


def _rows(data: dict) -> list[dict]:
    rows = (data.get("ranking") or {}).get("items") or []
    return [row for row in rows[:10] if isinstance(row, dict)]


def _app_name(row: dict) -> str | None:
    for key in ("app", "name", "label", "domain"):
        value = row.get(key)
        if value:
            return str(value)
    return None


@dataclass(frozen=True, kw_only=True)
class NetFlowSensorDescription(SensorEntityDescription):
    """Describe a NetFlow Plus sensor."""

    value: Callable[[dict], object]
    attributes: Callable[[dict], dict] | None = None
    optional: bool = False


SENSORS: tuple[NetFlowSensorDescription, ...] = (
    NetFlowSensorDescription(
        key="engine_status",
        translation_key="engine_status",
        icon="mdi:lan-check",
        value=lambda data: (
            _status(data).get("mode")
            or _engine(data).get("mode")
            or _engine(data).get("state")
            or "online"
        ),
        attributes=lambda data: {
            "engine": _engine(data),
            "version": _status(data).get("version"),
            "build": _status(data).get("build"),
        },
    ),
    NetFlowSensorDescription(
        key="export_age",
        translation_key="export_age",
        icon="mdi:timer-outline",
        native_unit_of_measurement="s",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: _engine(data).get("exportAge"),
        attributes=lambda data: {"mode": _status(data).get("mode")},
    ),
    NetFlowSensorDescription(
        key="ranked_app_count",
        translation_key="ranked_app_count",
        icon="mdi:format-list-numbered",
        value=lambda data: len(_rows(data)) if data.get("ranking") is not None else None,
        optional=True,
    ),
    NetFlowSensorDescription(
        key="top_application",
        translation_key="top_application",
        icon="mdi:application-cog-outline",
        value=lambda data: _app_name(_rows(data)[0]) if _rows(data) else None,
        attributes=lambda data: {"ranking": _rows(data)},
        optional=True,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up NetFlow Plus sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        NetFlowSensor(coordinator, entry, description)
        for description in SENSORS
    )


class NetFlowSensor(CoordinatorEntity, SensorEntity):
    """A read-only NetFlow Plus sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, description: NetFlowSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="NetFlow Plus",
            manufacturer="MikroTik Home NetFlow Plus",
            configuration_url=entry.data["url"],
        )

    @property
    def native_value(self):
        return self.entity_description.value(self.coordinator.data)

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return not self.entity_description.optional or self.coordinator.data.get("ranking") is not None

    @property
    def extra_state_attributes(self) -> dict | None:
        if self.entity_description.attributes is None:
            return None
        return self.entity_description.attributes(self.coordinator.data)
