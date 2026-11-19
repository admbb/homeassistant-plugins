"""Tests for entity values and metadata."""

from __future__ import annotations

from dataclasses import replace

from custom_components.hitokoto.sensor import SENSORS, HitokotoSensor


def test_daily_sensor_attributes(coordinator, sample_quote):
    """The main sensor exposes official metadata and favorite state."""
    coordinator.data = coordinator._make_data(
        quote=sample_quote, status="normal", error=None
    )
    entity = HitokotoSensor(coordinator, "entry-one", SENSORS[0])
    assert entity.native_value == sample_quote.text
    assert entity.extra_state_attributes["uuid"] == sample_quote.uuid
    assert entity.extra_state_attributes["source_url"] == sample_quote.source_url
    assert entity.extra_state_attributes["is_favorite"] is False


def test_status_sensor_stays_available_without_quote(coordinator):
    """The status sensor remains readable even without a cached sentence."""
    coordinator.data.quote = None
    coordinator.data.status = "unavailable"
    entity = HitokotoSensor(coordinator, "entry-one", SENSORS[-1])
    assert entity.available
    assert entity.native_value == "unavailable"


def test_primary_sensor_unavailable_without_quote(coordinator):
    """The daily quote sensor is unavailable until a usable sentence exists."""
    coordinator.data.quote = None
    entity = HitokotoSensor(coordinator, "entry-one", SENSORS[0])
    assert not entity.available
    assert entity.native_value is None


def test_author_and_source_have_friendly_empty_values(coordinator, sample_quote):
    """Missing API metadata does not surface as unknown in the helper sensors."""
    quote = replace(sample_quote, author=None, source=None)
    coordinator.data = coordinator._make_data(quote=quote, status="normal", error=None)
    author = HitokotoSensor(coordinator, "entry-one", SENSORS[1])
    source = HitokotoSensor(coordinator, "entry-one", SENSORS[2])
    assert author.native_value == "佚名"
    assert source.native_value == "未标注"
