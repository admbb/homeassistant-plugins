"""Traffic calculation, counter wrap/reset handling, and status normalization."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque

from .const import (
    ADMIN_STATUS_MAP,
    DUPLEX_STATUS_MAP,
    OPER_STATUS_MAP,
    VALID_REPORTED_SPEEDS_MBPS,
)

MAX_UINT32: int = 1 << 32
MAX_UINT64: int = 1 << 64


@dataclass(frozen=True)
class PortStatusInfo:
    """Normalized port administrative and operational status."""

    admin_code: int
    admin_key: str
    admin_label: str
    oper_code: int
    oper_key: str
    oper_label: str
    is_admin_disabled: bool
    is_connected: bool
    led_color: str  # "green" | "gray" | "yellow" | "blue" | "orange"
    summary_label: str


def normalize_port_status(admin_raw: int | None, oper_raw: int | None) -> PortStatusInfo:
    """Normalize ifAdminStatus and ifOperStatus without confusing admin-down with link-down."""
    admin_code = int(admin_raw) if admin_raw in ADMIN_STATUS_MAP else 1
    oper_code = int(oper_raw) if oper_raw in OPER_STATUS_MAP else 4

    admin_key, admin_label = ADMIN_STATUS_MAP[admin_code]
    oper_key, oper_label = OPER_STATUS_MAP[oper_code]

    is_admin_disabled = admin_code == 2
    is_connected = (not is_admin_disabled) and (oper_code == 1)

    if is_admin_disabled:
        led_color = "orange"
        summary_label = "管理禁用"
    elif oper_code == 1:
        led_color = "green"
        summary_label = "已连接"
    elif oper_code == 3:
        led_color = "yellow"
        summary_label = "测试中"
    elif oper_code == 5:
        led_color = "blue"
        summary_label = "休眠"
    elif oper_code == 7:
        led_color = "orange"
        summary_label = "下层断开"
    elif oper_code == 6:
        led_color = "gray"
        summary_label = "不存在"
    elif oper_code == 4:
        led_color = "gray"
        summary_label = "未知"
    else:
        led_color = "gray"
        summary_label = "未连接"

    return PortStatusInfo(
        admin_code=admin_code,
        admin_key=admin_key,
        admin_label=admin_label,
        oper_code=oper_code,
        oper_key=oper_key,
        oper_label=oper_label,
        is_admin_disabled=is_admin_disabled,
        is_connected=is_connected,
        led_color=led_color,
        summary_label=summary_label,
    )


def parse_negotiated_speed_mbps(
    is_connected: bool,
    if_high_speed: int | None,
    if_speed_bps: int | None,
) -> int | None:
    """Extract negotiated link speed in Mbps strictly from live SNMP values.

    Observed Sirivision SR-S25G3412F firmware behavior:
    - 100M / 1G UP links report exact values (100 / 1000).
    - Some 2.5G / 10G UP links report 0/0 -> return None (never guess max speed).
    - Some DOWN links report wrapped 32-bit default 1410 -> return None when disconnected.
    """
    if not is_connected:
        return None

    candidates: list[int] = []
    if if_high_speed is not None and int(if_high_speed) > 0:
        candidates.append(int(if_high_speed))
    if if_speed_bps is not None and int(if_speed_bps) > 0:
        mbps = int(if_speed_bps) // 1_000_000
        if mbps > 0:
            candidates.append(mbps)

    for spd in candidates:
        if spd in VALID_REPORTED_SPEEDS_MBPS:
            return spd

    return None


def parse_duplex_label(duplex_raw: int | None, is_connected: bool) -> str:
    """Return duplex string only when link is up and supported."""
    if not is_connected or duplex_raw is None:
        return "不支持" if duplex_raw is None else "未连接"
    return DUPLEX_STATUS_MAP.get(int(duplex_raw), "未知")


def compute_counter_delta(
    prev_bytes: int,
    curr_bytes: int,
    is_64bit: bool,
    device_rebooted: bool = False,
) -> int | None:
    """Compute byte delta handling device reboot resets and 32/64-bit wraparound.

    Returns None when counter reset occurred (so caller clamps rate to 0 instead of a false spike).
    """
    if curr_bytes < 0 or prev_bytes < 0:
        return None
    if device_rebooted:
        return None
    if curr_bytes >= prev_bytes:
        return curr_bytes - prev_bytes

    # Counter went backwards -> distinguish wraparound from counter reset/device reboot
    modulus = MAX_UINT64 if is_64bit else MAX_UINT32
    wrap_threshold = int(modulus * 0.70)
    if prev_bytes >= wrap_threshold:
        wrapped = (modulus - prev_bytes) + curr_bytes
        return wrapped if wrapped >= 0 else None

    # Otherwise counter was reset (e.g. switch reboot or stats cleared)
    return None


def compute_rate_bps(
    prev_bytes: int | None,
    curr_bytes: int | None,
    elapsed_seconds: float,
    *,
    is_64bit: bool,
    is_connected: bool,
    device_rebooted: bool = False,
    max_port_mbps: int = 10000,
) -> float:
    """Calculate live bit/s rate with full wraparound, reboot, and DOWN-port protection."""
    if not is_connected:
        return 0.0
    if prev_bytes is None or curr_bytes is None or elapsed_seconds <= 0.1:
        return 0.0

    delta = compute_counter_delta(prev_bytes, curr_bytes, is_64bit, device_rebooted=device_rebooted)
    if delta is None or delta <= 0:
        return 0.0

    bps = (delta * 8.0) / elapsed_seconds
    # Sanity upper bound: 2x physical port cap guards against transient clock/counter glitches
    max_sane_bps = max(max_port_mbps, 10000) * 1_000_000 * 2.0
    if bps < 0 or bps > max_sane_bps:
        return 0.0

    return round(bps, 1)


@dataclass
class TrafficSample:
    """Compact timestamped traffic point."""

    ts: int
    rx_bps: float
    tx_bps: float


class PortHistoryBuffer:
    """Maintains ~5m high-resolution (60 samples @ 5s) and ~1h downsampled (60 samples @ 60s) history."""

    def __init__(self) -> None:
        self._samples_5m: Deque[TrafficSample] = deque(maxlen=60)
        self._samples_1h: Deque[TrafficSample] = deque(maxlen=60)
        self._last_1h_bucket: int = -1

    def record(self, timestamp: float, rx_bps: float, tx_bps: float) -> None:
        ts_int = int(timestamp)
        pt = TrafficSample(ts=ts_int, rx_bps=round(rx_bps, 1), tx_bps=round(tx_bps, 1))
        self._samples_5m.append(pt)

        bucket = ts_int // 60
        if bucket != self._last_1h_bucket:
            self._last_1h_bucket = bucket
            self._samples_1h.append(pt)
        elif self._samples_1h:
            # Smooth minute peak/average in-place
            last = self._samples_1h[-1]
            self._samples_1h[-1] = TrafficSample(
                ts=ts_int,
                rx_bps=round((last.rx_bps + rx_bps) / 2.0, 1),
                tx_bps=round((last.tx_bps + tx_bps) / 2.0, 1),
            )

    def to_compact_5m(self) -> list[list[float]]:
        """Return compact [[ts, rx_mbps, tx_mbps], ...] for frontend chart."""
        return [
            [s.ts, round(s.rx_bps / 1_000_000.0, 3), round(s.tx_bps / 1_000_000.0, 3)]
            for s in self._samples_5m
        ]

    def to_compact_1h(self) -> list[list[float]]:
        """Return compact [[ts, rx_mbps, tx_mbps], ...] for 1h chart."""
        return [
            [s.ts, round(s.rx_bps / 1_000_000.0, 3), round(s.tx_bps / 1_000_000.0, 3)]
            for s in self._samples_1h
        ]
