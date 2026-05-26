# ClientTracker

Real-time wireless client roaming tracker for Cisco Catalyst 9800 Wireless LAN Controllers, Cisco APs, and local client Wi-Fi telemetry.

ClientTracker can run from a management machine to watch the infrastructure view, from the wireless client to watch local OS telemetry, or from the wireless client in combined mode to show both views in one live terminal UI.

## Requirements

- Python 3.10+
- Network SSH access to the WLC and APs for `infra` and `combined` modes
- Enable-level access on APs for AP-side client stats
- macOS or Windows for local Wi-Fi telemetry

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
```

Environment variables override file values:

- `CLIENT_TRACKER_WLC_HOST`
- `CLIENT_TRACKER_WLC_USERNAME`
- `CLIENT_TRACKER_WLC_PASSWORD`
- `CLIENT_TRACKER_WLC_ENABLE`
- `CLIENT_TRACKER_AP_USERNAME`
- `CLIENT_TRACKER_AP_PASSWORD`
- `CLIENT_TRACKER_AP_ENABLE`

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
