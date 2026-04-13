#!/usr/bin/env python3
"""
nest_to_zabbix.py — Google Nest SDM API to Zabbix helper script
================================================================
Connects to the Google Smart Device Management (SDM) API, retrieves
thermostat data, and outputs a single value to stdout for Zabbix to
consume via an External Check item.

Tested on:
  - Zabbix 7.4.8
  - Ubuntu/Debian (runs as the 'zabbix' OS user)
  - Google SDM API (as of April 2026)

NOTE: Google frequently changes SDM API authentication steps.
If authentication fails, check the README for the most recent
setup instructions and verify your credentials are current.

Usage:
  python3 nest_to_zabbix.py --metric <metric_name> [--device <device_id>]
  python3 nest_to_zabbix.py --list-devices

  Metrics:
    current_temp    Current ambient temperature (Celsius)
    set_temp        Target/set temperature (Celsius)
    humidity        Current relative humidity (%)
    mode            Current thermostat mode (e.g. MANUAL_ECO, HEAT, COOL, OFF)

  Device ID:
    Optional. If omitted and only one thermostat exists, it will be used
    automatically. If multiple thermostats exist, --device is required.
    Accepts either the full device name or just the trailing device ID segment.

  --list-devices:
    Prints all discovered Nest thermostats with their device IDs and display
    names. Useful for finding the correct value to pass to --device.

Credentials:
  Read from: /etc/zabbix/nest_to_zabbix.conf
  (Restricted to the 'zabbix' OS user — see README for setup instructions)

Output:
  On success : single value printed to stdout, exit code 0
  On failure : error message printed to stderr, exit code 1

Author: jerwah (https://github.com/jerwah)
License: MIT
"""

import argparse
import configparser
import fcntl
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# -----------------------------------------------------------------
# Version
# -----------------------------------------------------------------
__version__ = "0.1.3"

# -----------------------------------------------------------------
# Constants
# -----------------------------------------------------------------
CONFIG_PATH = "/etc/zabbix/nest_to_zabbix.conf"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SDM_BASE_URL = "https://smartdevicemanagement.googleapis.com/v1"
THERMOSTAT_TYPE = "sdm.devices.types.THERMOSTAT"
REQUEST_TIMEOUT = 15  # seconds
CACHE_DIR = "/tmp"
CACHE_TTL = 300  # seconds — one API call per device per 5-minute window


# -----------------------------------------------------------------
# Error handling
# -----------------------------------------------------------------
def error(msg):
    """Print an error message to stderr and exit with code 1."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# -----------------------------------------------------------------
# Config
# -----------------------------------------------------------------
def load_config(path):
    """Parse the INI config file and return the [google_sdm] section."""
    config = configparser.ConfigParser()
    if not config.read(path):
        error(f"Config file not found or not readable: {path}")

    if "google_sdm" not in config:
        error(f"Config file is missing the [google_sdm] section: {path}")

    required_keys = ["project_id", "client_id", "client_secret", "refresh_token", "sdm_project_id"]
    missing = [k for k in required_keys if not config.get("google_sdm", k, fallback="").strip()]
    if missing:
        error(f"Config file is missing required keys: {', '.join(missing)}")

    return config["google_sdm"]


# -----------------------------------------------------------------
# Authentication
# -----------------------------------------------------------------
def _update_refresh_token(new_token):
    """
    Persist a rotated refresh token back to the config file.

    Google may return a new refresh_token alongside the access_token when
    rotating credentials.  If the script discards it the stored token becomes
    invalid on the next rotation, causing an invalid_grant error.
    """
    try:
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH)
        config["google_sdm"]["refresh_token"] = new_token
        tmp_path = CONFIG_PATH + ".tmp"
        with open(tmp_path, "w") as f:
            config.write(f)
        os.replace(tmp_path, CONFIG_PATH)
    except OSError:
        pass  # Non-fatal; old token remains until the next successful rotation


def get_access_token(cfg):
    """Exchange the stored refresh token for a short-lived access token."""
    payload = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "refresh_token": cfg["refresh_token"],
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        error(f"Token refresh failed (HTTP {exc.code}): {detail}")
    except urllib.error.URLError as exc:
        error(f"Token refresh failed (network error): {exc.reason}")

    if "access_token" not in body:
        error("Token endpoint returned a response without an access_token field")

    # Google may rotate the refresh token; persist the new one if present.
    new_refresh_token = body.get("refresh_token")
    if new_refresh_token and new_refresh_token != cfg["refresh_token"]:
        _update_refresh_token(new_refresh_token)
        cfg["refresh_token"] = new_refresh_token

    return body["access_token"]


# -----------------------------------------------------------------
# SDM API helpers
# -----------------------------------------------------------------
def api_get(url, token):
    """Perform an authenticated GET request and return the parsed JSON body."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            error(
                "Rate limit exceeded (HTTP 429) — Google is rejecting requests because "
                "too many API calls are being made. Increase the check interval for Nest "
                "hosts in Zabbix (Data Collection → Hosts → Items) to reduce call frequency."
            )
        detail = exc.read().decode(errors="replace")
        error(f"SDM API request failed (HTTP {exc.code}): {detail}")
    except urllib.error.URLError as exc:
        error(f"SDM API request failed (network error): {exc.reason}")


