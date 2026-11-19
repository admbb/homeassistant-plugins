"""Tests for the public integration action names and handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from custom_components.hitokoto import (
    SERVICE_ADD_FAVORITE,
    SERVICE_CLEAR_HISTORY,
    SERVICE_GET_FAVORITES,
    SERVICE_GET_HISTORY,
    SERVICE_REFRESH,
)
from custom_components.hitokoto.api import HitokotoApiClient
from custom_components.hitokoto.const import DOMAIN
from custom_components.hitokoto.coordinator import HitokotoCoordinator
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry


def test_public_service_names():
    """Core action names stay stable for README and dashboard users."""
    assert SERVICE_REFRESH == "refresh"
    assert SERVICE_CLEAR_HISTORY == "clear_history"
    assert SERVICE_GET_HISTORY == "get_history"
    assert SERVICE_GET_FAVORITES == "get_favorites"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_favorite_read_and_clear_actions(hass, sample_quote):
    """Actions persist favorites and require explicit history confirmation."""
    options = {
        "api_route": "global",
        "timeout": 5,
        "categories": ["d", "i", "k"],
        "min_length": 8,
        "max_length": 80,
        "auto_update": False,
        "save_history": True,
        "history_limit": 365,
        "enable_favorites": True,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=options)
    entry.add_to_hass(hass)

    with patch.object(
        HitokotoApiClient,
        "async_get_quote",
        new=AsyncMock(return_value=sample_quote),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(DOMAIN, SERVICE_ADD_FAVORITE, {}, blocking=True)
        favorites = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_FAVORITES,
            {},
            blocking=True,
            return_response=True,
        )
        assert favorites["favorites"][0]["uuid"] == sample_quote.uuid

        history = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_HISTORY,
            {},
            blocking=True,
            return_response=True,
        )
        assert history["history"][0]["text"] == sample_quote.text

        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN, SERVICE_CLEAR_HISTORY, {}, blocking=True
            )

        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_HISTORY,
            {"confirm": True},
            blocking=True,
        )
        coordinator: HitokotoCoordinator = entry.runtime_data
        assert coordinator.get_history() == []
        assert len(coordinator.get_favorites()) == 1
