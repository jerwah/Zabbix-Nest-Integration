#!/usr/bin/env python3
"""
nest_auth_setup.py — Interactive setup wizard for nest_to_zabbix
=================================================================
Guides you through the Google OAuth2 authorization flow, exchanges
credentials for a refresh token, writes /etc/zabbix/nest_to_zabbix.conf,
locks it down, and confirms the integration is working — all in one run.

Must be run as root (or via sudo) so it can write to /etc/zabbix/.

Usage:
  sudo python3 scripts/nest_auth_setup.py

Author: jerwah (https://github.com/jerwah)
License: MIT
"""

import configparser
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# -----------------------------------------------------------------
# Version
# -----------------------------------------------------------------
__version__ = "0.2.0"

# -----------------------------------------------------------------
# Constants (must match nest_to_zabbix.py)
# -----------------------------------------------------------------
CONFIG_PATH   = "/etc/zabbix/nest_to_zabbix.conf"
TOKEN_URL     = "https://oauth2.googleapis.com/token"
SDM_BASE_URL  = "https://smartdevicemanagement.googleapis.com/v1"
REDIRECT_URI  = "https://www.google.com"
SCOPE         = "https://www.googleapis.com/auth/sdm.service"
THERMOSTAT_TYPE = "sdm.devices.types.THERMOSTAT"
REQUEST_TIMEOUT = 15


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------
def banner(text):
    width = 70
    print()
    print("=" * width)
    print(f"  {text}")
    print("=" * width)


def step(n, text):
    print(f"\n[Step {n}] {text}")
    print("-" * 60)


def info(text):
    print(f"  {text}")


def success(text):
    print(f"  ✓  {text}")


def warn(text):
    print(f"  ⚠  {text}")


def fatal(text):
    print(f"\nERROR: {text}", file=sys.stderr)
    sys.exit(1)


def prompt(label, hint=None, default=None, secret=False):
    """Prompt the user for a value, retrying until non-empty.

    If default is provided, it is shown in brackets and accepted on Enter.
    """
    if hint:
        print(f"  ({hint})")
    if default:
        display_default = "****" + default[-4:] if secret else default
        label_str = f"  {label} [{display_default}]: "
    else:
        label_str = f"  {label}: "
    while True:
        try:
            value = input(label_str).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            fatal("Setup cancelled.")
        if not value and default:
            return default
        if value:
            return value
        print("  Value cannot be empty — please try again.")


