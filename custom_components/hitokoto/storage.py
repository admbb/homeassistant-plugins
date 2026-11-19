"""Versioned local persistence for daily quotes, history, and favorites."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .api import Quote
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1


@dataclass(slots=True)
class PersistentData:
    """All integration data stored in one HA-managed JSON file."""

    daily_quote: Quote | None = None
    quote_date: str | None = None
    history: list[Quote] = field(default_factory=list)
    favorites: list[Quote] = field(default_factory=list)
    last_attempt_at: str | None = None


class HitokotoStorage:
    """Read and write versioned data using Home Assistant Store."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize per-config-entry storage."""
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_{entry_id}"
        )

    async def async_load(self) -> PersistentData:
        """Load data, accepting the first task-book schema for migration."""
        try:
            raw = await self._store.async_load()
        except Exception:  # Storage corruption must not prevent HA startup.
            _LOGGER.exception("Could not load Hitokoto Daily data; starting empty")
            return PersistentData()

        if not isinstance(raw, dict):
            return PersistentData()

        daily_raw = raw.get("daily_quote")
        daily = Quote.from_storage(daily_raw) if isinstance(daily_raw, dict) else None
        history = self._restore_list(raw.get("history", []))
        favorites = self._restore_list(raw.get("favorites", []))
        quote_date = raw.get("quote_date")
        last_attempt_at = raw.get("last_attempt_at")

        return PersistentData(
            daily_quote=daily,
            quote_date=quote_date if isinstance(quote_date, str) else None,
            history=history,
            favorites=favorites,
            last_attempt_at=(
                last_attempt_at if isinstance(last_attempt_at, str) else None
            ),
        )

    async def async_save(self, data: PersistentData) -> None:
        """Persist the complete state atomically through HA Store."""
        await self._store.async_save(
            {
                "schema_version": STORAGE_VERSION,
                "daily_quote": (
                    data.daily_quote.as_storage()
                    if data.daily_quote is not None
                    else None
                ),
                "quote_date": data.quote_date,
                "history": [quote.as_storage() for quote in data.history],
                "favorites": [quote.as_storage() for quote in data.favorites],
                "last_attempt_at": data.last_attempt_at,
            }
        )

    @staticmethod
    def _restore_list(value: Any) -> list[Quote]:
        """Return valid quote objects from a persisted list."""
        if not isinstance(value, list):
            return []
        restored: list[Quote] = []
        for item in value:
            if isinstance(item, dict):
                quote = Quote.from_storage(item)
                if quote is not None:
                    restored.append(quote)
        return restored
