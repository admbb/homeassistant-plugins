"""OxiDNS diagnostic and DNS sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SIGNAL_STREAM_UPDATED


def stat(data, key):
    return (data.get("stats") or {}).get(key) or {}


def metric(data, key):
    return (data.get("metrics") or {}).get(key)


def first(data, key):
    rows = stat(data, key).get("rows") or []
    return rows[0].get("key") if rows else None


def rcode(data, key):
    d = stat(data, "rcode")
    if not d:
        return None
    return next((row["count"] for row in d.get("rows", []) if str(row.get("key", "")).lower() == key), 0)


@dataclass(frozen=True, kw_only=True)
class Description(SensorEntityDescription):
    value: Callable
    source: str | None = None
    live: bool = False


DESCRIPTIONS = (
    Description(
        key="status", value=lambda d: (d.get("health") or {}).get("status"), entity_category=EntityCategory.DIAGNOSTIC
    ),
    Description(
        key="version", value=lambda d: (d.get("health") or {}).get("version"), entity_category=EntityCategory.DIAGNOSTIC
    ),
    Description(
        key="build",
        value=lambda d: (d.get("health") or {}).get("build_bundle"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    Description(
        key="queries_total", value=lambda d: metric(d, "query_total"), state_class=SensorStateClass.TOTAL_INCREASING
    ),
    Description(
        key="queries_per_second",
        value=lambda d: d.get("qps"),
        native_unit_of_measurement="queries/s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Description(
        key="queries_per_minute",
        value=lambda d: d["qps"] * 60 if d.get("qps") is not None else None,
        native_unit_of_measurement="queries/min",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Description(
        key="errors_total",
        value=lambda d: metric(d, "query_error_total"),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    Description(
        key="latency_avg",
        value=lambda d: stat(d, "latency").get("avg_ms"),
        source="latency",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Description(
        key="latency_p95",
        value=lambda d: stat(d, "latency").get("p95_ms"),
        source="latency",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Description(key="top_client", value=lambda d: first(d, "top_clients"), source="top_clients"),
    Description(key="top_domain", value=lambda d: first(d, "top_qnames"), source="top_qnames"),
    Description(
        key="nxdomain_count",
        value=lambda d: rcode(d, "nxdomain"),
        source="rcode",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Description(
        key="servfail_count",
        value=lambda d: rcode(d, "servfail"),
        source="rcode",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Description(key="query_type_distribution", value=lambda d: stat(d, "qtype").get("sample_size"), source="qtype"),
    Description(key="response_distribution", value=lambda d: stat(d, "rcode").get("sample_size"), source="rcode"),
    Description(key="last_query", value=lambda d: d.get("qname"), live=True, entity_registry_enabled_default=False),
    Description(
        key="last_client", value=lambda d: d.get("client_ip"), live=True, entity_registry_enabled_default=False
    ),
    Description(key="last_response", value=lambda d: d.get("rcode"), live=True, entity_registry_enabled_default=False),
    Description(
        key="last_latency",
        value=lambda d: d.get("elapsed_ms"),
        live=True,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator, stream = entry.runtime_data
    async_add_entities(OxiDNSSensor(coordinator, stream, entry, description) for description in DESCRIPTIONS)


class OxiDNSSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, stream, entry, description):
        super().__init__(coordinator)
        self.stream = stream
        self.entry_id = entry.entry_id
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name="OxiDNS", manufacturer="OxiDNS"
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if self.entity_description.live and self.stream:
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    SIGNAL_STREAM_UPDATED.format(self.entry_id),
                    self.async_write_ha_state,
                )
            )

    @property
    def native_value(self):
        data = self.coordinator.data
        if self.entity_description.live:
            data = self.stream.records[-1] if self.stream and self.stream.records else {}
        value = self.entity_description.value(data)
        return round(value, 3) if isinstance(value, float) else value

    @property
    def available(self):
        if not super().available or not self.coordinator.data.get("online"):
            return False
        if self.entity_description.live:
            return bool(self.stream and self.stream.connected and self.stream.records)
        if self.entity_description.source:
            return bool((self.coordinator.data.get("stats") or {}).get(self.entity_description.source))
        return self.native_value is not None

    @property
    def extra_state_attributes(self):
        if not self.entity_description.source:
            return None
        payload = stat(self.coordinator.data, self.entity_description.source)
        return {
            key: payload[key]
            for key in (
                "rows",
                "sample_size",
                "sample_truncated",
                "sample_since_ms",
                "sample_until_ms",
                "points",
            )
            if key in payload
        }
