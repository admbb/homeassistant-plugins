"""Tests for scheduling state transitions, history, and favorites."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from custom_components.hitokoto.const import DOMAIN, STATUS_NORMAL, STATUS_STALE
from custom_components.hitokoto.coordinator import (
    HitokotoCoordinator,
    RequestGate,
    RequestThrottled,
)
from custom_components.hitokoto.storage import PersistentData
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry


class MemoryStorage:
    """Small storage fake retaining the last saved snapshot."""

    def __init__(self):
        self.data = PersistentData()
        self.saves = 0

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.data = data
        self.saves += 1


def make_entry(hass, **overrides):
    options = {
        "api_route": "global",
        "timeout": 5,
        "categories": ["d", "i", "k"],
        "min_length": 8,
        "max_length": 80,
        "auto_update": False,
        **overrides,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=options)
    entry.add_to_hass(hass)
    return entry


async def test_startup_fetches_and_saves_once(hass, sample_quote):
    """An empty store fetches a quote and pushes it into coordinator data."""
    storage = MemoryStorage()
    coordinator = HitokotoCoordinator(hass, make_entry(hass), storage, RequestGate())
    coordinator.client.async_get_quote = AsyncMock(return_value=sample_quote)

    await coordinator.async_initialize()

    assert coordinator.data.quote == sample_quote
    assert coordinator.data.status == STATUS_NORMAL
    assert coordinator.persistent.quote_date == datetime.now().date().isoformat()
    assert coordinator.persistent.history == [sample_quote]
    assert storage.saves >= 2
    coordinator.async_shutdown()


async def test_same_day_cache_skips_api(hass, sample_quote):
    """A saved sentence for today is restored without another API request."""
    storage = MemoryStorage()
    storage.data = PersistentData(
        daily_quote=sample_quote,
        quote_date=datetime.now().date().isoformat(),
        history=[sample_quote],
    )
    coordinator = HitokotoCoordinator(hass, make_entry(hass), storage, RequestGate())
    coordinator.client.async_get_quote = AsyncMock()

    await coordinator.async_initialize()

    coordinator.client.async_get_quote.assert_not_called()
    assert coordinator.data.quote == sample_quote
    coordinator.async_shutdown()


async def test_failed_refresh_keeps_quote_and_marks_stale(hass, sample_quote):
    """A failed network refresh leaves the last usable sentence in place."""
    storage = MemoryStorage()
    storage.data = PersistentData(
        daily_quote=sample_quote,
        quote_date=datetime.now().date().isoformat(),
    )
    coordinator = HitokotoCoordinator(hass, make_entry(hass), storage, RequestGate())
    coordinator.client.async_get_quote = AsyncMock(side_effect=OSError("offline"))
    coordinator.enable_retries = False
    coordinator.data = coordinator._make_data(
        quote=sample_quote, status=STATUS_NORMAL, error=None
    )

    assert not await coordinator.async_refresh_quote(
        reason="manual", manual=True, force=True
    )
    assert coordinator.data.quote == sample_quote
    assert coordinator.data.status == STATUS_STALE
    coordinator.async_shutdown()


async def test_favorite_history_dedupe_and_clear(hass, sample_quote):
    """UUID deduplication, favorites, and clear-history isolation work."""
    storage = MemoryStorage()
    coordinator = HitokotoCoordinator(hass, make_entry(hass), storage, RequestGate())
    coordinator.persistent = PersistentData(
        daily_quote=sample_quote,
        quote_date=datetime.now().date().isoformat(),
        history=[sample_quote],
    )
    coordinator.data = coordinator._make_data(
        quote=sample_quote, status=STATUS_NORMAL, error=None
    )

    await coordinator.async_add_favorite()
    await coordinator.async_add_favorite()
    assert len(coordinator.get_favorites()) == 1
    await coordinator.async_clear_history()
    assert coordinator.get_history() == []
    assert len(coordinator.get_favorites()) == 1
    await coordinator.async_remove_favorite(sample_quote.uuid)
    assert coordinator.get_favorites() == []
    coordinator.async_shutdown()


async def test_request_gate_manual_cooldown(hass):
    """Manual retries inside five seconds are blocked before reaching the API."""
    gate = RequestGate()
    operation = AsyncMock(return_value=None)
    await gate.async_call(operation, manual=True)
    with pytest.raises(RequestThrottled):
        await gate.async_call(operation, manual=True)
    assert operation.await_count == 1


async def test_missing_local_uuid_raises(hass):
    """Favorite actions cannot fabricate a quote that is not stored locally."""
    coordinator = HitokotoCoordinator(
        hass, make_entry(hass), MemoryStorage(), RequestGate()
    )
    with pytest.raises(HomeAssistantError):
        await coordinator.async_add_favorite("missing")
    coordinator.async_shutdown()