def confirm(question):
    """Ask a yes/no question; return True for yes."""
    while True:
        try:
            answer = input(f"  {question} [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            fatal("Setup cancelled.")
        if answer in ("y", "yes"):
            return True
        if answer in ("", "n", "no"):
            return False
        print("  Please enter y or n.")


# -----------------------------------------------------------------
# Existing config loader
# -----------------------------------------------------------------
def load_existing_config():
    """Return the [google_sdm] section of an existing config, or None."""
    if not os.path.exists(CONFIG_PATH):
        return None
    cfg = configparser.ConfigParser()
    try:
        cfg.read(CONFIG_PATH)
        if "google_sdm" in cfg:
            return dict(cfg["google_sdm"])
    except Exception:
        pass
    return None


# -----------------------------------------------------------------
# Google API calls
# -----------------------------------------------------------------
def exchange_auth_code(client_id, client_secret, code):
    """Exchange a one-time authorization code for access + refresh tokens."""
    payload = urllib.parse.urlencode({
        "grant_type":    "authorization_code",
        "client_id":     client_id,
        "client_secret": client_secret,
        "code":          code,
        "redirect_uri":  REDIRECT_URI,
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        fatal(f"Token exchange failed (HTTP {exc.code}): {detail}")
    except urllib.error.URLError as exc:
        fatal(f"Token exchange failed (network error): {exc.reason}")


def list_thermostats(sdm_project_id, access_token):
    """Return all thermostat devices in the SDM project."""
    url = f"{SDM_BASE_URL}/enterprises/{sdm_project_id}/devices"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        fatal(f"SDM API request failed (HTTP {exc.code}): {detail}")
    except urllib.error.URLError as exc:
        fatal(f"SDM API request failed (network error): {exc.reason}")

    devices = data.get("devices", [])
    return [d for d in devices if d.get("type") == THERMOSTAT_TYPE]


def device_display_name(device):
    """Return the best human-readable name for a device."""
    info_trait = device.get("traits", {}).get("sdm.devices.traits.Info", {})
    name = info_trait.get("customName", "").strip()
    if not name:
        relations = device.get("parentRelations", [])
        if relations:
            name = relations[0].get("displayName", "").strip()
    if not name:
        name = device.get("name", "unknown").split("/")[-1]
    return name


# -----------------------------------------------------------------
# Config file writer
# -----------------------------------------------------------------
def write_config(project_id, client_id, client_secret, refresh_token, sdm_project_id):
    """Write the INI config file atomically and lock down permissions."""
    config = configparser.ConfigParser()
    config["google_sdm"] = {
        "project_id":    project_id,
        "client_id":     client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "sdm_project_id": sdm_project_id,
    }

    tmp_path = CONFIG_PATH + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            config.write(f)
        os.replace(tmp_path, CONFIG_PATH)
        os.chown(CONFIG_PATH, _zabbix_uid(), _zabbix_gid())
        os.chmod(CONFIG_PATH, 0o600)
    except OSError as exc:
        # Clean up tmp if it exists
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        fatal(f"Could not write config file: {exc}")


def _zabbix_uid():
    """Return the UID of the 'zabbix' OS user, or current UID as fallback."""
    import pwd
    try:
        return pwd.getpwnam("zabbix").pw_uid
    except KeyError:
        return os.getuid()


def _zabbix_gid():
    """Return the GID of the 'zabbix' OS user, or current GID as fallback."""
    import pwd
    try:
        return pwd.getpwnam("zabbix").pw_gid
    except KeyError:
        return os.getgid()


# -----------------------------------------------------------------
# URL parsing
# -----------------------------------------------------------------
def parse_auth_code(raw):
    """
    Accept either:
      - The full redirect URL  (https://www.google.com/?code=4/0A...&scope=...)
      - Just the code value    (4/0A...)
    Returns the authorization code string.
    """
    raw = raw.strip()
    if raw.startswith("http"):
        parsed = urllib.parse.urlparse(raw)
        params = urllib.parse.parse_qs(parsed.query)
        codes = params.get("code")
        if not codes:
            fatal(
                "Could not find a 'code' parameter in the URL you pasted.\n"
                "  Expected something like: https://www.google.com/?code=4/0A...&scope=...\n"
                "  Paste the full URL from your browser's address bar after the redirect."
            )
        return codes[0]
    # Assume bare code value
    return raw


# -----------------------------------------------------------------
# Main wizard
# -----------------------------------------------------------------
def main():
    banner("Nest → Zabbix  |  Interactive Setup Wizard")

    # ------------------------------------------------------------------
    # Permission check
    # ------------------------------------------------------------------
    if os.geteuid() != 0:
        print()
        warn("This wizard writes to /etc/zabbix/ and must run as root.")
        warn("Re-run with:")
        print()
        print("    sudo python3 scripts/nest_auth_setup.py")
        print()
        sys.exit(1)

    print()
    info("This wizard will:")
    info("  1. Collect your Google Cloud / Device Access credentials")
    info("  2. Walk you through the browser authorization flow")
    info("  3. Exchange your authorization code for a refresh token")
    info(f"  4. Write {CONFIG_PATH} with correct permissions")
    info("  5. Confirm the integration works by listing your thermostats")
    print()
    info("Prerequisites (complete these before continuing):")
    info("  • Google Cloud project with Smart Device Management API enabled")
    info("  • OAuth 2.0 Web application credentials created")
    info("    (redirect URI must include https://www.google.com)")
    info("  • OAuth consent screen configured with sdm.service scope")
    info("  • Google Device Access project created ($5 one-time fee)")
    info("  • Your Google account listed as a test user on the consent screen")
    print()
    info("See README.md Steps 1.1–1.4 if you have not completed these yet.")

    print()
    if not confirm("Ready to continue?"):
        print("  Setup cancelled.")
        sys.exit(0)

    # ------------------------------------------------------------------
    # Step 1 — Collect credentials
    # ------------------------------------------------------------------
    step(1, "Credentials")

    existing = load_existing_config()
    if existing:
        info("Existing config found — press Enter to keep each current value,")
        info("or type a new one to replace it.")
    else:
        info("Enter the values from Google Cloud Console and Device Access Console.")
        info("All values are case-sensitive.")
    print()

    project_id = prompt(
        "Google Cloud Project ID",
        hint="Cloud Console → top bar project dropdown  (e.g. zabbix-nest-123456)",
        default=existing.get("project_id") if existing else None,
    )
    client_id = prompt(
        "OAuth Client ID",
        hint="Cloud Console → APIs & Services → Credentials  (ends in .apps.googleusercontent.com)",
        default=existing.get("client_id") if existing else None,
    )
    client_secret = prompt(
        "OAuth Client Secret",
        hint="Cloud Console → APIs & Services → Credentials",
        default=existing.get("client_secret") if existing else None,
        secret=True,
    )
    sdm_project_id = prompt(
        "Device Access Project ID",
        hint="console.nest.google.com/device-access  ⚠ NOT the Cloud Project ID",
        default=existing.get("sdm_project_id") if existing else None,
    )

    # ------------------------------------------------------------------
    # Step 2 — Build authorization URL
    # ------------------------------------------------------------------
    step(2, "Authorize in your browser")

    auth_url = (
        f"https://nestservices.google.com/partnerconnections/{sdm_project_id}/auth"
        f"?redirect_uri={REDIRECT_URI}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&response_type=code"
        f"&scope={SCOPE}"
        f"&client_id={client_id}"
    )

    info("Open the following URL in a browser while signed in to the Google account")
    info("that owns your Nest thermostat(s).")
    print()
    print(f"  {auth_url}")
    print()
    info("Complete the consent flow:")
    info("  • Allow access to your home")
    info("  • Check every thermostat you want Zabbix to monitor")
    info("  • Approve any 'unverified app' warning (expected for Testing-mode apps)")
    info("  • Click Allow on the final permissions screen")
    print()
    info("After approval, your browser will redirect to google.com.")
    info("The address bar will look like:")
    info("  https://www.google.com/?code=4/0Adxxxxx...&scope=...")
    print()
    info("Copy the ENTIRE URL from the address bar and paste it below.")
    info("(You can also paste just the code= value if you prefer.)")

    # ------------------------------------------------------------------
    # Step 3 — Parse authorization code
    # ------------------------------------------------------------------
    step(3, "Paste the redirect URL (or authorization code)")
    raw_input = prompt("Paste here")
    auth_code = parse_auth_code(raw_input)
    success(f"Authorization code extracted  ({auth_code[:12]}...)")

    # ------------------------------------------------------------------
    # Step 4 — Exchange code for tokens
    # ------------------------------------------------------------------
    step(4, "Exchanging code for tokens")
    info("Contacting Google token endpoint...")

    token_response = exchange_auth_code(client_id, client_secret, auth_code)

    access_token  = token_response.get("access_token")
    refresh_token = token_response.get("refresh_token")

    if not access_token:
        fatal("Token response did not contain an access_token.")
    if not refresh_token:
        fatal(
            "Token response did not contain a refresh_token.\n"
            "  This usually means the authorization code was already used or expired.\n"
            "  Re-run the wizard and complete the browser flow again — codes are one-time use."
        )

    success("Access token received.")
    success("Refresh token received.")

    # ------------------------------------------------------------------
    # Step 5 — Write config
    # ------------------------------------------------------------------
    step(5, f"Writing {CONFIG_PATH}")

    write_config(project_id, client_id, client_secret, refresh_token, sdm_project_id)

    success(f"Config written to {CONFIG_PATH}")

    # Verify ownership/permissions for display
    stat = os.stat(CONFIG_PATH)
    import pwd, grp
    try:
        owner = pwd.getpwuid(stat.st_uid).pw_name
        group = grp.getgrgid(stat.st_gid).gr_name
    except KeyError:
        owner = str(stat.st_uid)
        group = str(stat.st_gid)
    mode = oct(stat.st_mode)[-3:]
    success(f"Permissions: {mode}  owner: {owner}:{group}")

    # ------------------------------------------------------------------
    # Step 6 — Verify with live device list
    # ------------------------------------------------------------------
    step(6, "Verifying — listing your Nest thermostats")
    info("Calling SDM API with the new credentials...")

    thermostats = list_thermostats(sdm_project_id, access_token)

    if not thermostats:
        print()
        warn("No thermostats were returned by the SDM API.")
        warn("This can happen if you did not check any devices during the consent flow.")
        warn("Re-run the wizard and ensure you tick each thermostat on the selection screen.")
        sys.exit(1)

    print()
    success(f"Found {len(thermostats)} thermostat(s):")
    print()
    for dev in thermostats:
        name  = dev.get("name", "unknown")
        label = device_display_name(dev)
        print(f"    Device ID  : {name}")
        print(f"    Room name  : {label}")
        print()

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    banner("Setup complete!")
    print()
    info("Next steps:")
    info("  1. Deploy the script to your Zabbix external scripts directory:")
    info("       sudo cp scripts/nest_to_zabbix.py /usr/lib/zabbix/externalscripts/")
    info("       sudo chmod 755 /usr/lib/zabbix/externalscripts/nest_to_zabbix.py")
    info("  2. Import template/zbx_template_google_nest.yaml into Zabbix")
    info("  3. Create one Zabbix host per thermostat, link the template,")
    info("     and set the {$NEST_DEVICE_ID} macro to the Device ID shown above")
    info("  See README.md Part 2 for full Zabbix setup instructions.")
    print()


if __name__ == "__main__":
    main()
