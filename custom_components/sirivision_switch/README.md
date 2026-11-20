# Sirivision SR-S25G3412F Switch

Home Assistant custom integration for read-only monitoring of a Sirivision
SR-S25G3412F managed switch over SNMP v1 or v2c.

## Features

- Reports switch identity and SNMP connectivity.
- Monitors port link and administrative state, traffic rates, errors, and
  discards.
- Reads VLAN membership and the MAC address table for the Lovelace card.
- Provides an optional custom Lovelace card with port, VLAN, and traffic views.
- Supports per-port aliases, ifIndex mapping, and independent polling intervals.
- Uses MDI icons for switch health, ports, and network traffic.

The integration performs read-only SNMP requests. It does not change switch
configuration.

## Installation

Copy `custom_components/sirivision_switch` into the `custom_components`
directory in your Home Assistant configuration, then restart Home Assistant.

Add the integration from **Settings → Devices & services → Add integration**.
Enter the switch address, SNMP port, community string, SNMP version, and a
device name. The switch must allow SNMP access from Home Assistant.

The integration copies the Lovelace card into `/config/www/sirivision_switch/`
and registers `/local/sirivision_switch/sirivision-switch-card.js` as a module
resource when Lovelace storage mode is enabled. If it is not registered, add
that `/local/` URL as a JavaScript module resource in Lovelace.

## Configuration options

The integration options allow you to set polling intervals, assign port
aliases, and map physical port labels to SNMP ifIndex values. These options
preserve the existing config entry and entity identifiers.