def list_thermostats(cfg, token):
    """Return a list of all thermostat devices in the SDM project."""
    url = f"{SDM_BASE_URL}/enterprises/{cfg['sdm_project_id']}/devices"
    data = api_get(url, token)
    devices = data.get("devices", [])
    return [d for d in devices if d.get("type") == THERMOSTAT_TYPE]


def get_device(cfg, token, full_name):
    """
    Fetch a single device via the GetDevice API endpoint.

    Expects a full resource name (enterprises/…/devices/…). Avoids calling
    ListDevices — which has a stricter rate limit — when the device is known.
    """
    return api_get(f"{SDM_BASE_URL}/{full_name}", token)


# -----------------------------------------------------------------
# Cache
# -----------------------------------------------------------------
def _cache_path(device_name):
    """Return the cache file path for a device, keyed by its trailing ID segment."""
    device_id = device_name.split("/")[-1]
    return os.path.join(CACHE_DIR, f"nest_zabbix_{device_id}.json")


def _load_cache(device_name):
    """Return cached device data if within TTL, else None."""
    path = _cache_path(device_name)
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if time.time() - data.get("fetched_at", 0) < CACHE_TTL:
            return data["device"]
    except (OSError, KeyError, ValueError):
        pass
    return None


def _save_cache(device_name, device_data):
    """Write device data to cache atomically (os.replace guarantees no partial reads)."""
    path = _cache_path(device_name)
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump({"fetched_at": time.time(), "device": device_data}, f)
        os.replace(tmp_path, path)
        os.chmod(path, 0o600)
    except OSError:
        pass  # Cache write failure is non-fatal; next call will just fetch live


def get_device_cached(cfg, token, full_name):
    """
    Return device data for full_name, serving from a per-device cache when fresh.

    Uses a lock file (fcntl.flock) to ensure that when the cache is stale, only
    one concurrent process fetches from the API.  All others wait for the lock,
    then re-check the cache and serve the freshly written data without making
    additional API calls.

    This reduces N simultaneous Zabbix item checks (N metrics × one script
    invocation each) to a single API call per device per CACHE_TTL window.
    """
    # Fast path: cache is fresh, no locking needed.
    device = _load_cache(full_name)
    if device is not None:
        return device

    # Slow path: acquire exclusive lock, re-check, fetch if still stale.
    lock_path = _cache_path(full_name) + ".lock"
    try:
        lock_file = open(lock_path, "w")
        fcntl.flock(lock_file, fcntl.LOCK_EX)  # blocks until this process owns the lock
        try:
            # Another process may have refreshed while we waited — re-check.
            device = _load_cache(full_name)
            if device is not None:
                return device
            # Still stale: this process is responsible for the API call.
            device = get_device(cfg, token, full_name)
            _save_cache(full_name, device)
            return device
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
    except OSError:
        # Lock file creation failed (e.g. /tmp permissions) — fall back to live fetch.
        return get_device(cfg, token, full_name)


def device_display_name(device):
    """
    Return a human-readable name for a device.

    Priority:
      1. customName from sdm.devices.traits.Info (set via SDM API — rarely populated)
      2. displayName from parentRelations (the room name shown in Google Home app)
      3. Trailing device ID segment as last resort
    """
    info = device.get("traits", {}).get("sdm.devices.traits.Info", {})
    name = info.get("customName", "").strip()
    if not name:
        relations = device.get("parentRelations", [])
        if relations:
            name = relations[0].get("displayName", "").strip()
    if not name:
        name = device.get("name", "unknown").split("/")[-1]
    return name


def resolve_device(thermostats, device_arg):
    """
    Return the single thermostat to monitor.

    If device_arg is provided, match by full resource name or trailing ID.
    If omitted, auto-select when exactly one thermostat exists.
    """
    if len(thermostats) == 0:
        error("No Nest thermostats were found in your account")

    if device_arg:
        for dev in thermostats:
            name = dev.get("name", "")
            if name == device_arg or name.endswith(f"/{device_arg}"):
                return dev
        error(
            f"Device '{device_arg}' not found. "
            "Run --list-devices to see available thermostats."
        )

    if len(thermostats) > 1:
        lines = "\n".join(
            f"  {dev.get('name', 'unknown')}  ({device_display_name(dev)})"
            for dev in thermostats
        )
        error(
            f"Multiple thermostats found — use --device to specify one:\n{lines}"
        )

    return thermostats[0]


