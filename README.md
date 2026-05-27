# ClientTracker

Wireless operations tools for Cisco Catalyst 9800 environments.

This repository currently includes two terminal applications:

- `client_tracker.py`: real-time wireless client roaming tracker using WLC, AP, and optional local endpoint telemetry.
- `ap_radio_monitor.py`: live AP radio client distribution monitor for spotting APs with skewed client counts across radio slots.

The client tracker can run from a management machine to watch the infrastructure view, from the wireless client to watch local OS telemetry, or from the wireless client in combined mode to show both views in one live terminal UI.

## Requirements

- Python 3.10+
- Network SSH access to the WLC and APs for `infra` and `combined` modes
- Enable-level access on APs for AP-side client stats
- macOS or Windows for local Wi-Fi telemetry
- WLC SSH access for the AP radio distribution monitor

See [CLI Command Access Requirements](docs/cli-command-access.md) for the WLC, AP, and local endpoint commands used by each mode.

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Copy the tracked example file and edit the local copy:

```bash
cp config.example.yaml config.yaml
```

`config.yaml` is ignored by Git. The preferred workflow is to store shared
infrastructure secrets in the OS keyring and keep only profile references in
`config.yaml`:

```bash
wifiops credentials set-profile c9800-admin --username netops-admin
```

```yaml
credentials:
  profiles:
    c9800-admin:
      username: "netops-admin"
      password_keyring: "wifiops:profile:c9800-admin:password"
      enable_keyring: "wifiops:profile:c9800-admin:enable"

wlc:
  host: "192.0.2.10"
  credential_profile: "c9800-admin"

ap:
  credential_profile: "c9800-admin"

local:
  ping_host: "8.8.8.8"
  sound_alerts: true
  identity_helper_path: ""

ap_balance:
  refresh_seconds: 30
  include: []
  exclude: []
  included_slots: []
  excluded_slots: []
  only_imbalanced: false
  display_columns: 1
  auto_exclude_admin_down_slots: false
  min_total_clients: 1
  imbalance:
    ratio_threshold: 10
    min_difference: 20
    include_zero_client_slots: true
```

Plaintext `username`, `password`, and `enable` values in `wlc` and `ap`
sections still work for local-only compatibility. Secrets can also be loaded
from explicit `password_keyring` and `enable_keyring` references.

Environment variables override file values:

- `CLIENT_TRACKER_WLC_HOST`
- `CLIENT_TRACKER_WLC_USERNAME`
- `CLIENT_TRACKER_WLC_PASSWORD`
- `CLIENT_TRACKER_WLC_ENABLE`
- `CLIENT_TRACKER_AP_USERNAME`
- `CLIENT_TRACKER_AP_PASSWORD`
- `CLIENT_TRACKER_AP_ENABLE`

Credential profiles are managed from the `wifiops` entrypoint:

```bash
wifiops credentials show-profiles
wifiops credentials delete-profile c9800-admin
```

`show-profiles` reads the YAML profile index and does not enumerate the OS
keyring. `delete-profile` removes the YAML profile and known keyring entries,
but it does not rewrite `wlc.credential_profile` or `ap.credential_profile`
references.

### macOS SSID/BSSID helper

On modern macOS, `wdutil` can return `<redacted>` for SSID and BSSID even when run with sudo. ClientTracker includes a small macOS helper that requests Location Services permission and fills only those two fields while keeping RF metrics from `wdutil`.

Build and install the repo-owned helper:

```bash
scripts/build-macos-wifi-identity-helper.sh
```

The script installs:

```text
~/Applications/client-tracker-wifi-identity.app/Contents/MacOS/client-tracker-wifi-identity
```

Run the helper once as your normal macOS user and approve the Location Services prompt:

```bash
~/Applications/client-tracker-wifi-identity.app/Contents/MacOS/client-tracker-wifi-identity
```

ClientTracker auto-detects that installed helper. An explicit helper path is still supported for advanced cases:

Example:

```yaml
local:
  identity_helper_path: "/Users/you/Applications/client-tracker-wifi-identity.app/Contents/MacOS/client-tracker-wifi-identity"
```

Security notes:

- ClientTracker never downloads external helper code.
- The built-in helper source is tracked in this repository under `macos/WifiIdentityHelper`.
- The default helper is auto-detected only from the current user's `~/Applications/client-tracker-wifi-identity.app`.
- Any custom helper path must be configured explicitly in local `config.yaml`.
- The helper is executed without a shell and is expected to print JSON with `ssid` and `bssid` fields.
- When ClientTracker is launched with sudo, the helper is run as the original `SUDO_USER` so macOS Location Services permissions apply to the user's app permission.
- Review any custom helper source before configuring it.

## Usage

### Client Roaming Tracker

Infrastructure mode tracks a client through the WLC and associated AP:

```bash
python client_tracker.py aa:bb:cc:dd:ee:ff
python client_tracker.py aa:bb:cc:dd:ee:ff --mode infra
```

Local mode shows Wi-Fi telemetry from the machine running the script:

```bash
sudo -v
python client_tracker.py --mode local
```

Combined mode shows infrastructure and local telemetry together:

```bash
sudo -v
python client_tracker.py aa:bb:cc:dd:ee:ff --mode combined
```

Polling defaults are mode-specific: local mode updates every 1 second, combined mode every 2 seconds, and infrastructure mode every 5 seconds. Override with `--interval`:

```bash
sudo python client_tracker.py --mode local --interval 0.5
```

Enable CSV logging for walk-test analysis:

