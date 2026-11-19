"""Polling coordinator for health, metrics and sampled recorder statistics."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AuthenticationError, OxiDNSError, ServiceUnavailable
from .const import CONF_METRICS_TAG, CONF_RECORDER_TAG, DOMAIN
from .models import Rate, metrics


class OxiDNSCoordinator(DataUpdateCoordinator):
    """Keep polling schedules independent while sharing a single timer."""

    def __init__(self, hass, client, entry):
        super().__init__(hass, logger=logging.getLogger(__name__), name=DOMAIN, update_interval=timedelta(seconds=15))
        self.client, self.entry = client, entry
        self.rate = Rate()
        self.failures = 0
        self.next_health = self.next_stats = 0.0
        self.snapshot = {"online": False, "ready": None, "stats": {}, "metrics": {}}

    async def _optional(self, path, params=None, *, json_response=True):
        try:
            return await self.client.get(path, params, json_response=json_response)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except OxiDNSError:
            return None

    async def _async_update_data(self):
        now = time.monotonic()
        data = dict(self.snapshot)
        if now >= self.next_health:
            health = await self._optional("health")
            data["online"] = health is not None
            data["health"] = health
            self.failures = 0 if health is not None else min(self.failures + 1, 4)
            self.next_health = now + 30 * (2 ** max(self.failures - 1, 0))
            try:
                ready = await self.client.get("readyz", json_response=False)
                data["ready"] = ready == "ready"
            except AuthenticationError as err:
                raise ConfigEntryAuthFailed from err
            except ServiceUnavailable:
                data["ready"] = False
            except OxiDNSError:
                data["ready"] = None
        if not data["online"]:
            self.rate.update(None, now, None)
            data.update({"metrics": {}, "stats": {}, "qps": None})
            self.snapshot = data
            return data
        tag = self.entry.data.get(CONF_METRICS_TAG)
        raw = await self._optional("metrics", json_response=False) if tag else None
        data["metrics"] = metrics(raw, tag) if raw else {}
        total = data["metrics"].get("query_total")
        data["qps"] = self.rate.update(total, now, (data.get("health") or {}).get("instance_id"))
        recorder = self.entry.data.get(CONF_RECORDER_TAG)
        if recorder and now >= self.next_stats:
            self.next_stats = now + 60
            end = int(time.time() * 1000)
            params = {"since_ms": end - 3600000, "until_ms": end}
            endpoints = ("top_clients", "top_qnames", "qtype", "rcode", "latency", "timeseries")
            slots = asyncio.Semaphore(2)

            async def fetch(endpoint):
                async with slots:
                    return await self._optional(
                        self.client.recorder_path(recorder, "stats/" + endpoint),
                        {
                            **params,
                            **(
                                {"limit": 10}
                                if endpoint == "top_clients"
                                else {"limit": 20}
                                if endpoint == "top_qnames"
                                else {}
                            ),
                        },
                    )

            values = await asyncio.gather(*(fetch(endpoint) for endpoint in endpoints))
            data["stats"] = dict(zip(endpoints, values, strict=True))
        self.snapshot = data
        return data
