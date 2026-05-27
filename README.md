# ClientTracker

Real-time wireless client roaming tracker for Cisco Catalyst 9800 Wireless LAN Controllers, Cisco APs, and local client Wi-Fi telemetry.

ClientTracker can run from a management machine to watch the infrastructure view, from the wireless client to watch local OS telemetry, or from the wireless client in combined mode to show both views in one live terminal UI.

## Requirements

- Python 3.10+
- Network SSH access to the WLC and APs for `infra` and `combined` modes
- Enable-level access on APs for AP-side client stats
- macOS or Windows for local Wi-Fi telemetry

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

`config.yaml` is ignored by Git and is where local WLC/AP credentials can be stored:

```yaml
wlc:
  host: "192.0.2.10"
  username: "admin"
  password: "changeme"
  enable: "changeme"

ap:
  username: "admin"
  password: "changeme"
  enable: "changeme"

local:
  ping_host: "8.8.8.8"
  sound_alerts: true
  identity_helper_path: ""
```

Environment variables override file values:

- `CLIENT_TRACKER_WLC_HOST`
- `CLIENT_TRACKER_WLC_USERNAME`
- `CLIENT_TRACKER_WLC_PASSWORD`
- `CLIENT_TRACKER_WLC_ENABLE`
- `CLIENT_TRACKER_AP_USERNAME`
- `CLIENT_TRACKER_AP_PASSWORD`
- `CLIENT_TRACKER_AP_ENABLE`

### macOS SSID/BSSID unredaction helper

On modern macOS, `wdutil` can return `<redacted>` for SSID and BSSID even when run with sudo. ClientTracker can optionally call an explicitly configured local helper to fill only those two fields while keeping RF metrics from `wdutil`.

Example:

```yaml
local:
  identity_helper_path: "/Users/you/Applications/wifi-unredactor.app/Contents/MacOS/wifi-unredactor"
```

Security notes:

- ClientTracker never downloads, installs, or auto-discovers this helper.
- The helper path must be configured explicitly in local `config.yaml`.
- The helper is executed without a shell and is expected to print JSON with `ssid` and `bssid` fields.
- When ClientTracker is launched with sudo, the helper is run as the original `SUDO_USER` so macOS Location Services permissions apply to the user's app permission.
- Review any helper source before configuring it.

## Usage

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
- Local telemetry on macOS uses `sudo -n wdutil info` by default and requires an active sudo credential cache. Run `sudo -v` before starting, or run the tracker with sudo.
- Local telemetry supports Windows through `netsh wlan show interfaces`.
- Linux local telemetry is not implemented in this version; Linux can still run infrastructure mode.

Press Ctrl+C to stop. The app closes AP sessions, disconnects the WLC, and flushes CSV output during shutdown.

## AP Radio Distribution Monitor

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
├── client_tracker.py    # Main script
├── ap_radio_monitor.py  # AP radio distribution monitor
├── ap_radio_monitor/    # AP monitor package
├── client_tracker/      # Unified client tracker package
├── config.yaml          # WLC and AP credentials (not tracked in git)
├── requirements.txt     # Python dependencies
└── README.md
```
