# ClientTracker

Real-time wireless client roaming tracker for **Cisco Catalyst 9800** Wireless LAN Controllers and Cisco APs.

The script maintains a persistent SSH session to the WLC, polls client association data, opens on-demand SSH sessions to the connected AP to pull live RSSI/MCS/channel stats, and displays everything in a live-updating terminal UI. When the client roams to a new AP, the event is logged with the last-known signal metrics.

## Requirements

- Python 3.10+
- Network SSH access to the WLC and its APs
- Enable-level access on the APs

Install dependencies:

```
pip install -r requirements.txt
```

## Configuration

Edit `config.yaml` in the project root with your WLC and AP credentials:

```yaml
wlc:
  host: "192.168.2.8"
  username: "admin"
  password: "changeme"
  enable: "changeme"

ap:
  username: "admin"
  password: "changeme"
  enable: "changeme"
```


## Usage

```
python client_tracker.py <mac-address>
```

The MAC address can be supplied in any common format — all delimiters (`:`, `-`, `.`) are accepted:

```
python client_tracker.py aa:bb:cc:dd:ee:ff
python client_tracker.py aa-bb-cc-dd-ee-ff
python client_tracker.py aabb.ccdd.eeff
python client_tracker.py aa.bb.cc.dd.ee.ff
python client_tracker.py aabbccddeeff
```

The script will:

1. SSH to the WLC and begin polling the client's association state.
2. SSH to the currently connected AP and pull live RSSI, MCS rate, and channel.
3. If the client roams, close the old AP session, open one to the new AP, and record the event.
4. Display all data in a continuously refreshing terminal UI.

Press **Ctrl+C** to stop.

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
├── config.yaml          # WLC and AP credentials (not tracked in git)
├── requirements.txt     # Python dependencies
└── README.md
```
