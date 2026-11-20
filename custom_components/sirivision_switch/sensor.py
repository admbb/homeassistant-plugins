"""Sensor platform for Sirivision SR-S25G3412F Switch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfDataRate, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SirivisionSwitchCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sirivision Switch sensors."""
    coordinator: SirivisionSwitchCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        SirivisionSummarySensor(coordinator, entry),
        SirivisionAggregateSensor(
            coordinator, entry,
            key="total_rx_bps", suffix="total_rx", name="总接收速率",
            icon="mdi:download-network-outline", is_rate=True,
            unit=UnitOfDataRate.MEGABITS_PER_SECOND, device_class=SensorDeviceClass.DATA_RATE,
        ),
        SirivisionAggregateSensor(
            coordinator, entry,
            key="total_tx_bps", suffix="total_tx", name="总发送速率",
            icon="mdi:upload-network-outline", is_rate=True,
            unit=UnitOfDataRate.MEGABITS_PER_SECOND, device_class=SensorDeviceClass.DATA_RATE,
        ),
        SirivisionAggregateSensor(
            coordinator, entry,
            key="ports_up", suffix="ports_up", name="在线端口数",
            icon="mdi:ethernet", is_rate=False, unit="个", device_class=None,
        ),
        SirivisionAggregateSensor(
            coordinator, entry,
            key="uptime_seconds", suffix="uptime", name="运行时间",
            icon="mdi:clock-outline", is_rate=False,
            unit=UnitOfTime.SECONDS, device_class=SensorDeviceClass.DURATION,
        ),
        SirivisionAggregateSensor(
            coordinator, entry,
            key="mac_total", suffix="mac_count", name="MAC 表数量",
            icon="mdi:lan", is_rate=False, unit="条", device_class=None,
        ),
    ]

    ports = (coordinator.data or {}).get("ports", [])
    for port in ports:
        entities.append(SirivisionPortSensor(coordinator, entry, port["physical_port"], port["slot"]))

    async_add_entities(entities)


class _BaseSirivisionSensor(CoordinatorEntity[SirivisionSwitchCoordinator], SensorEntity):
    """Shared base entity grouped under one switch device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SirivisionSwitchCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        data = coordinator.data or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=coordinator.device_name,
            manufacturer="Sirivision (希力威视)",
            model=data.get("model") or "SR-S25G3412F",
            configuration_url=f"http://{coordinator.host}",
        )


class SirivisionSummarySensor(_BaseSirivisionSensor):
    """Primary hub sensor carrying structured 12-port, VLAN, MAC, and health snapshot."""

    _attr_name = "状态"
    _attr_icon = "mdi:switch"

    def __init__(self, coordinator: SirivisionSwitchCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str:
        data = self.coordinator.data or {}
        return "online" if data.get("snmp_connected") else "offline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        if not data:
            return {"snmp_connected": False}
        # Never include community or secrets
        return {
            "entry_id": self._entry.entry_id,
            "device_name": data.get("device_name"),
            "manufacturer": data.get("manufacturer"),
            "model": data.get("model"),
            "sys_name": data.get("sys_name"),
            "sys_descr": data.get("sys_descr"),
            "sys_object_id": data.get("sys_object_id"),
            "host": data.get("host"),
            "snmp_connected": bool(data.get("snmp_connected")),
            "last_success_at": data.get("last_success_at"),
            "last_error": data.get("last_error"),
            "uptime_seconds": data.get("uptime_seconds"),
            "counter_bits": data.get("counter_bits"),
            "ports_total": data.get("ports_total", 12),
            "ports_up": data.get("ports_up", 0),
            "ports_rj45_up": data.get("ports_rj45_up", 0),
            "ports_sfp_up": data.get("ports_sfp_up", 0),
            "total_rx_bps": data.get("total_rx_bps", 0.0),
            "total_tx_bps": data.get("total_tx_bps", 0.0),
            "rj45_rx_bps": data.get("rj45_rx_bps", 0.0),
            "rj45_tx_bps": data.get("rj45_tx_bps", 0.0),
            "sfp_rx_bps": data.get("sfp_rx_bps", 0.0),
            "sfp_tx_bps": data.get("sfp_tx_bps", 0.0),
            "vlans": data.get("vlans", []),
            "mac_total": data.get("mac_total", 0),
            "mac_entries": data.get("mac_entries", []),
            "ports": data.get("ports", []),
        }


class SirivisionAggregateSensor(_BaseSirivisionSensor):
    """Numeric switch-level metric sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: SirivisionSwitchCoordinator,
        entry: ConfigEntry,
        *,
        key: str,
        suffix: str,
        name: str,
        icon: str,
        is_rate: bool,
        unit: str | None,
        device_class: SensorDeviceClass | None,
    ) -> None:
        super().__init__(coordinator, entry)
        self._key = key
        self._is_rate = is_rate
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class

    @property
    def available(self) -> bool:
        data = self.coordinator.data or {}
        return super().available and bool(data.get("snmp_connected"))

    @property
    def native_value(self) -> float | int | None:
        data = self.coordinator.data or {}
        val = data.get(self._key)
        if val is None:
            return None
        if self._is_rate:
            return round(float(val) / 1_000_000.0, 3)
        return val


class SirivisionPortSensor(_BaseSirivisionSensor):
    """Per-port state & telemetry sensor (12 physical ports)."""

    def __init__(
        self,
        coordinator: SirivisionSwitchCoordinator,
        entry: ConfigEntry,
        physical_port: str,
        slot: int,
    ) -> None:
        super().__init__(coordinator, entry)
        self._physical_port = physical_port
        self._slot = slot
        self._attr_name = physical_port
        self._attr_unique_id = f"{entry.entry_id}_port_{physical_port.lower().replace('+', 'p').replace('-', '_')}"

    def _find_port(self) -> dict[str, Any]:
        for p in (self.coordinator.data or {}).get("ports", []):
            if p.get("physical_port") == self._physical_port:
                return p
        return {}

    @property
    def icon(self) -> str:
        port = self._find_port()
        return "mdi:ethernet" if port.get("connected") else "mdi:ethernet-cable-off"

    @property
    def native_value(self) -> str:
        data = self.coordinator.data or {}
        if not data.get("snmp_connected"):
            return "offline"
        port = self._find_port()
        if port.get("admin_status") == "down":
            return "admin_down"
        return str(port.get("oper_status") or "unknown")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        port = self._find_port()
        if not port:
            return {"physical_port": self._physical_port, "slot": self._slot}
        return dict(port)
