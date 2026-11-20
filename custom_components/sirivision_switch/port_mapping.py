"""Physical port discovery and manual mapping for Sirivision SR-S25G3412F."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .const import CANONICAL_PORTS

_HISGMII_RE = re.compile(r"^hisgmiiethernet(\d+)$", re.IGNORECASE)
_TENGIG_RE = re.compile(r"^tengigabitethernet(\d+)$", re.IGNORECASE)
_LAG_RE = re.compile(r"^(lag|po|port-channel|bond|trunk|vlan|lo)", re.IGNORECASE)


@dataclass(frozen=True)
class PortMappingEntry:
    """Resolved physical-to-SNMP ifIndex mapping for one switch port."""

    physical_port: str
    slot: int
    port_type: str  # "rj45" | "sfp_plus"
    max_speed_mbps: int
    if_index: int | None
    interface_name: str
    alias: str


def _classify_interface(if_descr: str, if_name: str, if_type: int) -> tuple[str, int] | None:
    """Classify an SNMP interface row into ('rj45' | 'sfp_plus', port_ordinal) or None if virtual."""
    if if_type == 161:  # ieee8023adLag
        return None
    candidate = (if_name or if_descr or "").strip()
    if not candidate or _LAG_RE.match(candidate):
        return None
    m_rj = _HISGMII_RE.match(candidate)
    if m_rj:
        return ("rj45", int(m_rj.group(1)))
    m_sfp = _TENGIG_RE.match(candidate)
    if m_sfp:
        return ("sfp_plus", int(m_sfp.group(1)))
    return None


def discover_port_mapping(
    interfaces: dict[int, dict[str, Any]],
    manual_ifindex_map: dict[str, int] | None = None,
    port_aliases: dict[str, str] | None = None,
) -> list[PortMappingEntry]:
    """Discover and bind the 12 physical ports from live IF-MIB interface rows.

    Uses multi-field matching (ifIndex, ifDescr, ifName, ifType) instead of
    blindly assuming ifIndex 1..12, and applies optional manual overrides.
    """
    manual_ifindex_map = manual_ifindex_map or {}
    port_aliases = port_aliases or {}

    discovered_rj45: dict[int, tuple[int, str, str]] = {}
    discovered_sfp: dict[int, tuple[int, str, str]] = {}

    for if_idx, row in sorted(interfaces.items()):
        descr = str(row.get("if_descr") or "").strip()
        name = str(row.get("if_name") or "").strip()
        if_type = int(row.get("if_type") or 0)
        alias = str(row.get("if_alias") or "").strip()
        classified = _classify_interface(descr, name, if_type)
        if not classified:
            continue
        ptype, ordinal = classified
        iface_label = name or descr or f"ifIndex-{if_idx}"
        if ptype == "rj45":
            discovered_rj45[ordinal] = (if_idx, iface_label, alias)
        elif ptype == "sfp_plus":
            discovered_sfp[ordinal] = (if_idx, iface_label, alias)

    used_if_indices: set[int] = set()
    entries: list[PortMappingEntry] = []

    for spec in CANONICAL_PORTS:
        phys = str(spec["physical_port"])
        slot = int(spec["slot"])
        ptype = str(spec["type"])
        max_spd = int(spec["max_speed_mbps"])
        ordinal = slot if ptype == "rj45" else slot - 8

        override_idx = manual_ifindex_map.get(phys)
        if override_idx is not None and int(override_idx) > 0:
            idx = int(override_idx)
            row = interfaces.get(idx, {})
            iface_name = str(row.get("if_name") or row.get("if_descr") or spec["default_if_name"])
            snmp_alias = str(row.get("if_alias") or "").strip()
        else:
            bucket = discovered_rj45 if ptype == "rj45" else discovered_sfp
            if ordinal in bucket:
                idx, iface_name, snmp_alias = bucket[ordinal]
            else:
                idx = None
                iface_name = str(spec["default_if_name"])
                snmp_alias = ""

        # Guard against duplicate ifIndex bindings across ports
        if idx is not None:
            if idx in used_if_indices:
                idx = None
            else:
                used_if_indices.add(idx)

        custom_alias = str(port_aliases.get(phys) or "").strip()
        resolved_alias = custom_alias or snmp_alias

        entries.append(
            PortMappingEntry(
                physical_port=phys,
                slot=slot,
                port_type=ptype,
                max_speed_mbps=max_spd,
                if_index=idx,
                interface_name=iface_name,
                alias=resolved_alias,
            )
        )

    return entries