def get_trait(device, trait_name):
    """Return a trait dict for the device, or an empty dict if absent."""
    return device.get("traits", {}).get(trait_name, {})


# -----------------------------------------------------------------
# Metric extraction
# -----------------------------------------------------------------
def get_metric(device, metric):
    """
    Extract and return the requested metric value from the device traits.

    Returns a float for numeric metrics or a string for the 'mode' metric.
    Calls error() (and exits) if the trait is unavailable.
    """
    if metric == "current_temp":
        trait = get_trait(device, "sdm.devices.traits.Temperature")
        val = trait.get("ambientTemperatureCelsius")
        if val is None:
            error("Temperature trait is not available for this device")
        return round(float(val), 2)

    if metric == "humidity":
        trait = get_trait(device, "sdm.devices.traits.Humidity")
        val = trait.get("ambientHumidityPercent")
        if val is None:
            error("Humidity trait is not available for this device")
        return round(float(val), 1)

    if metric == "mode":
        # Eco mode is a separate trait that overrides the active HVAC mode.
        eco = get_trait(device, "sdm.devices.traits.ThermostatEco")
        if eco.get("mode") == "MANUAL_ECO":
            return "MANUAL_ECO"
        mode_trait = get_trait(device, "sdm.devices.traits.ThermostatMode")
        val = mode_trait.get("mode")
        if val is None:
            error("ThermostatMode trait is not available for this device")
        return val

    if metric == "set_temp":
        # In eco mode, the eco setpoints take precedence over the normal ones.
        eco = get_trait(device, "sdm.devices.traits.ThermostatEco")
        if eco.get("mode") == "MANUAL_ECO":
            # Return the eco heat setpoint (lower bound); if unavailable try cool.
            for key in ("heatCelsius", "coolCelsius"):
                val = eco.get(key)
                if val is not None:
                    return round(float(val), 2)
            error("Eco mode is active but no eco setpoint is available for this device")

        mode_trait = get_trait(device, "sdm.devices.traits.ThermostatMode")
        mode = mode_trait.get("mode", "")
        setpoint = get_trait(device, "sdm.devices.traits.ThermostatTemperatureSetpoint")

        # HEATCOOL (range) mode reports both bounds; return the heat/lower setpoint.
        if mode in ("HEAT", "HEATCOOL"):
            val = setpoint.get("heatCelsius")
        elif mode == "COOL":
            val = setpoint.get("coolCelsius")
        else:
            # OFF or an unknown mode — there is no meaningful active setpoint.
            error(f"No active setpoint: thermostat is in '{mode}' mode")

        if val is None:
            error(f"Setpoint not available for mode '{mode}'")
        return round(float(val), 2)

    error(f"Unknown metric: {metric}")


# -----------------------------------------------------------------
# CLI
# -----------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Retrieve Google Nest thermostat data for Zabbix"
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--metric",
        choices=["current_temp", "set_temp", "humidity", "mode"],
        help="The metric to retrieve",
    )
    action.add_argument(
        "--list-devices",
        action="store_true",
        help="List all discoverable Nest thermostats and exit",
    )
    parser.add_argument(
        "--device",
        default=None,
        help=(
            "Full device resource name or trailing device ID. "
            "Required when monitoring multiple thermostats."
        ),
    )
    args = parser.parse_args()

    cfg = load_config(CONFIG_PATH)
    token = get_access_token(cfg)

    if args.list_devices:
        thermostats = list_thermostats(cfg, token)
        if not thermostats:
            print("No Nest thermostats found.")
        for dev in thermostats:
            print(f"{dev.get('name', 'unknown')}  ({device_display_name(dev)})")
        sys.exit(0)

    if args.device:
        # Normalize to full resource name before cache lookup.
        if args.device.startswith("enterprises/"):
            full_name = args.device
        else:
            full_name = f"enterprises/{cfg['sdm_project_id']}/devices/{args.device}"
        device = get_device_cached(cfg, token, full_name)
    else:
        # No --device given: fall back to listing all and auto-selecting if exactly one.
        # Cache does not apply here — the caller hasn't specified a device, so we must
        # list to discover which one to use.
        thermostats = list_thermostats(cfg, token)
        device = resolve_device(thermostats, None)

    result = get_metric(device, args.metric)
    print(result)


if __name__ == "__main__":
    main()
