"""Quote coordinator, request throttling, scheduling, and local state."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time as monotonic_time
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_call_later,
    async_track_time_change,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import HitokotoApiClient, HitokotoApiError, Quote
from .const import (
    CONF_ALLOW_DUPLICATE_FAVORITES,
    CONF_API_ROUTE,
    CONF_AUTO_UPDATE,
    CONF_CATEGORIES,
    CONF_ENABLE_FAVORITES,
    CONF_HISTORY_LIMIT,
    CONF_MAX_LENGTH,
    CONF_MIN_LENGTH,
    CONF_PREFER_AUTHOR,
    CONF_PREFER_SOURCE,
    CONF_RETRIES,
    CONF_SAVE_HISTORY,
    CONF_TIMEOUT,
    CONF_UPDATE_TIME,
    DEFAULT_CATEGORIES,
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_MAX_LENGTH,
    DEFAULT_MIN_LENGTH,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_TIME,
    DOMAIN,
    MAX_MANUAL_COOLDOWN,
    REQUEST_SPACING,
    RETRY_DELAYS,
    STATUS_ERROR,
    STATUS_NORMAL,
    STATUS_STALE,
    STATUS_UNAVAILABLE,
)
from .storage import HitokotoStorage, PersistentData

_LOGGER = logging.getLogger(__name__)


class RequestThrottled(HomeAssistantError):
    """Raised when a user requests a refresh inside the cooldown window."""


class RequestGate:
    """Serialize requests for this integration and respect the public API limits."""

    def __init__(self) -> None:
        """Initialize the shared per-HA request gate."""
        self.lock = asyncio.Lock()
        self._last_request = 0.0
        self._last_manual = 0.0

    @property
    def manual_cooldown_remaining(self) -> float:
        """Return seconds until another user-initiated request is allowed."""
        elapsed = monotonic_time.monotonic() - self._last_manual
        return max(0.0, MAX_MANUAL_COOLDOWN - elapsed)

    async def async_call(self, operation: Any, *, manual: bool) -> Quote:
        """Run a single request, spaced below the global endpoint QPS limit."""
        async with self.lock:
            now = monotonic_time.monotonic()
            if manual and now - self._last_manual < MAX_MANUAL_COOLDOWN:
                raise RequestThrottled(
                    "Manual refresh is limited to one request every five seconds"
                )

            delay = REQUEST_SPACING - (now - self._last_request)
            if delay > 0:
                await asyncio.sleep(delay)
            started = monotonic_time.monotonic()
            self._last_request = started
            if manual:
                self._last_manual = started
            return await operation()


@dataclass(slots=True)
class CoordinatorData:
    """State shared by all entities for one config entry."""

    quote: Quote | None
    quote_date: str | None
    status: str
    error: str | None
    history: list[Quote]
    favorites: list[Quote]
    last_updated: str | None


class HitokotoCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Coordinate daily and user-triggered updates without periodic polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        storage: HitokotoStorage,
        gate: RequestGate,
    ) -> None:
        """Initialize the coordinator for one config entry."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
            always_update=True,
        )
        self.entry = entry
        self.storage = storage
        self.gate = gate
        options = {**entry.data, **entry.options}
        self.categories = tuple(options.get(CONF_CATEGORIES, DEFAULT_CATEGORIES))
        self.save_history = bool(options.get(CONF_SAVE_HISTORY, True))
        self.history_limit = int(options.get(CONF_HISTORY_LIMIT, DEFAULT_HISTORY_LIMIT))
        self.enable_favorites = bool(options.get(CONF_ENABLE_FAVORITES, True))
        self.allow_duplicate_favorites = bool(
            options.get(CONF_ALLOW_DUPLICATE_FAVORITES, False)
        )
        self.prefer_author = bool(options.get(CONF_PREFER_AUTHOR, False))
        self.prefer_source = bool(options.get(CONF_PREFER_SOURCE, False))
        self.enable_retries = bool(options.get(CONF_RETRIES, True))
        self.auto_update = bool(options.get(CONF_AUTO_UPDATE, True))
        self.update_time = self._parse_update_time(
            options.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME)
        )
        self.client = HitokotoApiClient(
            hass,
            route=options.get(CONF_API_ROUTE, "global"),
            timeout=int(options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
            min_length=int(options.get(CONF_MIN_LENGTH, DEFAULT_MIN_LENGTH)),
            max_length=int(options.get(CONF_MAX_LENGTH, DEFAULT_MAX_LENGTH)),
        )
        self.persistent = PersistentData()
        self.data = CoordinatorData(
            quote=None,
            quote_date=None,
            status=STATUS_UNAVAILABLE,
            error=None,
            history=[],
            favorites=[],
            last_updated=None,
        )
        self._refresh_lock = asyncio.Lock()
        self._cancel_daily: Any = None
        self._cancel_retry: Any = None
        self._cancel_midnight: Any = None
        self._retry_index = 0

    async def async_initialize(self) -> None:
        """Restore local data, schedule updates, then fetch only if needed."""
        self.persistent = await self.storage.async_load()
        today = self._today().isoformat()
        quote = self.persistent.daily_quote
        if quote is not None and self.persistent.quote_date == today:
            status = STATUS_NORMAL
        elif quote is not None:
            status = STATUS_STALE
        else:
            status = STATUS_UNAVAILABLE
        self.data = self._make_data(quote=quote, status=status, error=None)
        self.async_set_updated_data(self.data)

        if self.auto_update:
            self._schedule_daily_update()
        self._schedule_midnight_refresh()

        if quote is None or self.persistent.quote_date != today:
            await self.async_refresh_quote(reason="startup", manual=False, force=False)

    @property
    def is_favorite(self) -> bool:
        """Return whether the active sentence is in the favorite list."""
        quote = self.data.quote
        return quote is not None and any(
            self._quote_key(saved) == self._quote_key(quote)
            for saved in self.persistent.favorites
        )

    @property
    def last_updated_datetime(self) -> datetime | None:
        """Return the current sentence's local-aware fetched time."""
        if self.data.last_updated is None:
            return None
        try:
            parsed = datetime.fromisoformat(self.data.last_updated)
        except ValueError:
            return None
        return dt_util.as_local(parsed) if parsed.tzinfo is not None else None

    async def async_refresh_quote(
        self, *, reason: str, manual: bool, force: bool
    ) -> bool:
        """Fetch one quote, retain cache on errors, and persist every outcome."""
        async with self._refresh_lock:
            today = self._today().isoformat()
            if (
                not force
                and self.data.quote is not None
                and self.persistent.quote_date == today
                and reason in {"startup", "scheduled", "retry"}
            ):
                return False

            now = datetime.now(UTC)
            self.persistent.last_attempt_at = now.isoformat()
            await self.storage.async_save(self.persistent)
            try:
                quote = await self.gate.async_call(
                    lambda: self.client.async_get_quote(self.categories), manual=manual
                )
            except RequestThrottled:
                _LOGGER.debug("Refresh for entry %s was throttled", self.entry.entry_id)
                if reason == "options":
                    self._cancel_scheduled_retry()
                    self._cancel_retry = async_call_later(
                        self.hass,
                        self.gate.manual_cooldown_remaining + 0.1,
                        lambda _now: self.hass.async_create_task(
                            self.async_refresh_quote(
                                reason="options", manual=True, force=True
                            )
                        ),
                    )
                elif manual:
                    raise
                return False
            except (HitokotoApiError, HomeAssistantError) as err:
                _LOGGER.warning(
                    "Hitokoto refresh failed for entry %s: %s", self.entry.entry_id, err
                )
                status = STATUS_STALE if self.data.quote is not None else STATUS_ERROR
                self.data = self._make_data(
                    quote=self.data.quote, status=status, error=str(err)
                )
                self.async_set_updated_data(self.data)
                await self.storage.async_save(self.persistent)
                if self.enable_retries:
                    self._schedule_retry()
                return False
            except Exception as err:  # Unexpected client errors must not unload HA.
                _LOGGER.exception(
                    "Unexpected Hitokoto error for entry %s", self.entry.entry_id
                )
                status = STATUS_STALE if self.data.quote is not None else STATUS_ERROR
                self.data = self._make_data(
                    quote=self.data.quote, status=status, error=str(err)
                )
                self.async_set_updated_data(self.data)
                if self.enable_retries:
                    self._schedule_retry()
                return False

            if reason == "manual" and self._prefer_existing_quote(quote, today):
                self.persistent.quote_date = today
                self.data = self._make_data(
                    quote=self.data.quote, status=STATUS_NORMAL, error=None
                )
                self.async_set_updated_data(self.data)
                await self.storage.async_save(self.persistent)
                self._cancel_scheduled_retry()
                return False

            self._cancel_scheduled_retry()
            self._retry_index = 0
            self.persistent.daily_quote = quote
            self.persistent.quote_date = today
            if self.save_history:
                self._add_to_history(quote)
            self.data = self._make_data(quote=quote, status=STATUS_NORMAL, error=None)
            await self.storage.async_save(self.persistent)
            self.async_set_updated_data(self.data)
            _LOGGER.debug(
                "Updated Hitokoto sentence for entry %s (%s)",
                self.entry.entry_id,
                reason,
            )
            return True

    def _prefer_existing_quote(self, candidate: Quote, today: str) -> bool:
        """Honor metadata preferences when replacing a quote during the same day."""
        current = self.data.quote
        if current is None or self.persistent.quote_date != today:
            return False
        return (
            self.prefer_author
            and current.author is not None
            and candidate.author is None
        ) or (
            self.prefer_source
            and current.source is not None
            and candidate.source is None
        )

    async def async_add_favorite(self, uuid: str | None = None) -> None:
        """Save the requested or current sentence as a favorite."""
        if not self.enable_favorites:
            raise HomeAssistantError("Favorites are disabled in this config entry")
        quote = self._find_quote(uuid)
        if not self.allow_duplicate_favorites and any(
            self._quote_key(item) == self._quote_key(quote)
            for item in self.persistent.favorites
        ):
            return
        self.persistent.favorites.insert(0, quote)
        await self._async_publish_local_change()

    async def async_remove_favorite(self, uuid: str | None = None) -> None:
        """Remove a favorite by UUID or the active sentence."""
        quote = self._find_quote(uuid)
        key = self._quote_key(quote)
        self.persistent.favorites = [
            item for item in self.persistent.favorites if self._quote_key(item) != key
        ]
        await self._async_publish_local_change()

    async def async_clear_history(self) -> None:
        """Clear history without touching favorites or the daily cache."""
        self.persistent.history.clear()
        await self._async_publish_local_change()

    def get_history(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Return recent history in newest-first order."""
        quotes = self.persistent.history
        if limit is not None:
            quotes = quotes[:limit]
        return [self._quote_response(quote) for quote in quotes]

    def get_favorites(self) -> list[dict[str, Any]]:
        """Return favorites in newest-first order."""
        return [self._quote_response(quote) for quote in self.persistent.favorites]

    def async_shutdown(self) -> None:
        """Cancel all scheduled callbacks when the config entry unloads."""
        self._cancel_daily_update()
        self._cancel_scheduled_retry()
        if self._cancel_midnight is not None:
            self._cancel_midnight()
            self._cancel_midnight = None

    async def _async_update_data(self) -> CoordinatorData:
        """DataUpdateCoordinator hook; explicit refreshes select all network work."""
        return self.data

    def _add_to_history(self, quote: Quote) -> None:
        """Insert a new sentence and enforce the configured history limit."""
        key = self._quote_key(quote)
        if all(self._quote_key(item) != key for item in self.persistent.history):
            self.persistent.history.insert(0, quote)
        if self.history_limit > 0:
            self.persistent.history = self.persistent.history[: self.history_limit]

    async def _async_publish_local_change(self) -> None:
        """Persist changed counts and notify coordinator entities."""
        await self.storage.async_save(self.persistent)
        self.data = self._make_data(
            quote=self.data.quote, status=self.data.status, error=self.data.error
        )
        self.async_set_updated_data(self.data)

    def _find_quote(self, uuid: str | None) -> Quote:
        """Resolve a sentence from current state, history, or favorites."""
        if uuid is None:
            if self.data.quote is None:
                raise HomeAssistantError("There is no current sentence")
            return self.data.quote
        for quote in [
            self.data.quote,
            *self.persistent.history,
            *self.persistent.favorites,
        ]:
            if quote is not None and quote.uuid == uuid:
                return quote
        raise HomeAssistantError(f"Sentence UUID {uuid} was not found locally")

    def _make_data(
        self, *, quote: Quote | None, status: str, error: str | None
    ) -> CoordinatorData:
        """Build a snapshot from durable state and current request status."""
        return CoordinatorData(
            quote=quote,
            quote_date=self.persistent.quote_date,
            status=status,
            error=error,
            history=list(self.persistent.history),
            favorites=list(self.persistent.favorites),
            last_updated=(quote.fetched_at if quote is not None else None),
        )

    def _schedule_daily_update(self) -> None:
        """Register the user's local wall-clock daily update time."""
        self._cancel_daily_update()
        self._cancel_daily = async_track_time_change(
            self.hass,
            self._handle_daily_update,
            hour=self.update_time.hour,
            minute=self.update_time.minute,
            second=self.update_time.second,
        )

    @callback
    def _handle_daily_update(self, _now: datetime) -> None:
        self.hass.async_create_task(
            self.async_refresh_quote(reason="scheduled", manual=False, force=False)
        )

    def _schedule_midnight_refresh(self) -> None:
        """Re-evaluate local date at midnight to expose a stale cache."""
        if self._cancel_midnight is not None:
            self._cancel_midnight()
        self._cancel_midnight = async_track_time_change(
            self.hass,
            self._handle_midnight,
            hour=0,
            minute=0,
            second=0,
        )

    @callback
    def _handle_midnight(self, _now: datetime) -> None:
        """Update status after the local day changes, without network traffic."""
        if self.data.quote is None:
            return
        if self.persistent.quote_date != self._today().isoformat():
            self.data = self._make_data(
                quote=self.data.quote, status=STATUS_STALE, error=None
            )
            self.async_set_updated_data(self.data)

    def _schedule_retry(self) -> None:
        """Schedule the next bounded retry, if one remains in this cycle."""
        self._cancel_scheduled_retry()
        if self._retry_index >= len(RETRY_DELAYS):
            return
        delay = RETRY_DELAYS[self._retry_index]
        self._retry_index += 1
        self._cancel_retry = async_call_later(
            self.hass,
            delay,
            lambda _now: self.hass.async_create_task(
                self.async_refresh_quote(reason="retry", manual=False, force=True)
            ),
        )

    def _cancel_scheduled_retry(self) -> None:
        """Cancel a pending retry callback."""
        if self._cancel_retry is not None:
            self._cancel_retry()
            self._cancel_retry = None

    def _cancel_daily_update(self) -> None:
        """Cancel the daily wall-clock callback."""
        if self._cancel_daily is not None:
            self._cancel_daily()
            self._cancel_daily = None

    def _today(self) -> date:
        """Return today's date in the Home Assistant configured timezone."""
        return dt_util.now(self.hass).date()

    @staticmethod
    def _parse_update_time(value: Any) -> time:
        """Convert a TimeSelector string or time object to a naive local time."""
        if isinstance(value, time):
            return value.replace(tzinfo=None)
        if isinstance(value, str):
            try:
                return time.fromisoformat(value).replace(tzinfo=None)
            except ValueError:
                pass
        return DEFAULT_UPDATE_TIME

    @staticmethod
    def _quote_key(quote: Quote) -> str:
        """Return a stable identifier even when the API omitted its UUID."""
        if quote.uuid:
            return quote.uuid
        identity = json.dumps(
            [quote.text, quote.category_code, quote.source, quote.author],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(identity.encode()).hexdigest()

    @staticmethod
    def _quote_response(quote: Quote) -> dict[str, Any]:
        """Serialize one quote for the history and favorites actions."""
        return {
            "text": quote.text,
            "uuid": quote.uuid,
            "category": quote.category_name,
            "category_code": quote.category_code,
            "author": quote.author,
            "source": quote.source,
            "creator": quote.creator,
            "created_at": quote.created_at,
            "length": quote.length,
            "source_url": quote.source_url,
            "fetched_at": quote.fetched_at,
        }
