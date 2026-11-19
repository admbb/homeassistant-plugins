"""Asynchronous client for the official Hitokoto sentence API."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_URLS, CATEGORY_NAMES, DEFAULT_MAX_LENGTH, DEFAULT_MIN_LENGTH

_LOGGER = logging.getLogger(__name__)


class HitokotoApiError(Exception):
    """Raised when the Hitokoto API cannot return a usable sentence."""


@dataclass(frozen=True, slots=True)
class Quote:
    """A normalized sentence returned by the official API."""

    text: str
    uuid: str | None
    category_code: str | None
    source: str | None
    author: str | None
    creator: str | None
    created_at: str | None
    length: int
    fetched_at: str

    @property
    def category_name(self) -> str | None:
        """Return the localized category name when the code is known."""
        if self.category_code is None:
            return None
        return CATEGORY_NAMES.get(self.category_code, self.category_code)

    @property
    def source_url(self) -> str | None:
        """Return the official sentence page when the API supplied a UUID."""
        if self.uuid is None:
            return None
        return f"https://hitokoto.cn?uuid={self.uuid}"

    def as_storage(self) -> dict[str, Any]:
        """Serialize the quote for Home Assistant Store."""
        return asdict(self)

    @classmethod
    def from_storage(cls, value: dict[str, Any]) -> Quote | None:
        """Restore a quote from persisted data, tolerating older schemas."""
        text = value.get("text")
        if not isinstance(text, str) or not text.strip():
            # Version 1 initially used the upstream field name.
            text = value.get("hitokoto")
        if not isinstance(text, str) or not text.strip():
            return None

        fetched_at = value.get("fetched_at")
        if not isinstance(fetched_at, str):
            fetched_at = datetime.now(UTC).isoformat()

        length = value.get("length", len(text))
        try:
            normalized_length = int(length)
        except (TypeError, ValueError):
            normalized_length = len(text)

        def optional_string(key: str, legacy_key: str | None = None) -> str | None:
            item = value.get(key)
            if item is None and legacy_key is not None:
                item = value.get(legacy_key)
            return item.strip() if isinstance(item, str) and item.strip() else None

        return cls(
            text=text.strip(),
            uuid=optional_string("uuid"),
            category_code=optional_string("category_code", "type"),
            source=optional_string("source", "from"),
            author=optional_string("author", "from_who"),
            creator=optional_string("creator"),
            created_at=optional_string("created_at"),
            length=normalized_length,
            fetched_at=fetched_at,
        )


class HitokotoApiClient:
    """Call the configured API using Home Assistant's shared session."""

    def __init__(
        self,
        hass: HomeAssistant,
        route: str,
        timeout: int,
        min_length: int = DEFAULT_MIN_LENGTH,
        max_length: int = DEFAULT_MAX_LENGTH,
    ) -> None:
        """Initialize the client."""
        self._session = async_get_clientsession(hass)
        self._url = API_URLS[route]
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._min_length = min_length
        self._max_length = max_length

    async def async_get_quote(self, categories: tuple[str, ...]) -> Quote:
        """Fetch one sentence, preserving repeated category parameters."""
        params: list[tuple[str, str]] = [
            ("encode", "json"),
            ("charset", "utf-8"),
            ("min_length", str(self._min_length)),
            ("max_length", str(self._max_length)),
        ]
        params.extend(("c", category) for category in categories)

        try:
            async with self._session.get(
                self._url, params=params, timeout=self._timeout
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise HitokotoApiError("API request failed") from err

        if not isinstance(payload, dict):
            raise HitokotoApiError("API response is not a JSON object")

        text = payload.get("hitokoto")
        if not isinstance(text, str) or not text.strip():
            raise HitokotoApiError("API response has no usable sentence")

        quote_length = payload.get("length", len(text))
        try:
            quote_length = int(quote_length)
        except (TypeError, ValueError):
            quote_length = len(text)

        uuid = payload.get("uuid")
        if not isinstance(uuid, str) or not uuid.strip():
            uuid = None

        def clean_string(field: str) -> str | None:
            value = payload.get(field)
            return value.strip() if isinstance(value, str) and value.strip() else None

        category = clean_string("type")
        if category not in CATEGORY_NAMES:
            category = None

        return Quote(
            text=text.strip(),
            uuid=uuid,
            category_code=category,
            source=clean_string("from"),
            author=clean_string("from_who"),
            creator=clean_string("creator"),
            created_at=clean_string("created_at"),
            length=quote_length,
            fetched_at=datetime.now(UTC).isoformat(),
        )
