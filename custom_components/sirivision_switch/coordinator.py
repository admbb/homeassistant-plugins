"""Staggered multi-tier DataUpdateCoordinator for Sirivision SR-S25G3412F."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_COMMUNITY,
    CONF_DEVICE_NAME,
    CONF_HOST,
    CONF_POLL_DEVICE_INFO,
    CONF_POLL_STATUS,
    CONF_POLL_TRAFFIC,
    CONF_POLL_VLAN_MAC,
    CONF_PORT_ALIASES,
    CONF_PORT_IFINDEX_MAP,
    CONF_SNMP_PORT,
    CONF_SNMP_VERSION,
    DEFAULT_NAME,
    DEFAULT_POLL_DEVICE_INFO,
    DEFAULT_POLL_STATUS,
    DEFAULT_POLL_TRAFFIC,
    DEFAULT_POLL_VLAN_MAC,
    DEFAULT_SNMP_PORT,
    DEFAULT_SNMP_VERSION,
    DOMAIN,
)
from .port_mapping import PortMappingEntry, discover_port_mapping
from .snmp_client import SirivisionSnmpClient
from .traffic import (
    PortHistoryBuffer,
    compute_rate_bps,
    normalize_port_status,
    parse_duplex_label,
    parse_negotiated_speed_mbps,
)

_LOGGER = logging.getLogger(__name__)


class SirivisionSwitchCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinates read-only SNMP polling with staggered intervals and reboot recovery."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.host: str = entry.options.get(CONF_HOST, entry.data[CONF_HOST])
        self.snmp_port: int = int(entry.options.get(CONF_SNMP_PORT, entry.data.get(CONF_SNMP_PORT, DEFAULT_SNMP_PORT)))
        self.snmp_version: str = entry.options.get(CONF_SNMP_VERSION, entry.data.get(CONF_SNMP_VERSION, DEFAULT_SNMP_VERSION))
        self.device_name: str = entry.options.get(CONF_DEVICE_NAME, entry.data.get(CONF_DEVICE_NAME, DEFAULT_NAME))

        self.poll_traffic = max(3, int(entry.options.get(CONF_POLL_TRAFFIC, DEFAULT_POLL_TRAFFIC)))
        self.poll_status = max(5, int(entry.options.get(CONF_POLL_STATUS, DEFAULT_POLL_STATUS)))
        self.poll_vlan_mac = max(15, int(entry.options.get(CONF_POLL_VLAN_MAC, DEFAULT_POLL_VLAN_MAC)))
        self.poll_device_info = max(60, int(entry.options.get(CONF_POLL_DEVICE_INFO, DEFAULT_POLL_DEVICE_INFO)))

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.host}",
            update_interval=timedelta(seconds=self.poll_traffic),
        )

        self.client = SirivisionSnmpClient(
            hass=hass,
            host=self.host,
            port=self.snmp_port,
            community=entry.data[CONF_COMMUNITY],
            snmp_version=self.snmp_version,
            timeout=3.0,
            retries=1,
        )

        self._device_info: dict[str, Any] = {}
        self._interfaces: dict[int, dict[str, Any]] = {}
        self._port_mapping: list[PortMappingEntry] = []
        self._status_rows: dict[int, dict[str, Any]] = {}
        self._vlan_mac: dict[str, Any] = {"pvid_by_ifindex": {}, "vlans": [], "mac_entries": []}

        self._last_device_info_ts: float = 0.0
        self._last_status_ts: float = 0.0
        self._last_vlan_mac_ts: float = 0.0
        self._last_traffic_ts: float = 0.0
        self._last_uptime_ticks: int | None = None
        self._last_counter_is_64bit: bool | None = None
        self._prev_counters: dict[int, tuple[int, int]] = {}
        self._history: dict[str, PortHistoryBuffer] = {}

        self.snmp_connected: bool = False
        self.last_success_at: str | None = None
        self.last_error: str | None = None
        self._consecutive_failures: int = 0
        self._next_retry_at: float = 0.0

    def _refresh_mapping(self) -> None:
        aliases = self.entry.options.get(CONF_PORT_ALIASES, {})
        manual_map = self.entry.options.get(CONF_PORT_IFINDEX_MAP, {})
        self._port_mapping = discover_port_mapping(
            self._interfaces,
            manual_ifindex_map=manual_map,
            port_aliases=aliases,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        now_mono = time.monotonic()
        now_wall = time.time()

        # Exponential backoff when switch is offline
        if self._consecutive_failures > 0 and now_mono < self._next_retry_at:
            if self.data is not None:
                return self._build_offline_snapshot()
            raise UpdateFailed(self.last_error or "SNMP unreachable (backing off)")

        try:
            need_full_discovery = (
                not self._interfaces
                or (now_mono - self._last_device_info_ts) >= self.poll_device_info
                or self._consecutive_failures > 0
            )
            if need_full_discovery:
                self._device_info = await self.client.fetch_device_info()
                self._interfaces = await self.client.fetch_interface_inventory()
                self._refresh_mapping()
                self._last_device_info_ts = now_mono

            if (now_mono - self._last_status_ts) >= self.poll_status or not self._status_rows:
                self._status_rows = await self.client.fetch_port_status_and_errors()
                self._last_status_ts = now_mono

            if (now_mono - self._last_vlan_mac_ts) >= self.poll_vlan_mac:
                self._vlan_mac = await self.client.fetch_vlan_and_mac_table()
                self._last_vlan_mac_ts = now_mono

            counters, uptime_ticks, is_64bit = await self.client.fetch_traffic_counters()

            # A counter-width change needs a fresh baseline; values from the two
            # tables cannot safely be subtracted from one another.
            if self._last_counter_is_64bit is not None and self._last_counter_is_64bit != is_64bit:
                self._prev_counters.clear()
            self._last_counter_is_64bit = is_64bit

            # Detect device reboot via sysUpTime rollback -> invalidate delta & trigger discovery
            device_rebooted = (
                self._last_uptime_ticks is not None
                and uptime_ticks is not None
                and uptime_ticks < self._last_uptime_ticks
            )
            if device_rebooted:
                _LOGGER.info("Detected switch reboot on %s (sysUpTime reset), rediscovering ports", self.host)
                self._interfaces = await self.client.fetch_interface_inventory()
                self._refresh_mapping()
                self._prev_counters.clear()

            elapsed = (now_mono - self._last_traffic_ts) if self._last_traffic_ts > 0 else 0.0
            self._last_traffic_ts = now_mono
            if uptime_ticks is not None:
                self._last_uptime_ticks = uptime_ticks

            self.snmp_connected = True
            self._consecutive_failures = 0
            self.last_error = None
            self.last_success_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

            return self._assemble_snapshot(
                now_wall=now_wall,
                counters=counters,
                elapsed=elapsed,
                is_64bit=is_64bit,
                device_rebooted=device_rebooted,
                uptime_ticks=uptime_ticks,
            )

        except Exception as err:  # noqa: BLE001
            self._consecutive_failures += 1
            backoff_s = min(60, self.poll_traffic * (2 ** min(self._consecutive_failures - 1, 4)))
            self._next_retry_at = now_mono + backoff_s
            self.snmp_connected = False
            self.last_error = str(err)
            _LOGGER.warning("SNMP poll error on %s (%s); retry in %ss", self.host, err, backoff_s)

            if self.data is not None:
                return self._build_offline_snapshot()
            raise UpdateFailed(f"SNMP communication failed: {err}") from err

    def _build_offline_snapshot(self) -> dict[str, Any]:
        snap = dict(self.data or {})
        snap["snmp_connected"] = False
        snap["last_error"] = self.last_error or "SNMP 连接异常"
        snap["last_success_at"] = self.last_success_at
        return snap

    def _assemble_snapshot(
        self,
        *,
        now_wall: float,
        counters: dict[int, dict[str, int]],
        elapsed: float,
        is_64bit: bool,
        device_rebooted: bool,
        uptime_ticks: int | None,
    ) -> dict[str, Any]:
        mac_by_if: dict[int, list[dict[str, Any]]] = {}
        for item in self._vlan_mac.get("mac_entries", []):
            mac_by_if.setdefault(item["if_index"], []).append(
                {"mac": item["mac"], "vlan_id": item["vlan_id"]}
            )

        pvid_map: dict[int, int] = self._vlan_mac.get("pvid_by_ifindex", {})
        vlan_name_map = {v["vlan_id"]: v["name"] for v in self._vlan_mac.get("vlans", [])}

        ports_out: list[dict[str, Any]] = []
        total_rx_bps = 0.0
        total_tx_bps = 0.0
        rj45_rx_bps = 0.0
        rj45_tx_bps = 0.0
        sfp_rx_bps = 0.0
        sfp_tx_bps = 0.0
        ports_up = 0
        rj45_up = 0
        sfp_up = 0

        for entry in self._port_mapping:
            ifi = entry.if_index
            st_row = self._status_rows.get(ifi, {}) if ifi is not None else {}
            cnt_row = counters.get(ifi, {}) if ifi is not None else {}
            inv_row = self._interfaces.get(ifi, {}) if ifi is not None else {}

            status_info = normalize_port_status(st_row.get("admin_status"), st_row.get("oper_status"))
            speed_mbps = parse_negotiated_speed_mbps(
                status_info.is_connected,
                st_row.get("if_high_speed"),
                st_row.get("if_speed"),
            )
            duplex_label = parse_duplex_label(st_row.get("duplex"), status_info.is_connected)

            curr_rx = cnt_row.get("rx_bytes")
            curr_tx = cnt_row.get("tx_bytes")
            prev_pair = self._prev_counters.get(ifi) if ifi is not None else None
            prev_rx = prev_pair[0] if prev_pair else None
            prev_tx = prev_pair[1] if prev_pair else None

            rx_bps = compute_rate_bps(
                prev_rx,
                curr_rx,
                elapsed,
                is_64bit=is_64bit,
                is_connected=status_info.is_connected,
                device_rebooted=device_rebooted,
                max_port_mbps=entry.max_speed_mbps,
            )
            tx_bps = compute_rate_bps(
                prev_tx,
                curr_tx,
                elapsed,
                is_64bit=is_64bit,
                is_connected=status_info.is_connected,
                device_rebooted=device_rebooted,
                max_port_mbps=entry.max_speed_mbps,
            )

            if ifi is not None and curr_rx is not None and curr_tx is not None:
                self._prev_counters[ifi] = (curr_rx, curr_tx)
            elif ifi is not None:
                # Do not combine an old sample with the next poll's interval.
                self._prev_counters.pop(ifi, None)

            hist = self._history.setdefault(entry.physical_port, PortHistoryBuffer())
            hist.record(now_wall, rx_bps, tx_bps)

            if status_info.is_connected:
                ports_up += 1
                total_rx_bps += rx_bps
                total_tx_bps += tx_bps
                if entry.port_type == "rj45":
                    rj45_up += 1
                    rj45_rx_bps += rx_bps
                    rj45_tx_bps += tx_bps
                else:
                    sfp_up += 1
                    sfp_rx_bps += rx_bps
                    sfp_tx_bps += tx_bps

            pvid = pvid_map.get(ifi) if ifi is not None else None
            macs = mac_by_if.get(ifi, []) if ifi is not None else []

            ports_out.append(
                {
                    "physical_port": entry.physical_port,
                    "slot": entry.slot,
                    "type": entry.port_type,
                    "max_speed_mbps": entry.max_speed_mbps,
                    "if_index": ifi,
                    "interface_name": entry.interface_name,
                    "alias": entry.alias,
                    "mtu": inv_row.get("if_mtu"),
                    "admin_status": status_info.admin_key,
                    "admin_label": status_info.admin_label,
                    "oper_status": status_info.oper_key,
                    "oper_label": status_info.oper_label,
                    "summary_label": status_info.summary_label,
                    "led_color": status_info.led_color,
                    "connected": status_info.is_connected,
                    "speed_mbps": speed_mbps,
                    "duplex": duplex_label,
                    "pvid": pvid,
                    "vlan_name": vlan_name_map.get(pvid) if pvid is not None else None,
                    "rx_bps": rx_bps,
                    "tx_bps": tx_bps,
                    "rx_bytes": curr_rx,
                    "tx_bytes": curr_tx,
                    "in_errors": st_row.get("in_errors", 0),
                    "out_errors": st_row.get("out_errors", 0),
                    "in_discards": st_row.get("in_discards", 0),
                    "out_discards": st_row.get("out_discards", 0),
                    "mac_count": len(macs),
                    "mac_list": macs[:32],
                    "history_5m": hist.to_compact_5m(),
                    "history_1h": hist.to_compact_1h(),
                }
            )

        uptime_sec = int(uptime_ticks // 100) if uptime_ticks is not None else None

        return {
            "device_name": self.device_name,
            "manufacturer": "Sirivision (希力威视)",
            "model": self._device_info.get("sys_descr") or "SR-S25G3412F",
            "sys_name": self._device_info.get("sys_name") or "Switch",
            "sys_descr": self._device_info.get("sys_descr") or "SR-S25G3412F",
            "sys_object_id": self._device_info.get("sys_object_id") or "",
            "host": self.host,
            "snmp_connected": True,
            "last_success_at": self.last_success_at,
            "last_error": None,
            "uptime_seconds": uptime_sec,
            "counter_bits": 64 if is_64bit else 32,
            "ports_total": len(ports_out),
            "ports_up": ports_up,
            "ports_rj45_up": rj45_up,
            "ports_sfp_up": sfp_up,
            "total_rx_bps": round(total_rx_bps, 1),
            "total_tx_bps": round(total_tx_bps, 1),
            "rj45_rx_bps": round(rj45_rx_bps, 1),
            "rj45_tx_bps": round(rj45_tx_bps, 1),
            "sfp_rx_bps": round(sfp_rx_bps, 1),
            "sfp_tx_bps": round(sfp_tx_bps, 1),
            "vlans": self._vlan_mac.get("vlans", []),
            "mac_total": len(self._vlan_mac.get("mac_entries", [])),
            "mac_entries": self._vlan_mac.get("mac_entries", [])[:120],
            "ports": ports_out,
        }
