"""Bounded SSE consumer with reconnect and event filtering."""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .api import OxiDNSError
from .const import SIGNAL_STREAM_UPDATED
from .models import record_summary


class EventStream:
    def __init__(self, hass, client, tag, entry_id):
        self.hass, self.client, self.tag, self.entry_id = hass, client, tag, entry_id
        self.records = deque(maxlen=100)
        self.ids = deque(maxlen=500)
        self.task = None
        self.connected = False

    async def run(self):
        delay = 1
        while True:
            connected_at = None
            try:
                async for event, data in self.client.stream(self.tag, tail=0):
                    if not self.connected:
                        self.connected = True
                        connected_at = time.monotonic()
                        self.hass.bus.async_fire("oxidns_connection_restored", {"entry_id": self.entry_id})
                        async_dispatcher_send(self.hass, SIGNAL_STREAM_UPDATED.format(self.entry_id))
                    if event != "record":
                        continue
                    try:
                        payload = json.loads(data)
                        if not isinstance(payload, dict):
                            continue
                        record = record_summary(payload)
                        identity = (record["id"], record["created_at_ms"])
                        if record["id"] is None or identity in self.ids:
                            continue
                        self.ids.append(identity)
                        self.records.append(record)
                        async_dispatcher_send(self.hass, SIGNAL_STREAM_UPDATED.format(self.entry_id))
                        self.hass.bus.async_fire("oxidns_query_received", {**record, "entry_id": self.entry_id})
                    except (ValueError, TypeError, KeyError, AttributeError):
                        continue
            except OxiDNSError:
                pass
            if self.connected:
                self.connected = False
                async_dispatcher_send(self.hass, SIGNAL_STREAM_UPDATED.format(self.entry_id))
                self.hass.bus.async_fire("oxidns_connection_lost", {"entry_id": self.entry_id})
            if connected_at is not None and time.monotonic() - connected_at >= 30:
                delay = 1
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)
