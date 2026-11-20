"""Read-only async SNMPv1/v2c client for Sirivision SR-S25G3412F."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    bulk_walk_cmd,
    get_cmd,
    walk_cmd,
)

from .const import (
    OID_DOT1D_BASE_PORT_IFINDEX,
    OID_DOT1Q_PVID,
    OID_DOT1Q_TP_FDB_PORT,
    OID_DOT1Q_VLAN_CURRENT_EGRESS,
    OID_DOT1Q_VLAN_CURRENT_UNTAGGED,
    OID_DOT1Q_VLAN_STATIC_NAME,
    OID_DOT3_DUPLEX_STATUS,
    OID_IF_ADMIN_STATUS,
    OID_IF_ALIAS,
    OID_IF_DESCR,
    OID_IF_HC_IN_OCTETS,
    OID_IF_HC_OUT_OCTETS,
    OID_IF_HIGH_SPEED,
    OID_IF_IN_DISCARDS,
    OID_IF_IN_ERRORS,
    OID_IF_IN_OCTETS,
    OID_IF_INDEX,
    OID_IF_MTU,
    OID_IF_NAME,
    OID_IF_NUMBER,
    OID_IF_OPER_STATUS,
    OID_IF_OUT_DISCARDS,
    OID_IF_OUT_ERRORS,
    OID_IF_OUT_OCTETS,
    OID_IF_SPEED,
    OID_IF_TYPE,
    OID_SYS_CONTACT,
    OID_SYS_DESCR,
    OID_SYS_LOCATION,
    OID_SYS_NAME,
    OID_SYS_OBJECT_ID,
    OID_SYS_UPTIME,
    SNMP_VERSION_TO_MP_MODEL,
)

_LOGGER = logging.getLogger(__name__)

_SNMP_ENGINE: SnmpEngine | None = None
_ENGINE_LOCK = asyncio.Lock()


def _create_engine() -> SnmpEngine:
    """Create and warm SnmpEngine inside executor thread so event loop never blocks."""
    engine = SnmpEngine()
    mib_builder = engine.get_mib_builder()
    for mod in (
        "SNMPv2-SMI",
        "SNMPv2-TC",
        "SNMPv2-CONF",
        "SNMPv2-TM",
        "SNMPv2-MIB",
        "PYSNMP-SOURCE-MIB",
        "__SNMPv2-MIB",
    ):
        try:
            mib_builder.load_modules(mod)
        except Exception:  # noqa: BLE001
            pass

    for src in mib_builder.get_mib_sources():
        src_dir = getattr(src, "_srcName", None)
        if not src_dir or not os.path.isdir(src_dir):
            continue
        for _root, _dirs, files in os.walk(src_dir):
            for fname in files:
                if fname.endswith(".py") and fname != "__init__.py":
                    try:
                        mib_builder.load_modules(os.path.splitext(fname)[0])
                    except Exception:  # noqa: BLE001
                        pass
    return engine


async def async_get_snmp_engine(hass: Any) -> SnmpEngine:
    """Return shared warmed SnmpEngine singleton."""
    global _SNMP_ENGINE
    async with _ENGINE_LOCK:
        if _SNMP_ENGINE is None:
            _SNMP_ENGINE = await hass.async_add_executor_job(_create_engine)
    return _SNMP_ENGINE


def _parse_raw_val(val: Any) -> Any:
    """Convert pysnmp varbind value cleanly to Python str/int."""
    if val is None:
        return None
    # OctetString bytes formatting for printable vs MAC/bitmask
    try:
        raw_bytes = val.asOctets()
        if all(32 <= b <= 126 for b in raw_bytes):
            return raw_bytes.decode("utf-8", errors="replace")
        return raw_bytes.hex()
    except Exception:  # noqa: BLE001
        pass
    try:
        return int(val)
    except Exception:  # noqa: BLE001
        pass
    return val.prettyPrint()


class SirivisionSnmpClient:
    """Async read-only SNMP client with GET/WALK helpers."""

    def __init__(
        self,
        hass: Any,
        host: str,
        port: int,
        community: str,
        snmp_version: str = "v2c",
        timeout: float = 3.0,
        retries: int = 1,
    ) -> None:
        self.hass = hass
        self.host = host
        self.port = int(port)
        self._community = community
        self.mp_model = SNMP_VERSION_TO_MP_MODEL.get(snmp_version, 1)
        self.timeout = timeout
        self.retries = retries

    async def _make_transport(self) -> UdpTransportTarget:
        return await UdpTransportTarget.create(
            (self.host, self.port),
            timeout=self.timeout,
            retries=self.retries,
        )

    async def get_scalars(self, oids: list[str]) -> dict[str, Any]:
        """Fetch multiple scalar OIDs in one SNMP GetRequest."""
        if not oids:
            return {}
        engine = await async_get_snmp_engine(self.hass)
        transport = await self._make_transport()
        obj_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]

        err_ind, err_stat, _err_idx, var_binds = await get_cmd(
            engine,
            CommunityData(self._community, mpModel=self.mp_model),
            transport,
            ContextData(),
            *obj_types,
        )
        if err_ind:
            raise ConnectionError(f"SNMP GET failed on {self.host}: {err_ind}")
        if err_stat:
            raise RuntimeError(f"SNMP GET error status on {self.host}: {err_stat.prettyPrint()}")

        result: dict[str, Any] = {}
        for oid_var, val in var_binds:
            s_val = str(val.prettyPrint())
            if s_val in ("No Such Object currently exists at this OID", "No Such Instance currently exists at this OID"):
                continue
            result[str(oid_var)] = _parse_raw_val(val)
        return result

    async def walk_table(
        self, base_oid: str, max_items: int = 400, *, octets_as_hex: bool = False
    ) -> dict[str, Any]:
        """Walk an SNMP subtree cleanly (GetBulk for v2c, GetNext fallback for v1)."""
        engine = await async_get_snmp_engine(self.hass)
        transport = await self._make_transport()
        prefix = base_oid + "."
        out: dict[str, Any] = {}

        if self.mp_model == 1:
            iterator = bulk_walk_cmd(
                engine,
                CommunityData(self._community, mpModel=1),
                transport,
                ContextData(),
                0,
                25,
                ObjectType(ObjectIdentity(base_oid)),
                lexicographicMode=False,
                ignoreNonIncreasingOid=True,
            )
        else:
            iterator = walk_cmd(
                engine,
                CommunityData(self._community, mpModel=0),
                transport,
                ContextData(),
                ObjectType(ObjectIdentity(base_oid)),
                lexicographicMode=False,
                ignoreNonIncreasingOid=True,
            )

        async for err_ind, err_stat, _err_idx, var_binds in iterator:
            if err_ind:
                raise ConnectionError(f"SNMP WALK failed on {self.host} ({base_oid}): {err_ind}")
            if err_stat:
                break
            for oid_var, val in var_binds:
                oid_str = str(oid_var)
                if not oid_str.startswith(prefix) and oid_str != base_oid:
                    return out
                if octets_as_hex:
                    try:
                        out[oid_str] = val.asOctets().hex()
                    except (AttributeError, TypeError, ValueError):
                        continue
                else:
                    out[oid_str] = _parse_raw_val(val)
                if len(out) >= max_items:
                    return out
        return out

    async def fetch_device_info(self) -> dict[str, Any]:
        """Read standard System MIB scalars."""
        scalars = await self.get_scalars(
            [
                OID_SYS_DESCR,
                OID_SYS_OBJECT_ID,
                OID_SYS_UPTIME,
                OID_SYS_CONTACT,
                OID_SYS_NAME,
                OID_SYS_LOCATION,
                OID_IF_NUMBER,
            ]
        )
        return {
            "sys_descr": str(scalars.get(OID_SYS_DESCR) or "SR-S25G3412F").strip(),
            "sys_object_id": str(scalars.get(OID_SYS_OBJECT_ID) or "").strip(),
            "sys_uptime_ticks": _to_int(scalars.get(OID_SYS_UPTIME)),
            "sys_contact": str(scalars.get(OID_SYS_CONTACT) or "").strip(),
            "sys_name": str(scalars.get(OID_SYS_NAME) or "Switch").strip(),
            "sys_location": str(scalars.get(OID_SYS_LOCATION) or "").strip(),
            "if_number": _to_int(scalars.get(OID_IF_NUMBER)),
        }

    async def fetch_interface_inventory(self) -> dict[int, dict[str, Any]]:
        """Discover all interfaces with descriptors, names, types, aliases, MTU."""
        idx_map, descr_map, name_map, type_map, alias_map, mtu_map = await asyncio.gather(
            self.walk_table(OID_IF_INDEX, 100),
            self.walk_table(OID_IF_DESCR, 100),
            self.walk_table(OID_IF_NAME, 100),
            self.walk_table(OID_IF_TYPE, 100),
            self.walk_table(OID_IF_ALIAS, 100),
            self.walk_table(OID_IF_MTU, 100),
        )
        interfaces: dict[int, dict[str, Any]] = {}
        for oid, val in idx_map.items():
            idx = _to_int(val) or _suffix_int(oid)
            if idx is not None:
                interfaces[idx] = {"if_index": idx}

        def merge(tbl: dict[str, Any], key: str, as_int: bool = False) -> None:
            for oid, val in tbl.items():
                idx = _suffix_int(oid)
                if idx is None:
                    continue
                interfaces.setdefault(idx, {"if_index": idx})
                interfaces[idx][key] = _to_int(val) if as_int else str(val or "").strip()

        merge(descr_map, "if_descr")
        merge(name_map, "if_name")
        merge(type_map, "if_type", as_int=True)
        merge(alias_map, "if_alias")
        merge(mtu_map, "if_mtu", as_int=True)
        return interfaces

    async def fetch_traffic_counters(self) -> tuple[dict[int, dict[str, int]], int | None, bool]:
        """Fetch sysUpTime + 64-bit ifHC* octets (with 32-bit fallback if unsupported)."""
        scalars, hc_in, hc_out = await asyncio.gather(
            self.get_scalars([OID_SYS_UPTIME]),
            self.walk_table(OID_IF_HC_IN_OCTETS, 100),
            self.walk_table(OID_IF_HC_OUT_OCTETS, 100),
        )
        uptime_ticks = _to_int(scalars.get(OID_SYS_UPTIME))
        is_64bit = bool(hc_in and hc_out)

        if not is_64bit:
            hc_in, hc_out = await asyncio.gather(
                self.walk_table(OID_IF_IN_OCTETS, 100),
                self.walk_table(OID_IF_OUT_OCTETS, 100),
            )

        counters: dict[int, dict[str, int]] = {}
        for oid, val in hc_in.items():
            idx = _suffix_int(oid)
            v = _to_int(val)
            if idx is not None and v is not None:
                counters.setdefault(idx, {})["rx_bytes"] = v
        for oid, val in hc_out.items():
            idx = _suffix_int(oid)
            v = _to_int(val)
            if idx is not None and v is not None:
                counters.setdefault(idx, {})["tx_bytes"] = v

        return counters, uptime_ticks, is_64bit

    async def fetch_port_status_and_errors(self) -> dict[int, dict[str, Any]]:
        """Fetch admin/oper status, speed, highSpeed, duplex, error & discard counters."""
        adm, oper, spd, hspd, dup, in_err, out_err, in_disc, out_disc = await asyncio.gather(
            self.walk_table(OID_IF_ADMIN_STATUS, 100),
            self.walk_table(OID_IF_OPER_STATUS, 100),
            self.walk_table(OID_IF_SPEED, 100),
            self.walk_table(OID_IF_HIGH_SPEED, 100),
            self.walk_table(OID_DOT3_DUPLEX_STATUS, 100),
            self.walk_table(OID_IF_IN_ERRORS, 100),
            self.walk_table(OID_IF_OUT_ERRORS, 100),
            self.walk_table(OID_IF_IN_DISCARDS, 100),
            self.walk_table(OID_IF_OUT_DISCARDS, 100),
        )
        rows: dict[int, dict[str, Any]] = {}

        def put(tbl: dict[str, Any], key: str) -> None:
            for oid, val in tbl.items():
                idx = _suffix_int(oid)
                v = _to_int(val)
                if idx is not None and v is not None:
                    rows.setdefault(idx, {})[key] = v

        put(adm, "admin_status")
        put(oper, "oper_status")
        put(spd, "if_speed")
        put(hspd, "if_high_speed")
        put(dup, "duplex")
        put(in_err, "in_errors")
        put(out_err, "out_errors")
        put(in_disc, "in_discards")
        put(out_disc, "out_discards")
        return rows

    async def fetch_vlan_and_mac_table(self) -> dict[str, Any]:
        """Fetch Q-BRIDGE-MIB PVIDs, VLAN static names, egress/untagged port masks, and MAC FDB."""
        bridge_map_raw, pvid_raw, vlan_names_raw, egress_raw, untagged_raw, mac_fdb_raw = await asyncio.gather(
            self.walk_table(OID_DOT1D_BASE_PORT_IFINDEX, 100),
            self.walk_table(OID_DOT1Q_PVID, 100),
            self.walk_table(OID_DOT1Q_VLAN_STATIC_NAME, 128),
            self.walk_table(OID_DOT1Q_VLAN_CURRENT_EGRESS, 128, octets_as_hex=True),
            self.walk_table(OID_DOT1Q_VLAN_CURRENT_UNTAGGED, 128, octets_as_hex=True),
            self.walk_table(OID_DOT1Q_TP_FDB_PORT, 400),
        )

        bridge_port_to_ifindex: dict[int, int] = {}
        for oid, val in bridge_map_raw.items():
            bp = _suffix_int(oid)
            ifi = _to_int(val)
            if bp is not None and ifi is not None:
                bridge_port_to_ifindex[bp] = ifi

        pvid_by_ifindex: dict[int, int] = {}
        for oid, val in pvid_raw.items():
            bp = _suffix_int(oid)
            v = _to_int(val)
            if bp is not None and v is not None:
                ifi = bridge_port_to_ifindex.get(bp, bp)
                pvid_by_ifindex[ifi] = v

        vlans: dict[int, dict[str, Any]] = {}
        for oid, val in vlan_names_raw.items():
            vid = _suffix_int(oid)
            if vid is not None:
                vlans[vid] = {"vlan_id": vid, "name": str(val or f"VLAN {vid}").strip()}

        def decode_portlist(hex_str: Any) -> list[int]:
            if not isinstance(hex_str, str):
                return []
            try:
                raw = bytes.fromhex(hex_str)
            except ValueError:
                return []
            out_ifs: list[int] = []
            for byte_idx, byte_val in enumerate(raw):
                for bit_idx in range(8):
                    if byte_val & (1 << (7 - bit_idx)):
                        bp = byte_idx * 8 + bit_idx + 1
                        ifi = bridge_port_to_ifindex.get(bp, bp)
                        if ifi <= 100:  # ignore virtual LAG placeholders above 100
                            out_ifs.append(ifi)
            return out_ifs

        for oid, val in egress_raw.items():
            vid = _suffix_int(oid)
            if vid is not None:
                vlans.setdefault(vid, {"vlan_id": vid, "name": f"VLAN {vid}"})
                vlans[vid]["egress_if_indices"] = decode_portlist(val)
        for oid, val in untagged_raw.items():
            vid = _suffix_int(oid)
            if vid is not None:
                vlans.setdefault(vid, {"vlan_id": vid, "name": f"VLAN {vid}"})
                vlans[vid]["untagged_if_indices"] = decode_portlist(val)

        # MAC entries: OID ends with .<fdbId>.<6 MAC octets>
        mac_entries: list[dict[str, Any]] = []
        prefix_len = len(OID_DOT1Q_TP_FDB_PORT.split("."))
        for oid, val in mac_fdb_raw.items():
            bp = _to_int(val)
            if bp is None or bp <= 0:
                continue
            parts = oid.split(".")
            tail = parts[prefix_len:]
            # Expected: <fdbId>.<m1>.<m2>.<m3>.<m4>.<m5>.<m6> OR with len prefix 6
            if len(tail) == 7:
                fdb_id = int(tail[0])
                mac_octets = tail[1:7]
            elif len(tail) == 8 and tail[1] == "6":
                fdb_id = int(tail[0])
                mac_octets = tail[2:8]
            else:
                continue
            try:
                mac = ":".join(f"{int(x):02x}" for x in mac_octets)
            except ValueError:
                continue
            ifi = bridge_port_to_ifindex.get(bp, bp)
            mac_entries.append({"mac": mac, "vlan_id": fdb_id, "if_index": ifi})

        return {
            "pvid_by_ifindex": pvid_by_ifindex,
            "vlans": sorted(vlans.values(), key=lambda x: x["vlan_id"]),
            "mac_entries": mac_entries,
        }


def _suffix_int(oid: str) -> int | None:
    try:
        return int(oid.rsplit(".", 1)[-1])
    except (ValueError, IndexError):
        return None


def _to_int(val: Any) -> int | None:
    if val is None:
        return None
    if isinstance(val, int):
        return val
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return None
