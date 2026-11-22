"""Coordinator for NetFlow Plus telemetry."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, NetFlowClient, NetFlowError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NetFlowCoordinator(DataUpdateCoordinator[dict]):
    """Poll the read-only NetFlow Plus API."""

    def __init__(self, hass, client: NetFlowClient, entry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        """Refresh engine status and application ranking."""
        try:
            status = await self.client.status()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("NetFlow Plus authentication failed") from err
        except NetFlowError as err:
            raise UpdateFailed("Unable to read NetFlow Plus API") from err

        try:
            ranking = await self.client.app_ranking()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("NetFlow Plus authentication failed") from err
        except NetFlowError as err:
            _LOGGER.warning("NetFlow Plus application ranking is temporarily unavailable")
            ranking = None
        return {"status": status, "ranking": ranking}
