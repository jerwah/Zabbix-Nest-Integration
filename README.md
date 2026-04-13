# Zabbix Template for Monitoring Google Nest Thermostats via the SDM API

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Tested on Zabbix](https://img.shields.io/badge/Tested%20on-Zabbix%207.4.8-red.svg)
![Platform](https://img.shields.io/badge/Platform-Ubuntu%20%2F%20Debian-blue.svg)
![Status](https://img.shields.io/badge/Status-Stable-brightgreen.svg)

---

## What This Does

Google Nest Thermostats cannot be polled directly by Zabbix (they don't expose a local
API endpoint). Instead, this project uses a Python helper script that:

1. Authenticates with the **Google Smart Device Management (SDM) API**
2. Retrieves live thermostat data from the cloud
3. Outputs the data in a format Zabbix can consume via an **External Check** item

**Metrics collected per thermostat:**

| Metric | Description | Unit |
|---|---|---|
| Current Temperature | Ambient air temperature | °C |
| Set Temperature | Target thermostat temperature | °C |
| Humidity | Relative humidity | % |
| Mode | Operating mode (HEAT, COOL, MANUAL_ECO, OFF, HEATCOOL) | text |

**Supports monitoring multiple thermostats** — each device is monitored as a separate
Zabbix host using the device ID macro `{$NEST_DEVICE_ID}`.

---

## Compatibility & Caveats

> **⚠️ Important — Read Before You Start**

| Item | Details |
|---|---|
| Zabbix version | Tested on **7.4.8 only**. May work on 6.x but is untested. |
| OS | Tested on **Ubuntu/Debian only**. |
| Google SDM API | Instructions in this README reflect the API setup flow as of **April 2026**. Google changes the setup flow regularly. If steps don't match what you see, check the [official SDM documentation](https://developers.google.com/nest/device-access). |
| Google API costs | The Google Device Access program has a **one-time $5 registration fee** per Google account (as of April 2026). |
| Python | Python 3.8+ required on the Zabbix server. |

---

## Project Structure

```
Zabbix-Nest-Integration/
├── .gitignore                          
├── CHANGELOG.md                        
├── LICENSE                             
├── README.md                           
├── scripts/
│   ├── nest_to_zabbix.py             ← Python helper script (runs on Zabbix server)
│   ├── nest_auth_setup.py            ← Interactive OAuth setup wizard (run once)
│   └── nest_to_zabbix.conf.example   ← Example config
└── template/
    └── zbx_template_google_nest.yaml  ← Zabbix 7.x import template
```
---

## Prerequisites

Before you begin, you need:

1. A working **Zabbix 7.x server** running on Ubuntu/Debian
2. A **Google account** that owns (or has access to) the Nest thermostat(s)
3. Python 3.8+ on the Zabbix server (`python3 --version` to check)
   > The helper script uses only Python standard library modules — no third-party packages required.
4. A Google Cloud account (free tier is sufficient) — [console.cloud.google.com](https://console.cloud.google.com)
5. Enrollment in the Google Device Access program ($5 one-time fee) — [console.nest.google.com/device-access](https://console.nest.google.com/device-access)

---

## Part 1 — Google SDM API Setup

> **⚠️ API Setup Caveat (April 2026)** — Google restructures their Cloud Console and
> Device Access Console frequently. The steps below were accurate as of April 2026.
> Menu names, button labels, and URLs may differ from what you see. If a step doesn't
> match, refer to the [official SDM quickstart guide](https://developers.google.com/nest/device-access/get-started).

Steps 1.1–1.4 must be completed manually in the Google web consoles. Once done,
**`nest_auth_setup.py`** handles the rest — it runs the browser authorization flow,
exchanges credentials, writes the config file, locks it down, and confirms your
thermostats are visible, all in a single guided session.

### Step 1.1 — Enable the SDM API in Google Cloud

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (top bar → project dropdown → **New Project**)
   - Give it a name like `zabbix-nest`
   - Note the **Project ID** (e.g. `zabbix-nest-123456`) — you need this later
3. In the left menu, go to **APIs & Services → Library**
4. Search for **Smart Device Management API** and click **Enable**

### Step 1.2 — Configure the OAuth Consent Screen

> **This step is mandatory** for all new Cloud projects. Google will block credential
> creation until it is complete. You only need to do this once per project.

1. In the left menu, go to **APIs & Services → OAuth consent screen**
2. Under **User Type**, select **External** → click **Create**
   > "Internal" requires a Google Workspace org account. **External** is correct for
   > personal Gmail/Google accounts.
3. Fill in the **App information** page (only asterisked fields are required):
   - **App name**: `Zabbix Nest Monitor` (any recognisable name)
   - **User support email**: your Google account email
   - **Developer contact information** (bottom of page): your Google account email
   - Everything else (logo, homepage URL, etc.) can be left blank
4. Click **Save and Continue**
5. On the **Data Access** page:
   - Click **Add or Remove Scopes**
   - Scroll to the bottom of the panel and find the **Manually add scopes** text box
   - Paste in: `https://www.googleapis.com/auth/sdm.service`
   - Click **Add to Table**, then **Update**
   - Click **Save and Continue**
6. On the **Audience** page:
   - Click **+ Add Users** in the Test Users section ensure your google account that owns the Nest thermostats is listed.    
   - Click **Add** if not, then **Save and Continue**

   > **Important:** While the app is in **Testing** publishing status (the default),
   > Google only allows listed test users to authorise it. You **must** add the account
   > that owns your Nest devices here or the authorisation flow in Step 1.5 will fail.

You can now create the OAuth credentials.

### Step 1.3 — Create OAuth 2.0 Client ID

1. Go to **APIs & Services → Credentials**
2. Click **+ Create Credentials → OAuth client ID**
3. **Application type**: **Web application**
   > ⚠️ Do NOT choose "Desktop app" — Desktop app clients only permit `localhost` as a
   > redirect URI. The authorization flow in Step 1.5 uses `https://www.google.com` as the
   > redirect, which requires a Web application client.
4. **Name**: `zabbix-nest-client`
5. Under **Authorized redirect URIs**, click **+ Add URI** and add:
   `https://www.google.com`
6. Click **Create** — a popup shows your **Client ID** and **Client Secret**. Copy both
   values now; also click **Download JSON** for a backup copy.

### Step 1.4 — Enroll in Google Device Access

1. Go to [console.nest.google.com/device-access](https://console.nest.google.com/device-access)
2. Accept the Terms of Service and pay the **$5 one-time registration fee**
3. Create a new project:
   - Name: `zabbix-nest`
   - Paste in your **OAuth Client ID** from Step 1.3
   - **Events: leave this unchecked / disabled**
     > Events enable real-time push notifications via Google Cloud Pub/Sub. This
     > integration uses scheduled polling instead, so Events are not needed and
     > enabling them will ask you to configure a Pub/Sub topic that serves no purpose here.
4. Note the **Device Access Project ID** — this is DIFFERENT from your Cloud Project ID

### Step 1.5 — Run the Setup Wizard

Once Steps 1.1–1.4 are complete, run the interactive setup wizard from the repo directory:

```bash
sudo python3 scripts/nest_auth_setup.py
```

The wizard will:
1. Prompt for your `Cloud Project ID`, `Client ID`, `Client Secret`, and `Device Access Project ID`
2. Print a browser authorization URL for you to open and complete the consent flow
3. Ask you to paste the full redirect URL from your browser's address bar — it parses the authorization code for you
4. Exchange the code for a refresh token automatically
5. Write `/etc/zabbix/nest_to_zabbix.conf` with `600` permissions owned by the `zabbix` user
6. Call the SDM API to verify your credentials work and print all discovered thermostats with their device IDs

> **⚠️ Refresh Token Expiry** — Google refresh tokens can be revoked if:
> - Your app is in "Testing" mode and 7 days pass without use
> - You change your Google account password
> - You revoke access in Google account settings
>
> As of v0.1.3 the script automatically persists any rotated refresh token back to the
> config file, so routine rotation is handled for you. However, if the token is outright
> revoked (e.g. after a password change or a long period of inactivity) you will see an
> `invalid_grant` error — see the [Troubleshooting](#troubleshooting) section, which
> includes instructions for re-running the wizard to recover.

<details>
<summary>Manual authorization steps (without the wizard)</summary>

**Placeholder reference:**

| Placeholder | What it is | Where you got it |
|---|---|---|
| `<SDM_PROJECT_ID>` | **Device Access Project ID** | Step 1.4 — ⚠️ this is **NOT** the Cloud Project ID from Step 1.1 |
| `<CLIENT_ID>` | OAuth Client ID | Step 1.3 |
| `<CLIENT_SECRET>` | OAuth Client Secret | Step 1.3 |
| `<AUTHORIZATION_CODE>` | One-time code from the redirect URL | Sub-step 4 below |

1. Build this URL and open it in a browser while logged into the Google account that owns your Nest devices:
   ```
   https://nestservices.google.com/partnerconnections/<SDM_PROJECT_ID>/auth?redirect_uri=https://www.google.com&access_type=offline&prompt=consent&response_type=code&scope=https://www.googleapis.com/auth/sdm.service&client_id=<CLIENT_ID>
   ```
   > `prompt=consent` is required — without it Google will not return a `refresh_token`
   > if this account has previously authorized the app.
2. Complete the consent flow. After approval, copy the full redirect URL from the browser address bar.
3. Extract the code from the URL (everything after `code=`, up to `&scope`) and exchange it:
   ```bash
   curl -s -X POST https://oauth2.googleapis.com/token \
     -d "client_id=<CLIENT_ID>" \
     -d "client_secret=<CLIENT_SECRET>" \
     -d "code=<AUTHORIZATION_CODE>" \
     -d "grant_type=authorization_code" \
     -d "redirect_uri=https://www.google.com"
   ```
4. Copy the `refresh_token` from the response and place it in `/etc/zabbix/nest_to_zabbix.conf`.

</details>

---

## Part 2 — Zabbix Server Setup

### Step 2.1 — Deploy the Script

```bash
# Confirm your Zabbix ExternalScripts path (tweak subsequent steps if it differs)
sudo grep ExternalScripts /etc/zabbix/zabbix_server.conf

# Copy the script to the Zabbix external scripts directory
sudo cp scripts/nest_to_zabbix.py /usr/lib/zabbix/externalscripts/

# Make it executable
sudo chmod 755 /usr/lib/zabbix/externalscripts/nest_to_zabbix.py
```

### Step 2.2 — Credentials Config File

If you used the setup wizard in Step 1.5, `/etc/zabbix/nest_to_zabbix.conf` is already
written and locked down — nothing more to do here.

If you skipped the wizard and need to create the file manually:

```bash
# Copy the example config to the secure location
sudo cp scripts/nest_to_zabbix.conf.example /etc/zabbix/nest_to_zabbix.conf

# Edit it and replace ALL placeholder values with your real credentials
sudo nano /etc/zabbix/nest_to_zabbix.conf

# Lock it down — ONLY the zabbix OS user can read it
sudo chown zabbix:zabbix /etc/zabbix/nest_to_zabbix.conf
sudo chmod 600 /etc/zabbix/nest_to_zabbix.conf

# Verify the permissions (should show: -rw------- zabbix zabbix)
ls -la /etc/zabbix/nest_to_zabbix.conf
```

### Step 2.3 — Import the Zabbix Template

1. In the Zabbix web UI, go to **Data Collection → Templates**
2. Click **Import** (top right)
3. Upload `template/zbx_template_google_nest.yaml`
4. Accept all defaults and click **Import**

### Step 2.4 — Link the Template to a Host

For each thermostat you want to monitor:

1. Go to **Data Collection → Hosts → Create Host** (or edit an existing one)
2. Set the **Host name** to something descriptive (e.g. `Nest - Living Room`)
3. Under **Templates**, add **Google Nest Thermostat**
4. Under **Macros**, add a macro named `{$NEST_DEVICE_ID}` (include the `{$` and `}`) and
   set its value to the full device resource name (printed by the wizard in Step 1.5), e.g.:
   `enterprises/abc123/devices/xyz789`
   > The setup wizard (Step 1.5) prints device IDs at the end. You can also retrieve
   > them at any time with:
   > ```bash
   > sudo -u zabbix python3 /usr/lib/zabbix/externalscripts/nest_to_zabbix.py --list-devices
   > ```

---

## Troubleshooting

### `invalid_grant` — Token has been expired or revoked

Zabbix shows a value like:
```
ERROR: Token refresh failed (HTTP 400): {"error": "invalid_grant", ...}
```

This means the refresh token stored in `/etc/zabbix/nest_to_zabbix.conf` is no longer
valid. The easiest fix is to re-run the setup wizard — it handles the full re-authorization
flow and overwrites the config with a fresh token:

```bash
sudo python3 scripts/nest_auth_setup.py
```

When prompted whether to overwrite the existing config, type `y`. The wizard will walk
through the browser consent flow, exchange a new refresh token, update the file, and
confirm your thermostats are visible before exiting.

<details>
<summary>Manual recovery steps (without the wizard)</summary>

**What you need:**

| Value | Where to find it |
|---|---|
| `<SDM_PROJECT_ID>` | Your Device Access project — [console.nest.google.com/device-access](https://console.nest.google.com/device-access) |
| `<CLIENT_ID>` | Google Cloud → APIs & Services → Credentials |
| `<CLIENT_SECRET>` | Same credentials page (or the downloaded JSON) |

**Step 1 — Build the authorization URL and open it in your browser:**

```
https://nestservices.google.com/partnerconnections/<SDM_PROJECT_ID>/auth?redirect_uri=https://www.google.com&access_type=offline&prompt=consent&response_type=code&scope=https://www.googleapis.com/auth/sdm.service&client_id=<CLIENT_ID>
```

> `prompt=consent` is required — without it Google will not return a `refresh_token`
> if this account has previously authorized the app.

Complete the consent flow. After approval, copy the full redirect URL from the address bar.

> ⚠️ Authorization codes expire within minutes — run the next step immediately.

**Step 2 — Exchange the code for a new refresh token:**

```bash
curl -s -X POST https://oauth2.googleapis.com/token \
  -d "client_id=<CLIENT_ID>" \
  -d "client_secret=<CLIENT_SECRET>" \
  -d "code=<AUTHORIZATION_CODE>" \
  -d "grant_type=authorization_code" \
  -d "redirect_uri=https://www.google.com"
```

Copy the `refresh_token` from the response.

**Step 3 — Update the config file:**

```bash
sudo nano /etc/zabbix/nest_to_zabbix.conf
```

Replace the `refresh_token` value, save and exit.

**Step 4 — Verify:**

```bash
sudo -u zabbix python3 /usr/lib/zabbix/externalscripts/nest_to_zabbix.py --metric current_temp
```

You should see a temperature value. Zabbix will recover automatically on the next polling cycle.

</details>

> **Going forward:** As of v0.1.3 the script automatically saves any rotated refresh
> token back to the config file, so you should not need to do this again unless the token
> is explicitly revoked (password change, account security event, or extended inactivity
> while your app is in Testing mode).

---

## Possible Future Enhancements

Ideas for future development (not yet planned):
- Nothing currently planned — open an Issue if you have a suggestion

---

## Contributing

This is a personal project published for community use. If you find it useful or have
improvements, feel free to open an Issue or Pull Request on GitHub.

---

## Author

**jerwah** — [github.com/jerwah](https://github.com/jerwah)

---

## License

MIT — see [LICENSE](LICENSE) for full text.


## AI Disclaimer

Claude Sonnet 4.6 was heavily used in the creation of this project but an actual human did actually do some stuff too.
