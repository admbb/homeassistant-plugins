"""Common fixtures for the custom integration tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from custom_components.hitokoto.api import Quote
from custom_components.hitokoto.const import DOMAIN
from custom_components.hitokoto.coordinator import HitokotoCoordinator, RequestGate
from custom_components.hitokoto.storage import PersistentData
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture
def sample_quote() -> Quote:
    """A representative quote based on the official API response schema."""
    return Quote(
        text="用代码表达言语的魅力，用代码书写山河的壮丽。",
        uuid="75a45fd4-4f2f-45eb-80cb-6f0a7bcdfaf2",
        category_code="f",
        source="一言开发者中心",
        author="一言",
        creator="DreamOne",
        created_at="1621833280",
        length=22,
        fetched_at=datetime.now(UTC).isoformat(),
    )


@pytest.fixture
def coordinator(hass):
    """A coordinator with in-memory storage for entity unit tests."""

    class MemoryStorage:
        def __init__(self):
            self.data = PersistentData()

        async def async_load(self):
            return self.data

        async def async_save(self, data):
            self.data = data

    entry = MockConfigEntry(domain=DOMAIN, data={"auto_update": False})
    entry.add_to_hass(hass)
    value = HitokotoCoordinator(hass, entry, MemoryStorage(), RequestGate())
    try:
        yield value
    finally:
        value.async_shutdown()
