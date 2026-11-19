"""Tests for visual initial setup and options validation."""

from __future__ import annotations

import pytest
from custom_components.hitokoto.config_flow import _options_schema, _validate_input
from custom_components.hitokoto.const import DEFAULT_CATEGORIES, DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry


def valid_input():
    return {
        "api_route": "global",
        "timeout": 10,
        "enable_retries": True,
        "categories": list(DEFAULT_CATEGORIES),
        "min_length": 8,
        "max_length": 80,
        "prefer_author": False,
        "prefer_source": False,
        "auto_update": True,
        "update_time": "00:05:00",
        "save_history": True,
        "history_limit": 365,
        "enable_favorites": True,
        "allow_duplicate_favorites": False,
    }


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_user_config_flow_creates_entry_without_network(hass):
    """The first-time visual setup does not require the API to be online."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_input()
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Hitokoto Daily"
    assert result["data"]["categories"] == list(DEFAULT_CATEGORIES)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_options_flow_updates_settings(hass):
    """Options can be changed without deleting the cached sentence."""
    entry = MockConfigEntry(domain=DOMAIN, data=valid_input())
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    options = valid_input()
    options["api_route"] = "international"
    options["apply_now"] = False
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=options
    )
    assert result["type"] == "create_entry"
    assert result["data"]["api_route"] == "international"


def test_schema_defaults_cover_all_options():
    """The visual schema presents defaults for all configured preferences."""
    schema = _options_schema({})
    assert len(schema.schema) == 14
    assert _validate_input(valid_input()) == {}


def test_invalid_length_and_empty_categories_are_reported():
    """Invalid API filters are rejected before creating an entry."""
    options = valid_input()
    options["min_length"] = 60
    options["max_length"] = 20
    assert _validate_input(options)["base"] == "invalid_length_range"
    options = valid_input()
    options["categories"] = []
    assert _validate_input(options)["base"] == "select_category"
