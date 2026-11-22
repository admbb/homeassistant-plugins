# NetFlow Plus

Home Assistant integration for the locally hosted MikroTik Home NetFlow Plus
service. It reads the authenticated /api/v1/status and
/api/v1/domains/app-ranking endpoints.

## Entities

- Engine status and the age of the latest flow export.
- Number of ranked applications and the current top application.
- The ranking entity exposes up to ten application rows as attributes.

The integration reads telemetry only. It sends a password to /api/v1/login
to create a session; all telemetry requests use GET. It does not change
RouterOS, exporters, firewall rules, or NetFlow Plus settings.

## Install

Copy this directory to config/custom_components/netflow_plus/, restart Home
Assistant, then add NetFlow Plus from Settings → Devices & services → Add
integration.

The default URL is http://192.168.100.36:8080. Enter the NetFlow Plus web
password in the setup form. The integration validates the password and status
endpoint before creating the config entry.
