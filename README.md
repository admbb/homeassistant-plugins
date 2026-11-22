# Home Assistant Plugins

Home Assistant custom integrations maintained in this repository.

## Integrations

| Integration | Description | Documentation |
| --- | --- | --- |
| Hitokoto Daily | Daily sentence sensor with history, favorites, and actions | [README](custom_components/hitokoto/README.md) |
| OxiDNS | Read-only health, metrics, query statistics, and optional live events for OxiDNS | [README](custom_components/oxidns/README.md) |
| NetFlow V2 | Read-only observed-flow totals, DNS/app rankings, device ranking, and attribution diagnostics | [README](custom_components/netflow_plus/README.md) |
| Sirivision Switch | Read-only SNMP monitoring for the SR-S25G3412F switch, including ports, traffic, VLANs, and MAC data | [README](custom_components/sirivision_switch/README.md) |

## Manual installation

Copy the integration folder you want from `custom_components/` into the same path in your Home Assistant configuration directory, then restart Home Assistant and add the integration from **Settings → Devices & services → Add integration**.

Each integration has its own README and license file where applicable. Do not copy secrets or Home Assistant configuration data into this repository.

## Brand icons

Home Assistant 2026.3 and newer reads custom integration brand images from each
component's `brand/` directory. Hitokoto Daily, OxiDNS, and Sirivision include
`brand/icon.png`. The WxPusher icon is a supplemental asset for an integration
installed separately; see [brand-assets/README.md](brand-assets/README.md).
