# Unified Client Tracker Design

## Summary

Merge the local client roaming script into ClientTracker so one application can show infrastructure-side and endpoint-side roaming telemetry. ClientTracker remains the base project because it already has the richer command-line interface, Catalyst 9800/AP SSH integration, structured state models, and Rich live terminal UI.

The first version will support three practical modes:

- `infra`: track a target client MAC through the WLC and associated APs.
- `local`: show local Wi-Fi client telemetry from the machine running the script.
- `combined`: show both views together when the script runs on the same wireless client being tracked by the WLC.

The goal is a lab and troubleshooting tool that can answer two questions at the same time: what does the controller/AP think is happening, and what does the client OS think is happening?

## Goals

- Preserve existing ClientTracker behavior for infrastructure tracking.
- Add local client telemetry from the existing roaming script.
- Add a Local Client Stats panel to the Rich UI.
- Add a shared event timeline for WLC/AP roams, local BSSID changes, disassociation, reassociation, and polling failures/recovery.
- Add optional CSV logging for post-test analysis.
- Improve credential handling by documenting `config.example.yaml`, ignoring real `config.yaml`, and avoiding committed secrets.
- Keep the implementation modular enough to test parsers and polling logic without live wireless hardware.

## Non-Goals

- No graphical desktop or web UI in the first version.
- No packet capture, 802.11 frame parsing, or monitor-mode support.
- No full BSSID-to-AP-name correlation unless the required controller/AP command output is added later.
- No Linux local Wi-Fi telemetry in the first version. Linux can still run infrastructure tracking.
- No multi-client tracking in the first version.

## User Interface

The CLI will expose explicit modes:

```bash
python client_tracker.py aa:bb:cc:dd:ee:ff
python client_tracker.py aa:bb:cc:dd:ee:ff --mode infra
python client_tracker.py --mode local
python client_tracker.py aa:bb:cc:dd:ee:ff --mode combined
python client_tracker.py --mode local --interval 0.5
python client_tracker.py aa:bb:cc:dd:ee:ff --mode combined --log roam-test.csv
python client_tracker.py --check
```

Default mode:

- If a MAC is supplied and no mode is specified, use `infra`.
- If no MAC and no mode are supplied, use `local`.
- If `--mode local` is used, no MAC is required.
- If `--mode combined` is used, a MAC is required.

Polling interval:

- Default `infra` interval is 5 seconds.
- Default `local` interval is 1 second.
- Default `combined` interval is 2 seconds.
- `--interval <seconds>` overrides the mode default and must be greater than zero.

The Rich terminal UI will show up to four stacked panels:

- WLC Client Stats: existing controller-derived state.
- AP Client Stats: existing AP-derived RSSI/MCS/channel state.
- Local Client Stats: local SSID, BSSID, channel, TX/RX rate where available, signal, noise, CCA, PHY mode, MCS index, guard interval, NSS, security, IPv4 address, IPv4 router, and ping status where available.
- Event Timeline: unified recent events from infrastructure and local telemetry.

## Architecture

The app will be split into small modules while preserving the current single-command user experience.

Modules:

- `client_tracker/cli.py`: argument parsing, mode selection, startup checks.
- `client_tracker/config.py`: load config, validate fields, support env var overrides, expose redacted display values.
- `client_tracker/infra.py`: WLC session, AP session pool, infrastructure parsers and state models.
- `client_tracker/local.py`: local OS polling, local parsers, local state model.
- `client_tracker/events.py`: event model, event timeline, CSV logger.
- `client_tracker/display.py`: Rich renderers for all panels.
- `client_tracker/app.py`: orchestration loop for infra, local, and combined modes.

The existing `client_tracker.py` will remain as the executable shim so existing users can continue running:

```bash
python client_tracker.py <mac>
```

## Data Models

Reuse and extend the current dataclass approach.

Infrastructure state:

- Client MAC
- AP name
- AP IP
- SSID
- protocol
- policy state
- WLC RSSI
- SNR
- timestamp

AP state:

- Client MAC
- AP name
- RSSI
- channel
- SSID
- MCS/rate
- timestamp

Local state:

- interface name
- SSID
- BSSID
- channel
- TX rate
- RX rate when available
- signal/RSSI
- noise when available
- CCA when available
- security
- PHY mode
- MCS index
- guard interval
- NSS
- country code
- IPv4 address
- IPv4 router
- ping status when configured
- platform
- timestamp

Event:

- timestamp
- source: `infra`, `ap`, `local`, or `system`
- type: `roam`, `bssid-change`, `disassociated`, `associated`, `poll-error`, `poll-recovered`, `startup`, `shutdown`
- message
- optional fields for previous/current AP, previous/current BSSID, RSSI, channel, and error text

## Data Flow

Infra mode:

1. Connect to WLC.
2. Poll client state by MAC.
3. Resolve AP IP.
4. Poll AP live client stats.
5. Detect AP-name changes and append roam events.
6. Render WLC, AP, and timeline panels.
7. Write CSV rows if logging is enabled.

Local mode:

1. Detect platform.
2. Poll local Wi-Fi command output.
3. Parse local SSID/BSSID/channel/rate/signal/noise.
4. Detect BSSID changes, association loss, and recovery.
5. Render local and timeline panels.
6. Write CSV rows if logging is enabled.

Combined mode:

1. Run infrastructure polling and local polling in the same application loop.
2. Render all panels.
3. Emit separate events for infrastructure AP roams and local BSSID changes.
4. Correlate events by timestamp in the timeline, without claiming AP/BSSID equivalence unless a future mapping source is added.

## Local Telemetry Support

macOS local telemetry:

- Use `sudo -n wdutil info` as the primary telemetry source.
- Parse only the `WIFI` section when section headers are present so AWDL data cannot overwrite the active Wi-Fi interface.
- Parse SSID, BSSID, interface name, channel, RSSI, noise, CCA, Tx rate, security, PHY mode, MCS index, guard interval, NSS, country code, IPv4 address, and IPv4 router.
- Preserve SSIDs with spaces.
- Require an active sudo credential cache. Users should run `sudo -v` before local or combined macOS testing, or run the tracker with sudo.
- Do not use a weak non-sudo macOS fallback for the primary path because it does not provide equivalent RF detail.
- Keep the `airport -I` parser as parser coverage/compatibility code, but do not make it the primary macOS telemetry path.
- Detect BSSID changes and play an optional alert.
- If `wdutil` cannot run through sudo, show a clear local telemetry error without stopping infra tracking in combined mode.

macOS SSID/BSSID identity helper:

- `wdutil` can return `<redacted>` for SSID and BSSID even with sudo on modern macOS.
- Add a repo-owned Swift helper at `macos/WifiIdentityHelper`.
- Build and install the helper with `scripts/build-macos-wifi-identity-helper.sh`.
- Install path is `~/Applications/client-tracker-wifi-identity.app/Contents/MacOS/client-tracker-wifi-identity`.
- The helper uses CoreLocation and CoreWLAN to request Location Services permission and print JSON with `interface`, `ssid`, `bssid`, and `authorization`.
- ClientTracker auto-detects this helper when `local.identity_helper_path` is blank and the default app is installed.
- The app launches the default helper through LaunchServices with `open -W -n <app> --args --output <tempfile>` so macOS grants Location Services permission to the app bundle.
- If ClientTracker is running with sudo, it launches the helper as `SUDO_USER` and hands off a temp output file owned by that user.
- Explicit custom helper paths remain supported for advanced use, must be absolute, and are executed without a shell.

Windows local telemetry:

- Use `netsh wlan show interfaces`.
- Preserve SSIDs with spaces.
- Preserve existing optional ICMP ping behavior, but make it non-blocking and configurable rather than prompting during import/startup.
- Continue converting signal percent to approximate dBm, labelled as approximate.

Linux local telemetry:

- Not implemented in the first version.
- `--mode local` on Linux shows a clear unsupported-platform message and exits non-zero.
- `--mode infra` on Linux continues to work.

## Configuration

Add `config.example.yaml` and document that real credentials belong in local `config.yaml`.

Expected config shape:

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

When `local.identity_helper_path` is blank, macOS local telemetry auto-detects the repo-owned helper at the default install path. Set it only to override the helper path explicitly.

