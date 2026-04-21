# Privacy Policy

**Zabbix Nest Monitor** is an open-source tool that uses the Google Smart Device
Management (SDM) API to read thermostat data from your Google Nest devices and forward
it to your local Zabbix monitoring server.

**No data is collected, transmitted, or stored by the developer.**

- All communication is directly between your Zabbix server and the Google SDM API.
- OAuth credentials (refresh tokens, access tokens) are stored only on your own server
  at `/etc/zabbix/nest_to_zabbix.conf`, accessible only to the local `zabbix` OS user.
- The developer has no server, no backend, and no access to your account, tokens, or
  thermostat data.

The full source code is publicly auditable at:
https://github.com/jerwah/Zabbix-Nest-Integration

For questions, open an issue on GitHub.
