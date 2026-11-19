"""Tests for the asynchronous official API client."""

from __future__ import annotations

import aiohttp
import pytest
from custom_components.hitokoto.api import HitokotoApiClient, HitokotoApiError

API_URL = "https://v1.hitokoto.cn/"


@pytest.mark.parametrize("status", [403, 429, 500])
async def test_http_error(aioclient_mock, hass, status):
    """Non-success HTTP responses become a normalized API error."""
    aioclient_mock.get(API_URL, status=status)
    client = HitokotoApiClient(hass, "global", 5)
    with pytest.raises(HitokotoApiError):
        await client.async_get_quote(("d", "i", "k"))


async def test_valid_response_and_repeated_categories(
    aioclient_mock, hass, sample_quote
):
    """Parse metadata and send each selected category as its own query pair."""
    aioclient_mock.get(
        API_URL,
        json={
            "uuid": sample_quote.uuid,
            "hitokoto": sample_quote.text,
            "type": "f",
            "from": sample_quote.source,
            "from_who": sample_quote.author,
            "creator": sample_quote.creator,
            "created_at": sample_quote.created_at,
            "length": sample_quote.length,
        },
    )
    client = HitokotoApiClient(hass, "global", 5)
    result = await client.async_get_quote(("d", "i", "k"))

    assert result.text == sample_quote.text
    assert result.uuid == sample_quote.uuid
    assert result.category_code == "f"
    assert result.category_name == "网络"
    assert result.source_url == f"https://hitokoto.cn?uuid={sample_quote.uuid}"
    assert len(aioclient_mock.mock_calls) == 1
    request_url = aioclient_mock.mock_calls[0][1]
    assert request_url.query.getall("c") == ["d", "i", "k"]
    assert request_url.query["min_length"] == "8"
    assert request_url.query["max_length"] == "80"


async def test_non_json_response(aioclient_mock, hass):
    """Invalid JSON is handled as a recoverable API error."""
    aioclient_mock.get(
        API_URL, content="not-json", headers={"Content-Type": "application/json"}
    )
    client = HitokotoApiClient(hass, "global", 5)
    with pytest.raises(HitokotoApiError):
        await client.async_get_quote(("d",))


async def test_empty_sentence_is_rejected(aioclient_mock, hass):
    """An empty API sentence cannot replace the current daily quote."""
    aioclient_mock.get(API_URL, json={"hitokoto": "  ", "uuid": "abc"})
    client = HitokotoApiClient(hass, "global", 5)
    with pytest.raises(HitokotoApiError, match="no usable sentence"):
        await client.async_get_quote(("d",))


async def test_missing_metadata_and_uuid_are_supported(aioclient_mock, hass):
    """Optional fields remain absent instead of becoming unknown strings."""
    aioclient_mock.get(API_URL, json={"hitokoto": "一段诗句", "type": "z"})
    client = HitokotoApiClient(hass, "global", 5)
    quote = await client.async_get_quote(("i",))

    assert quote.uuid is None
    assert quote.author is None
    assert quote.source is None
    assert quote.category_code is None
    assert quote.source_url is None


async def test_timeout_is_normalized(aioclient_mock, hass):
    """Client timeouts are reported using the integration error type."""
    aioclient_mock.get(API_URL, exc=aiohttp.ServerTimeoutError())
    client = HitokotoApiClient(hass, "global", 3)
    with pytest.raises(HitokotoApiError):
        await client.async_get_quote(("k",))