Credential env var overrides:

- `CLIENT_TRACKER_WLC_HOST`
- `CLIENT_TRACKER_WLC_USERNAME`
- `CLIENT_TRACKER_WLC_PASSWORD`
- `CLIENT_TRACKER_WLC_ENABLE`
- `CLIENT_TRACKER_AP_USERNAME`
- `CLIENT_TRACKER_AP_PASSWORD`
- `CLIENT_TRACKER_AP_ENABLE`

`config.yaml` will be ignored by Git. `config.example.yaml` will be tracked.

## CSV Logging

When `--log <path>` is supplied, write one row per poll and one row per event.

Columns:

- timestamp
- row_type: `sample` or `event`
- mode
- infra_ap_name
- infra_ap_ip
- infra_ssid
- infra_rssi
- infra_snr
- ap_rssi
- ap_channel
- ap_mcs_rate
- local_ssid
- local_bssid
- local_channel
- local_signal
- local_noise
- local_cca
- local_security
- local_phy_mode
- local_mcs_index
- local_nss
- local_ipv4_address
- local_ipv4_router
- event_source
- event_type
- event_message
- error

The logger will create the file with a header if it does not exist and append rows if it already exists.

## Error Handling

- WLC authentication or connection failure exits in `infra` and `combined` mode.
- AP polling failure shows in the AP panel and adds an event, but does not stop WLC or local polling.
- Local polling failure shows in the Local Client Stats panel and adds an event, but does not stop infra polling in combined mode.
- Missing `config.yaml` exits only for modes that require infrastructure credentials.
- Unsupported local platform exits in `local` mode and degrades gracefully in `combined` mode.
- Missing macOS identity helper does not stop polling; SSID/BSSID remain whatever `wdutil` reported.
- macOS identity helper failures are surfaced as local polling errors when enrichment is required.
- Ctrl+C closes AP sessions, disconnects WLC, stops background workers, flushes CSV output, and prints a concise shutdown message.

## Testing Strategy

Unit tests:

- MAC normalization and validation.
- WLC client detail parser.
- AP `show dot11 clients` parser, including multi-word SSIDs.
- macOS `wdutil info` parser, including multi-word SSIDs, WIFI-section scoping, RF fields, IP fields, and AWDL isolation.
- macOS SSID/BSSID helper JSON parser.
- macOS default helper auto-detection.
- macOS sudo-to-original-user helper launch behavior.
- macOS explicit custom helper path validation.
- macOS `airport -I` parser compatibility coverage, including multi-word SSIDs.
- Windows `netsh wlan show interfaces` parser, including multi-word SSIDs.
- Event generation for AP changes, BSSID changes, disassociation, and recovery.
- CSV row formatting.

Smoke checks:

- `python -m py_compile` for all modules.
- `python client_tracker.py --check` without hardware validates local dependencies and reports missing external access clearly.
- `scripts/build-macos-wifi-identity-helper.sh` builds and ad-hoc signs the macOS helper.
- Launching `~/Applications/client-tracker-wifi-identity.app` returns JSON with Location Services authorization status, interface, SSID, and BSSID.

Manual validation:

- `--mode local` on macOS client.
- `--mode infra` from a management machine with WLC/AP reachability.
- `--mode combined` from the wireless client while roaming between APs.
- macOS helper first-run Location Services approval.

## Implementation Sequence

1. Add package layout while keeping `client_tracker.py` as the executable shim.
2. Move existing WLC/AP code into infrastructure modules with no behavior change.
3. Add local telemetry parser/state code from `clientroam1.py`.
4. Add mode-aware CLI and configuration loading.
5. Extend Rich display with Local Client Stats and Event Timeline panels.
6. Add event timeline and CSV logger.
7. Add tests for parsers, event detection, and logging.
8. Replace third-party macOS SSID/BSSID helper dependency with repo-owned Swift helper and auto-detection.
9. Update README with modes, setup, config hygiene, and examples.

## Decisions

- Sound alerts default to enabled in `local` mode and disabled in `combined` mode unless enabled in config.
- CSV logging records both samples and events because roam debugging needs before/after signal context.
- Add `pytest` for parser, event, and CSV tests.
