"""Constants for Sirivision SR-S25G3412F Switch integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "sirivision_switch"
PLATFORMS: Final = ["sensor"]

DEFAULT_NAME: Final = "希力威视 SR-S25G3412F"
DEFAULT_SNMP_PORT: Final = 161
DEFAULT_SNMP_VERSION: Final = "v2c"
DEFAULT_POLL_TRAFFIC: Final = 5
DEFAULT_POLL_STATUS: Final = 10
DEFAULT_POLL_VLAN_MAC: Final = 60
DEFAULT_POLL_DEVICE_INFO: Final = 300

CONF_HOST: Final = "host"
CONF_SNMP_PORT: Final = "snmp_port"
CONF_COMMUNITY: Final = "community"
CONF_SNMP_VERSION: Final = "snmp_version"
CONF_DEVICE_NAME: Final = "device_name"
CONF_POLL_TRAFFIC: Final = "poll_traffic"
CONF_POLL_STATUS: Final = "poll_status"
CONF_POLL_VLAN_MAC: Final = "poll_vlan_mac"
CONF_POLL_DEVICE_INFO: Final = "poll_device_info"
CONF_PORT_ALIASES: Final = "port_aliases"
CONF_PORT_IFINDEX_MAP: Final = "port_ifindex_map"

# Standard MIB OIDs verified against SR-S25G3412F (1.3.6.1.4.1.27282.3.2.10)
OID_SYS_DESCR: Final = "1.3.6.1.2.1.1.1.0"
OID_SYS_OBJECT_ID: Final = "1.3.6.1.2.1.1.2.0"
OID_SYS_UPTIME: Final = "1.3.6.1.2.1.1.3.0"
OID_SYS_CONTACT: Final = "1.3.6.1.2.1.1.4.0"
OID_SYS_NAME: Final = "1.3.6.1.2.1.1.5.0"
OID_SYS_LOCATION: Final = "1.3.6.1.2.1.1.6.0"
OID_IF_NUMBER: Final = "1.3.6.1.2.1.2.1.0"

OID_IF_INDEX: Final = "1.3.6.1.2.1.2.2.1.1"
OID_IF_DESCR: Final = "1.3.6.1.2.1.2.2.1.2"
OID_IF_TYPE: Final = "1.3.6.1.2.1.2.2.1.3"
OID_IF_MTU: Final = "1.3.6.1.2.1.2.2.1.4"
OID_IF_SPEED: Final = "1.3.6.1.2.1.2.2.1.5"
OID_IF_PHYS_ADDR: Final = "1.3.6.1.2.1.2.2.1.6"
OID_IF_ADMIN_STATUS: Final = "1.3.6.1.2.1.2.2.1.7"
OID_IF_OPER_STATUS: Final = "1.3.6.1.2.1.2.2.1.8"
OID_IF_IN_OCTETS: Final = "1.3.6.1.2.1.2.2.1.10"
OID_IF_IN_DISCARDS: Final = "1.3.6.1.2.1.2.2.1.13"
OID_IF_IN_ERRORS: Final = "1.3.6.1.2.1.2.2.1.14"
OID_IF_OUT_OCTETS: Final = "1.3.6.1.2.1.2.2.1.16"
OID_IF_OUT_DISCARDS: Final = "1.3.6.1.2.1.2.2.1.19"
OID_IF_OUT_ERRORS: Final = "1.3.6.1.2.1.2.2.1.20"

OID_IF_NAME: Final = "1.3.6.1.2.1.31.1.1.1.1"
OID_IF_HC_IN_OCTETS: Final = "1.3.6.1.2.1.31.1.1.1.6"
OID_IF_HC_OUT_OCTETS: Final = "1.3.6.1.2.1.31.1.1.1.10"
OID_IF_HIGH_SPEED: Final = "1.3.6.1.2.1.31.1.1.1.15"
OID_IF_ALIAS: Final = "1.3.6.1.2.1.31.1.1.1.18"

OID_DOT3_DUPLEX_STATUS: Final = "1.3.6.1.2.1.10.7.2.1.19"
OID_DOT1D_BASE_PORT_IFINDEX: Final = "1.3.6.1.2.1.17.1.4.1.2"
OID_DOT1Q_TP_FDB_PORT: Final = "1.3.6.1.2.1.17.7.1.2.2.1.2"
OID_DOT1Q_TP_FDB_STATUS: Final = "1.3.6.1.2.1.17.7.1.2.2.1.3"
OID_DOT1Q_VLAN_STATIC_NAME: Final = "1.3.6.1.2.1.17.7.1.4.3.1.1"
OID_DOT1Q_VLAN_CURRENT_EGRESS: Final = "1.3.6.1.2.1.17.7.1.4.2.1.4"
OID_DOT1Q_VLAN_CURRENT_UNTAGGED: Final = "1.3.6.1.2.1.17.7.1.4.2.1.5"
OID_DOT1Q_PVID: Final = "1.3.6.1.2.1.17.7.1.4.5.1.1"

SNMP_VERSION_TO_MP_MODEL: Final[dict[str, int]] = {
    "v1": 0,
    "v2c": 1,
}

OPER_STATUS_MAP: Final[dict[int, tuple[str, str]]] = {
    1: ("up", "已连接"),
    2: ("down", "未连接"),
    3: ("testing", "测试中"),
    4: ("unknown", "未知"),
    5: ("dormant", "休眠"),
    6: ("not_present", "不存在"),
    7: ("lower_layer_down", "下层断开"),
}

ADMIN_STATUS_MAP: Final[dict[int, tuple[str, str]]] = {
    1: ("up", "启用"),
    2: ("down", "已禁用"),
    3: ("testing", "测试中"),
}

DUPLEX_STATUS_MAP: Final[dict[int, str]] = {
    1: "未知",
    2: "半双工",
    3: "全双工",
}

VALID_REPORTED_SPEEDS_MBPS: Final[frozenset[int]] = frozenset(
    {10, 100, 1000, 2500, 5000, 10000, 25000, 40000, 100000}
)

# Canonical 12-port specification for SR-S25G3412F
CANONICAL_PORTS: Final[list[dict[str, object]]] = [
    *[
        {
            "physical_port": f"RJ45-{i:02d}",
            "slot": i,
            "type": "rj45",
            "max_speed_mbps": 2500,
            "default_if_index": i,
            "default_if_name": f"HisgmiiEthernet{i}",
        }
        for i in range(1, 9)
    ],
    *[
        {
            "physical_port": f"SFP+-{i:02d}",
            "slot": 8 + i,
            "type": "sfp_plus",
            "max_speed_mbps": 10000,
            "default_if_index": 8 + i,
            "default_if_name": f"TenGigabitEthernet{i}",
        }
        for i in range(1, 5)
    ],
]

FRONTEND_JS_FILENAME: Final = "sirivision-switch-card.js"
FRONTEND_RESOURCE_URL: Final = f"/local/sirivision_switch/{FRONTEND_JS_FILENAME}"
