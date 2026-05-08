# Privacy Policy

In compliance with the Google API Services User Data Policy and Google APIs Terms of Service, this policy thoroughly and clearly discloses how the application accesses, uses, stores, and shares Google user data.

**TLDR:** The application accesses your thermostat data to send it to your Zabbix server. The developer never sees, stores, nor shares this data with anything other than your Zabbix server. The only pieces of Google user data stored on your server ever is the authentication token needed in order to access the API, and a cache file. You have full control over it. It's YOUR data, we don't want it. 

---

### Data Accessed: The specific types of Google user data your application accesses, collects, or interacts with.

The application accesses two types of data from Google's services:

*   **Thermostat Readings:** It uses the Google Smart Device Management (SDM) API to read data points from your thermostat, specifically: ambient temperature, ambient humidity, thermostat mode, and temperature setpoints.
*   **Authentication Tokens:** To perform the action above, the application uses OAuth 2.0 to authenticate with Google. This provides the application with the necessary tokens in order to make API calls on your behalf.

### Data Usage: How the application uses, processes, and handles the Google user data it accesses and the purpose for this use.

The application acts as a simple bridge. It takes data from Google and hands it to your Zabbix server. What you do with it from there is your business.

*   **Thermostat Data** is read from the Google SDM API, processed in-memory, and immediately sent to the Zabbix server you configured. The data is not used for any other purpose. It is not analyzed, aggregated, sniffed, smelled, bent, folded, nor mutilated. It's simply transmitted to your Zabbix server and nobody else. 
*   **Authentication Tokens** are used for one reason only: to make authenticated calls to the Google SDM API to fetch the thermostat data from the devices you authorized. 


### Data Sharing: A clear description of if and how Google user data is shared with specific categories of third parties and the purpose for this sharing.

This is simple: **it isn't.** - We don't want your data. We don't see your data.

The developer of this application does not have a backend server, does not collect any data of any kind. Not even usage data. There is no visibility into your information, ever. The data flow is contained entirely within systems you control.

Data Flow:
1. Google's API servers
2. The server under your control where you run the application script (usually the Zabbix server itself)
3. Your local Zabbix monitoring instance.


### Data Storage & Protection: Your practices for securely storing and protecting user data.

*  ** Storage **
  *   **Thermostat Data (Temperature, Humidity, etc.):** This data is considered ephemeral and not stored long-term. To be a good Internet citizen and avoid flooding Google's servers with API calls if you have 10 thermostats, the application uses a temporary cache. The complete data response from Google is saved to a file in `/tmp/` for a maximum of 5 minutes. This significantly reduces the number of API calls made for frequent Zabbix checks. After 5 minutes, the cached file is considered stale and is deleted or overwritten on the next run. This is the only time your thermostat readings touch a disk (your disk), and it's done purely for rate-limiting, not for data collection.
  *   **OAuth Refresh Token:** The single piece of Google user data that is stored long term is the OAuth Refresh Token. This is necessary for the application to re-authenticate with Google's API without requiring you to log in every time it runs.
      *   **Storage Location:** The token is stored in a local configuration file on your server at `/etc/zabbix/nest_to_zabbix.conf`.
      

*  ** Protection **
  *   **OAuth Token Protection:** The project's documentation and the `nest_auth_setup.py` script explicitly configure this file to have strict `600` permissions, making it readable and writable **only** by the `zabbix` system user on your server and root. This prevents other users on the system from accessing your credentials.
  *   **Thermostat Data Cache File:** The cache file in /tmp is created with `600` permissions, making it readable and writable **only** by the `zabbix` system user as well.
  *   **Encryption in Transit:** Your thermostat data is encrypted in transit when being retrieved via the Google SDM API. If your zabbix configuration is setup for encrpytion then it is sent to your Zabbix server encrypted. If your Zabbix server is not setup for encryption, then it is not encrypted.
      * The typical use case of this application is to run this code on the Zabbix server so this distinction is normally not a concern.
          * Setting up encryption for your zabbix server is your responsibility if the app and zabbix server are connected over an untrusted network. 


### Data Retention & Deletion: Your policy on how long user data is retained and an accessible process for users to request the deletion of their data.

This is also simple: You can't retain and delete something that doesn't exist. 

*   **Thermostat Data:** As described above, thermostat data is cached in a temporary file for a maximum of 5 minutes to reduce API calls. The file is automatically overwritten or becomes irrelevant after this period. There is no long-term retention, and no action is required from you to delete it; the script manages its own temporary cache.
    *   **To delete the cache file from your server:** Simply delete the file from /tmp. Log into your server and run: `sudo rm /tmp/nest_zabbix_*.json`.
*   **OAuth Refresh Token:** The refresh token is stored on your server indefinitely in order to allow for unattended, long-term monitoring in Zabbix. You have complete control over its deletion.
    *   **To delete the data from your server:** Simply delete the configuration file. Log into your server and run: `sudo rm /etc/zabbix/nest_to_zabbix.conf`.
    *   **To revoke the token from Google's side:** Go to your Google Account's security settings (https://myaccount.google.com/permissions), find the application you created for this integration, and click "Remove Access". This will permanently invalidate the token, rendering the stored copy useless.
    *   **To replace a token you believe has been exposed:** You can generate a new token at any time. First, revoke the application's access in your Google Account settings as described above (this is the most secure step). Then, simply re-run the setup wizard: `sudo python3 scripts/nest_auth_setup.py`. This will guide you through the authorization process again and write a fresh, new token to the configuration file.

---

The full source code for this application is publicly available and auditable on GitHub, ensuring full transparency into its operation:
https://github.com/jerwah/Zabbix-Nest-Integration
