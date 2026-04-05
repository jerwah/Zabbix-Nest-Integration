#!/usr/bin/env python3
"""
nest_to_zabbix.py — Google Nest SDM API to Zabbix helper script
================================================================
Connects to the Google Smart Device Management (SDM) API, retrieves
thermostat data, and outputs values in a format Zabbix can consume
via an External Check item.

Tested on:
  - Zabbix 7.4.8
  - Ubuntu/Debian (runs as the 'zabbix' OS user)
  - Google SDM API (as of April 2026)

NOTE: Google frequently changes SDM API authentication steps.
If authentication fails, check the README for the most recent
setup instructions and verify your credentials are current.

Usage:
  python3 nest_to_zabbix.py --metric <metric_name> [--device <device_id>]

  Metrics:
    current_temp    Current ambient temperature (Celsius)
    set_temp        Target/set temperature (Celsius)
    humidity        Current relative humidity (%)
    mode            Current thermostat mode (e.g. MANUAL_ECO, HEAT, COOL, OFF)

  Device ID:
    Optional. If omitted and only one thermostat exists, it will be used.
    If multiple thermostats exist, --device is required.

Credentials:
  Read from: /etc/zabbix/nest_to_zabbix.conf
  (Restricted to the 'zabbix' OS user — see README for setup instructions)

Author: jerwah (https://github.com/jerwah)
License: MIT
"""

# =============================================================
# THIS IS A PLACEHOLDER — implementation comes next phase.
# See README.md for the full development roadmap.
# =============================================================

import argparse
import sys

# Placeholder — will be replaced with real implementation
def main():
    parser = argparse.ArgumentParser(
        description="Retrieve Google Nest thermostat data for Zabbix"
    )
    parser.add_argument(
        "--metric",
        required=True,
        choices=["current_temp", "set_temp", "humidity", "mode"],
        help="The metric to retrieve"
    )
    parser.add_argument(
        "--device",
        required=False,
        default=None,
        help="Device ID (required when monitoring multiple thermostats)"
    )
    args = parser.parse_args()

    # Placeholder output — real API calls will replace this block
    print(f"PLACEHOLDER: metric={args.metric}, device={args.device}")
    print("Script not yet implemented. See README for development status.")
    sys.exit(1)


if __name__ == "__main__":
    main()
