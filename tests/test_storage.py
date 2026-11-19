"""Tests for Home Assistant Store persistence."""

from __future__ import annotations

from custom_components.hitokoto.storage import HitokotoStorage, PersistentData


async def test_store_round_trip(hass, sample_quote):
    """Daily cache, history, favorites, and attempts survive a reload."""
    first = HitokotoStorage(hass, "entry-one")
    data = PersistentData(
        daily_quote=sample_quote,
        quote_date="2026-11-19",
        history=[sample_quote],
        favorites=[sample_quote],
        last_attempt_at=sample_quote.fetched_at,
    )
    await first.async_save(data)

    restored = await HitokotoStorage(hass, "entry-one").async_load()
    assert restored.daily_quote == sample_quote
    assert restored.quote_date == "2026-11-19"
    assert restored.history == [sample_quote]
    assert restored.favorites == [sample_quote]
    assert restored.last_attempt_at == sample_quote.fetched_at


async def test_corrupt_and_old_fields_recover(hass):
    """Invalid sentence rows are skipped rather than breaking setup."""
    storage = HitokotoStorage(hass, "entry-corrupt")
    await storage._store.async_save(
        {
            "daily_quote": {"hitokoto": "迁移的句子", "type": "i", "from_who": "作者"},
            "history": [{"hitokoto": "有效历史"}, {"hitokoto": "  "}],
            "favorites": "invalid",
            "quote_date": "2026-11-19",
        }
    )

    loaded = await storage.async_load()
    assert loaded.daily_quote is not None
    assert loaded.daily_quote.text == "迁移的句子"
    assert loaded.daily_quote.category_code == "i"
    assert len(loaded.history) == 1
    assert loaded.favorites == []