```bash
python client_tracker.py aa:bb:cc:dd:ee:ff --mode combined --log roam-test.csv
```

Validate local setup without starting a tracking loop:

```bash
python client_tracker.py --check
```

The MAC address can be supplied in common formats:

```bash
python client_tracker.py aa:bb:cc:dd:ee:ff
python client_tracker.py aa-bb-cc-dd-ee-ff
python client_tracker.py aabb.ccdd.eeff
python client_tracker.py aabbccddeeff
```

## What It Shows

- WLC Client Stats: AP name, AP IP, SSID, protocol, policy state, RSSI, and SNR.
- AP Client Stats: AP-side RSSI, MCS/rate, channel, and SSID.
- Local Client Stats: endpoint SSID, BSSID, channel, TX/RX rate, signal, noise, CCA, PHY, MCS, NSS, security, IPv4 address, and optional ping status.
- Event Timeline: infrastructure AP roams, local BSSID changes, association changes, and polling errors.

## Platform Notes

- Infrastructure tracking works on any platform that can run Python and reach the WLC/APs over SSH.
- Local telemetry on macOS uses `sudo -n wdutil info` by default and requires an active sudo credential cache. Run `sudo -v` before starting, then run `wifiops client local`.
- Avoid running infrastructure commands under sudo when using keyring profiles. Keyring lookups may use root's keyring instead of the profile stored for your normal user.
- Local telemetry supports Windows through `netsh wlan show interfaces`.
- Linux local telemetry is not implemented in this version; Linux can still run infrastructure mode.

Press Ctrl+C to stop. The app closes AP sessions, disconnects the WLC, and flushes CSV output during shutdown.

### AP Radio Distribution Monitor

`ap_radio_monitor.py` is a standalone live monitor for finding APs where client
counts are skewed across radio slots. It uses one SSH session to the Catalyst
9800 WLC and polls:

```
show ap summary load-info
```

Run the live monitor:

```
python ap_radio_monitor.py
```

Useful options:

```
python ap_radio_monitor.py --once
python ap_radio_monitor.py --refresh 30
python ap_radio_monitor.py --only-imbalanced
python ap_radio_monitor.py --config config.yaml
python ap_radio_monitor.py --columns 2
python ap_radio_monitor.py --auto-exclude-admin-down-slots
wifiops c9800 radio --auto-exclude-admin-down-slots
```

Add optional AP radio monitor settings to `config.yaml`:

```yaml
ap_balance:
  refresh_seconds: 30
  include:
    - "NOC-*"
  exclude:
    - "*-TEST"
  included_slots: []
  excluded_slots: []
  only_imbalanced: false
  display_columns: 1
  auto_exclude_admin_down_slots: false
  min_total_clients: 1
  imbalance:
    ratio_threshold: 10
    min_difference: 20
    include_zero_client_slots: true
```

The monitor displays each slot separately, for example:

```
S0 1 cl / 12% util █ | S1 50 cl / 76% util ████████████ | S2 0 cl / 4% util .
```

The percentage is radio/channel utilization from the WLC. It is not the
percentage of clients on that radio. Client distribution scoring is based on
client counts, while utilization is shown as RF context.

### AP Ethernet Port Audit

Audit AP uplink speed and duplex from a Catalyst 9800 WLC:

```bash
wifiops c9800 ap-ports --config config.yaml
wifiops c9800 ap-ports --include "MBY-*"
wifiops c9800 ap-ports --all
wifiops c9800 ap-ports --speed-threshold 2500
```

By default, the audit shows only ports with issues. Add optional defaults to
`config.yaml` when the same filters or threshold should apply every run:

```yaml
ap_ports:
  include:
    - "NOC-*"
  exclude:
    - "*-TEST"
  show_all: false
  speed_threshold: 1000
```

## Example Output

```
Connected to MyWLC. Tracking client 3c6d.6606.0907...

╭────────────────────── WLC Client Stats ──────────────────────╮
│  WLC:      MyWLC                                             │
│  Client:   3c6d.6606.0907                                    │
│  AP Name:  AP-9166-1             AP IP: 10.1.2.3             │
│  SSID:     DevNet                Protocol: 802.11ax - 5 GHz  │
│  RSSI:     -42 dBm               SNR: 38 dB                  │
│  State:    Run                   Updated: 14:23:05           │
╰──────────────────────────────────────────────────────────────╯
╭──────────── AP Client Stats (AP-9166-1) ─────────────────────╮
│  Live RSSI: -45 dBm    Rate: MCS112SS    Ch: 34              │
│  Updated: 14:23:05                                           │
╰──────────────────────────────────────────────────────────────╯
╭──────────────────── Roaming History ─────────────────────────╮
│  14:20:12  AP-9166-2 -> AP-9166-1  -51 dBm  MCS92SS  Ch 40   │
│  14:15:44  AP-9166-3 -> AP-9166-2  -63 dBm  MCS72SS  Ch 36   │
╰──────────────────────────────────────────────────────────────╯
Ctrl+C to quit
```

## Project Structure

```
ClientTracker/
├── client_tracker.py    # Unified client tracker executable
├── ap_radio_monitor.py  # AP radio distribution monitor
├── ap_radio_monitor/    # AP monitor package
├── client_tracker/      # Unified client tracker package
├── macos/               # Repo-owned macOS helper source
├── scripts/             # Local build/install helpers
├── config.yaml          # WLC and AP credentials (not tracked in git)
├── requirements.txt     # Python dependencies
└── README.md
```
