"""Sensor entities for the active sentence and local library statistics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import STATUS_OPTIONS
from .coordinator import HitokotoCoordinator
from .entity import HitokotoEntity


@dataclass(frozen=True, kw_only=True, slots=True)
class HitokotoSensorDescription(SensorEntityDescription):
    """Describe one sensor backed by the coordinator."""

    value_key: str


SENSORS = (
    HitokotoSensorDescription(
        key="daily",
        translation_key="daily",
        icon="mdi:script-text-outline",
        value_key="daily",
    ),
    HitokotoSensorDescription(
        key="author",
        translation_key="author",
        icon="mdi:account-outline",
        value_key="author",
    ),
    HitokotoSensorDescription(
        key="source",
        translation_key="source",
        icon="mdi:book-open-page-variant-outline",
        value_key="source",
    ),
    HitokotoSensorDescription(
        key="category",
        translation_key="category",
        icon="mdi:shape-outline",
        value_key="category",
    ),
    HitokotoSensorDescription(
        key="last_updated",
        translation_key="last_updated",
        icon="mdi:clock-check-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_key="last_updated",
    ),
    HitokotoSensorDescription(
        key="favorites_count",
        translation_key="favorites_count",
        icon="mdi:heart-multiple-outline",
        value_key="favorites_count",
    ),
    HitokotoSensorDescription(
        key="history_count",
        translation_key="history_count",
        icon="mdi:history",
        value_key="history_count",
    ),
    HitokotoSensorDescription(
        key="status",
        translation_key="status",
        icon="mdi:check-circle-outline",
        device_class=SensorDeviceClass.ENUM,
        options=list(STATUS_OPTIONS),
        value_key="status",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create all sensor entities for a config entry."""
    coordinator: HitokotoCoordinator = entry.runtime_data
    async_add_entities(
        HitokotoSensor(coordinator, entry.entry_id, description)
        for description in SENSORS
    )


class HitokotoSensor(HitokotoEntity, SensorEntity):
    """A sensor whose value is read from the in-memory coordinator snapshot."""

    entity_description: HitokotoSensorDescription

    def __init__(
        self,
        coordinator: HitokotoCoordinator,
        entry_id: str,
        description: HitokotoSensorDescription,
    ) -> None:
        """Initialize a unique sensor for this config entry."""
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_entity_registry_enabled_default = True

    @property
    def suggested_object_id(self) -> str:
        """Keep the default entity IDs from the integration's documented API."""
        return f"hitokoto_{self.entity_description.key}"

    @property
    def native_value(self) -> str | int | datetime | None:
        """Return the sensor's current value."""
        key = self.entity_description.value_key
        quote = self.coordinator.data.quote
        if key == "daily":
            return quote.text if quote is not None else None
        if key == "author":
            return (quote.author or "佚名") if quote is not None else "佚名"
        if key == "source":
            return (quote.source or "未标注") if quote is not None else "未标注"
        if key == "category":
            return quote.category_name if quote is not None else None
        if key == "last_updated":
            return self.coordinator.last_updated_datetime
        if key == "favorites_count":
            return len(self.coordinator.persistent.favorites)
        if key == "history_count":
            return len(self.coordinator.persistent.history)
        if key == "status":
            return self.coordinator.data.status
        return None

    @property
    def available(self) -> bool:
        """Keep statistics and status sensors available without an API quote."""
        if self.entity_description.value_key == "daily":
            return self.coordinator.data.quote is not None
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose quote metadata on the primary sensor."""
        if self.entity_description.value_key != "daily":
            if self.entity_description.value_key == "status":
                return {"last_error": self.coordinator.data.error}
            return None
        quote = self.coordinator.data.quote
        if quote is None:
            return {"error": self.coordinator.data.error}
        return {
            "uuid": quote.uuid,
            "type": quote.category_code,
            "category": quote.category_name,
            "category_name": quote.category_name,
            "from": quote.source,
            "from_who": quote.author,
            "creator": quote.creator,
            "created_at": quote.created_at,
            "length": quote.length,
            "source_url": quote.source_url,
            "fetched_at": quote.fetched_at,
            "quote_date": self.coordinator.data.quote_date,
            "is_favorite": self.coordinator.is_favorite,
        }
