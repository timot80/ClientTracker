# Android Probe Telemetry Design

## Summary

Add an installable Android app that can provide real client Wi-Fi perspective to `wifiops` during walk tests. The first version is local-first: the phone sends telemetry to a receiver running on the same machine as `wifiops`. The payload format, session model, and authentication approach should also support a later hosted collector without redesigning the mobile app.

The Android app runs a foreground walk-test session. It records Wi-Fi connection snapshots, detected roam events, and active reachability checks. It stores all telemetry locally before upload so test data survives roaming gaps, DHCP loss, receiver outages, and other connectivity interruptions.

## Goals

- Build a native Android probe app that can be installed on an Android phone.
- Send Android client-perspective Wi-Fi telemetry to `wifiops`.
- Support local receiver mode first, with a clear path to a hosted collector later.
- Use QR pairing so the operator does not type receiver URLs or tokens on the phone.
- Run collection as an explicit Android foreground session with a persistent notification.
- Store telemetry locally on the phone before upload and retry unsent records.
- Reuse existing `wifiops` local telemetry concepts, event timeline, and CSV logging where practical.
- Allow optional infrastructure correlation when the operator supplies a WLC client MAC.

## Non-Goals

- No GPS latitude/longitude collection in the first version.
- No hidden always-on background monitoring.
- No automatic WLC client discovery in the first version.
- No hosted cloud collector in the first implementation, only a design path for it.
- No packet capture, monitor mode, or 802.11 frame parsing.
- No iOS app in the first version.

## User Workflow

Local receiver workflow:

```bash
wifiops probe receive --pair
wifiops probe receive --pair --log walktest.csv
```

`wifiops` starts a local HTTP receiver, creates a session, and prints a QR code containing:

- receiver URL
- session ID
- short-lived pairing token
- optional receiver display name

The Android user opens the app, scans the QR code, and taps Start Test. Android shows an ongoing foreground-service notification while collection is active. The app samples Wi-Fi and active probe health until the user taps Stop Test.

Optional future combined infrastructure workflow:

```bash
wifiops c9800 client aa:bb:cc:dd:ee:ff --mode combined --android-session <session-id>
```

This would let one terminal view show WLC/AP state plus Android client telemetry for the same walk test. In the first implementation, Android telemetry can still be useful without WLC correlation.

## Architecture

Components:

- Android app: native Kotlin app that owns Wi-Fi collection, foreground service lifecycle, local persistence, upload retry, and simple walk-test UI.
- `wifiops` probe receiver: Python local HTTP receiver that accepts paired Android telemetry records, validates session token, deduplicates retries, and exposes the latest state to display/logging code.
- Existing `client_tracker` display/events layer: reused for local client panels, timeline events, and CSV rows where the Android fields map cleanly to `LocalClientState`.
- Future hosted collector: accepts the same JSON envelope over HTTPS and stores records centrally for remote/multi-site collection.

The local receiver should be a small bounded component rather than a general web service. It only needs session creation, health, telemetry ingest, and optional session export endpoints.

## Android App

Use native Kotlin Android for the first version. This gives direct access to Android Wi-Fi APIs, foreground services, notification behavior, permissions, QR scanning, local storage, and installable APK packaging.

Target Android API should track the current Android SDK available to the build environment. Minimum SDK should be Android 10 / API 29 for the first version because it keeps the device support range practical while avoiding older Wi-Fi and background-execution behavior.

Primary screens:

- Pair screen: scan QR code or manually enter receiver URL/session token.
- Session screen: show SSID, BSSID, RSSI, link speed, channel/frequency, IP state, active probe status, and sync counts.
- Session history/export screen: show saved walk-test sessions and allow JSON/CSV export if records could not be uploaded.

QR scanning should use ML Kit Barcode Scanning for the first implementation. Manual receiver URL/token entry remains available as a fallback.

Runtime behavior:

1. User scans QR pairing code.
2. User starts a walk-test session.
3. App starts a foreground service with a persistent notification.
4. Sampling loop records Wi-Fi snapshot and active probe results.
5. Detection logic emits events for BSSID changes, association loss, association recovery, and upload failures/recovery.
6. Every record is committed to local storage before upload.
7. Sync loop uploads pending records in timestamp/sequence order.
8. User stops the session, which stops sampling and performs a final sync attempt.

## Android Permissions And Privacy

Android may require location-related permissions to expose SSID, BSSID, and Wi-Fi connection details. The app may request the permissions required to read Wi-Fi identity and RF data, but it must not collect GPS coordinates in the first version.

Permission and service requirements:

- Target current Android SDK. Minimum SDK remains Android 10 / API 29.
- Declare `android.permission.ACCESS_NETWORK_STATE`, `android.permission.ACCESS_WIFI_STATE`, `android.permission.INTERNET`, `android.permission.POST_NOTIFICATIONS` for Android 13+, and foreground-service permissions required by the selected foreground service type.
- Declare `android.permission.NEARBY_WIFI_DEVICES` for Android 13+ with `android:usesPermissionFlags="neverForLocation"` because the app does not derive physical location from Wi-Fi data.
- Keep `android.permission.ACCESS_FINE_LOCATION` with `android:maxSdkVersion="32"` for Android 10-12L Wi-Fi identity access. Do not request GPS coordinates.
- Avoid active Wi-Fi scans in the MVP. If a later version uses `WifiManager.getScanResults()` or `startScan()`, revisit `ACCESS_FINE_LOCATION` behavior because some scan APIs still require it even for apps targeting Android 13+.
- For Android 14+, declare the foreground service type and matching foreground-service permission. Use `dataSync` for the upload/sync service. Do not use the `location` foreground-service type in the first version.
- The app must show degraded states when required permissions are denied, Nearby Devices is disabled, Location Services prevents SSID/BSSID access on older versions, notification permission is denied, or foreground-service startup fails.
- Local HTTP receiver mode requires an Android network security configuration that permits cleartext only for explicitly paired local IP addresses or debug/local builds. Hosted collector mode must be HTTPS-only.

The app should make this explicit in its UI and data model:

- collect SSID, BSSID, RSSI, link speed, frequency/channel, network ID where available, IP/gateway/DNS state, and Android device/app metadata needed for troubleshooting
- do not collect latitude, longitude, altitude, or raw location tracks
- let the operator choose whether to include a human-readable device label, defaulting to no label
- use a per-install random device ID that can be reset by clearing app data; use per-session IDs in exports and uploads rather than hardware identifiers
- provide session delete controls and make exports explicit because SSID, BSSID, IP addresses, DNS servers, and device model can still be sensitive

## Telemetry Scope

Each periodic sample should include a stable envelope and a nullable payload. Android API level, permission state, OEM behavior, Wi-Fi generation, 6 GHz/7 support, and MLO behavior can make individual fields unavailable or redacted.

Required envelope fields:

- `schema_version`
- `session_id`
- `device_id`
- `record_id`
- `sequence_number`
- `record_type`
- `client_timestamp`
- `app_version`
- `android_api_level`

Payload fields are best-effort and nullable:

| Field | Source | Required access | Fallback |
| --- | --- | --- | --- |
| `connection_state` | Connectivity/Wi-Fi APIs | network state | report disconnected or unknown |
| `ssid` | Wi-Fi connection info | Wi-Fi identity permission and platform settings | null with availability reason |
| `bssid` | Wi-Fi connection info | Wi-Fi identity permission and platform settings | null with availability reason |
| `rssi` | Wi-Fi connection info | Wi-Fi state | null if unavailable |
| `link_mbps` | Wi-Fi connection info | Wi-Fi state | null if unavailable |
| `tx_link_mbps` | API-dependent Wi-Fi connection info | Wi-Fi state | null if unsupported |
| `rx_link_mbps` | API-dependent Wi-Fi connection info | Wi-Fi state | null if unsupported |
| `frequency_mhz` | Wi-Fi connection info | Wi-Fi state | null if unavailable |
| `channel` | derived from frequency | frequency present | null if frequency unavailable |
| `wifi_standard` | API-dependent Wi-Fi connection info | Wi-Fi state | null if unsupported |
| `security` | connection/capability APIs | API and permission dependent | null in MVP unless reliably available |
| `ipv4_address` | link properties | network state | null if unavailable |
| `gateway` | link properties/routes | network state | null if unavailable |
| `dns` | link properties | network state | empty list if unavailable |
| `manufacturer`/`model` | Android build metadata | none | optional; may be omitted by privacy setting |
| `availability` | app-generated metadata | none | include per-field unavailable reasons |

Active probe results:

- default gateway reachability/timing
- DNS lookup timing/result for a configured hostname
- HTTP GET timing/status for one configurable endpoint

The MVP should default to gateway, DNS, and one HTTP endpoint. A fully configurable target list can come later.

## Events

Android should emit explicit events in addition to samples:

- `bssid-change`
- `disassociated`
- `associated`
- `probe-failed`
- `probe-recovered`
- `upload-failed`
- `upload-recovered`
- `session-started`
- `session-stopped`

The `wifiops` receiver should convert relevant Android events into the existing timeline model. Existing `LocalClientState` should remain the normalized current-state view, while Android-specific raw details stay available in the ingested record.

## Data Contract

Use a versioned JSON envelope for both local and future hosted upload:

```json
{
  "schema_version": 1,
  "session_id": "walk_20260527_abc123",
  "device_id": "android_probe_9f3c",
  "record_id": "01J...",
  "sequence_number": 42,
  "record_type": "sample",
  "client_timestamp": "2026-05-27T14:05:31.123-07:00",
  "payload": {
    "ssid": "corp-wifi",
    "bssid": "aa:bb:cc:dd:ee:ff",
    "rssi": -63,
    "frequency_mhz": 5180,
    "channel": "36",
    "tx_link_mbps": 432,
    "rx_link_mbps": 390,
    "ipv4_address": "192.0.2.45",
    "gateway": "192.0.2.1",
    "dns": ["192.0.2.53"],
    "probes": {
      "gateway": {"ok": true, "latency_ms": 8},
      "dns": {"ok": true, "latency_ms": 24, "hostname": "example.com"},
      "http": {"ok": true, "latency_ms": 90, "status": 204, "url": "https://example.com/health"}
    }
  }
}
```

Events use the same envelope with `record_type: "event"` and an event payload. The receiver must accept repeated records safely by deduplicating on `record_id`.

## Pairing And Authentication

`wifiops probe receive --pair` creates a short-lived token and prints a QR code. The token authorizes writes only for one session. The receiver rejects records with missing, expired, or mismatched tokens.

Local MVP transport can use HTTP on the local network because it is scoped to lab/walk-test use and authenticated by the token. The data contract should not depend on HTTP. The hosted collector path should require HTTPS and either longer-lived device credentials or a device enrollment flow.

Token rules:

- Generate at least 128 bits of entropy using a cryptographically secure random source.
- Put the token in `Authorization: Bearer <token>` only. Do not put tokens in URL query strings.
- QR payload may contain the token because it is the pairing handoff, but terminal logs and CSV files must redact it.
- Token expires if unused within the pairing window and is invalidated when the receiver stops.
- On first successful upload, bind the session to the first `device_id` unless `--allow-multiple-devices` is explicitly added in a future version.
- Reject uploads for mismatched `device_id`, invalid session ID, missing token, expired token, or malformed authorization header.
- Keep dedupe and accepted-record state for the lifetime of the receiver session in the MVP.
- Apply a max request body size, max records per batch, and simple per-session rate limit so a bad client cannot exhaust memory.
- Print a clear warning when binding to `0.0.0.0` or any non-loopback address because the receiver is exposed to the LAN.

Pairing details:

- token expires if not used within a short window
- token is bound to a session ID
- receiver can rotate/revoke the token by stopping the session
- Android stores paired receiver details only for the active or saved session

## Offline Storage And Retry

The Android app must persist each sample/event before attempting upload. Collection must continue if upload fails.

Use Android Room/SQLite for the first implementation:

- `sessions` table for session metadata and receiver pairing information
- `records` table for samples/events, sequence numbers, sync status, retry count, and last error
- indexes on session ID, sequence number, sync status, and record ID

Sync behavior:

- upload pending records in timestamp/sequence order
- retry transient failures with backoff
- mark records synced only after receiver acknowledgement
- keep records after sync until the user deletes the session
- expose synced, pending, and failed counts in the UI
- support JSON/CSV export from the phone if upload never succeeds

The receiver should acknowledge accepted record IDs and ignore duplicates. This makes Android retries safe after network interruption or app restart.

## wifiops Receiver

Add a new probe command group:

```bash
wifiops probe receive --pair
wifiops probe receive --pair --host 0.0.0.0 --port 8765
wifiops probe receive --pair --log walktest.csv
```

Receiver endpoints:

- `GET /health`: basic receiver health
- `POST /api/v1/sessions/{session_id}/records`: ingest one or more telemetry records
- `GET /api/v1/sessions/{session_id}/latest`: latest normalized state for display/integration

Receiver preflight behavior:

- Default bind address is loopback for safety. The operator must opt into LAN exposure with `--host 0.0.0.0` or a specific interface address.
- When pairing, print the exact advertised URL encoded into the QR code and show the selected bind host/port.
- Add `--advertise-host` so the operator can choose the reachable host/IP when the machine has multiple interfaces or VPN routes.
- The Android app calls `/health` before enabling Start Test and shows actionable errors for timeout, refused connection, token rejected, or wrong network.
- Document that guest WLAN client isolation, host firewalls, VPN routing, NAT, and wrong interface selection can prevent phone-to-receiver connectivity.

Ingest API semantics:

- Request body is JSON with a top-level `records` array.
- Maximum body size is 1 MiB in the MVP.
- Maximum records per batch is 100.
- The receiver processes records independently and returns per-record status.
- Duplicate `record_id` returns status `duplicate` and does not mutate latest state or write another CSV row.
- Invalid records return status `rejected` with a machine-readable error code.
- Valid new records return status `accepted`.
- A batch with mixed valid and invalid records returns HTTP 207 Multi-Status or HTTP 200 with per-record statuses; the MVP should use HTTP 200 to keep the Android client simple.
- Receiver timestamps accepted records, but preserves Android `client_timestamp` for ordering and analysis.
- The receiver does not promise strict ordering across batches. Android uploads in sequence order, and CSV rows include sequence number so post-processing can sort.
- Dedupe state is in-memory for the receiver session in the first version.

Example acknowledgement:

```json
{
  "accepted": ["01JABC"],
  "duplicate": ["01JABD"],
  "rejected": [
    {"record_id": "01JABE", "error": "missing_payload"}
  ]
}
```

The receiver should run until interrupted, render the latest Android local client state and event timeline, and write CSV rows when `--log` is supplied.

The first implementation should use Python standard library HTTP support, such as `ThreadingHTTPServer`, to avoid adding a web framework dependency for a narrow local receiver. Keep the receiver isolated under a new package/module so it does not entangle WLC/AP polling code.

## Integration With Existing Models

Keep Android-specific ingest records separate from the existing `client_tracker` models. Add a receiver-side adapter that projects Android records into the current display and CSV concepts:

- `AndroidTelemetryRecord`: raw validated ingest envelope and payload.
- `AndroidReceiverState`: session/device/token/dedupe/latest-state holder.
- `AndroidLocalAdapter`: maps the latest sample into `LocalClientState`.
- `AndroidEventAdapter`: maps only supported event names into `TrackerEvent`; unsupported Android-specific events remain in receiver records and optional Android CSV columns.

Do not extend global `EventType` until a concrete UI needs those event names outside probe receiver mode. For MVP timeline display:

- `bssid-change` maps to existing `bssid-change`
- `disassociated` maps to existing `disassociated`
- `associated` maps to existing `associated`
- `probe-failed`, `probe-recovered`, `upload-failed`, `upload-recovered`, `session-started`, and `session-stopped` map to existing `poll-error`, `poll-recovered`, `startup`, or `shutdown` where that preserves meaning; otherwise render them as receiver-local text events without changing the shared model

Add Android CSV support as a receiver-owned CSV writer or extend the existing CSV writer only after preserving backward compatibility. Android CSV rows should include `session_id`, `device_id`, `record_id`, `sequence_number`, `client_timestamp`, probe summaries, sync/upload event text, and normalized local fields.

Map Android sample payloads into `LocalClientState`:

- `ssid` -> `LocalClientState.ssid`
- `bssid` -> `LocalClientState.bssid`
- `channel` or `frequency_mhz` -> `LocalClientState.channel`
- `tx_link_mbps` -> `LocalClientState.tx_rate`
- `rx_link_mbps` -> `LocalClientState.rx_rate`
- `rssi` -> `LocalClientState.signal`
- security details -> `LocalClientState.security`
- Wi-Fi standard -> `LocalClientState.phy_mode`
- `ipv4_address` -> `LocalClientState.ipv4_address`
- gateway -> `LocalClientState.ipv4_router`
- active probe summary -> `LocalClientState.ping_status`
- platform -> `android`

Do not force every Android-specific field into `LocalClientState`. Keep the raw Android record available for future richer display, cloud upload, and debugging.

## Path To Hosted Collector

The local receiver and hosted collector should share:

- JSON envelope
- schema versioning
- record IDs
- session IDs
- sequence numbers
- event names
- retry/deduplication semantics

The hosted path will add:

- HTTPS-only transport
- device enrollment
- durable backend storage
- organization/site scoping
- multi-session views
- stricter authentication and authorization

The Android app should model the upload destination as a configurable sink so the local receiver and hosted collector are different endpoints, not different collection engines.

## Testing

Python receiver tests:

- pairing token validation
- telemetry schema validation
- record deduplication
- Android sample to `LocalClientState` mapping
- event conversion into timeline records
- CSV logging for Android samples/events
- CLI parser coverage for `wifiops probe receive`

Android tests:

- data model serialization/deserialization
- Room persistence for sessions and records
- sync retry and deduplication behavior
- BSSID-change event detection
- probe result formatting
- permission-denied UI states

Manual field tests:

- phone paired to local receiver by QR code
- receiver reachable and samples visible in terminal
- receiver unavailable while phone continues collecting
- receiver restored and buffered records sync in order
- BSSID roam generates event
- disassociation/reassociation generates events
- CSV contains samples and events in expected order

## Implementation Slices

Implement in independently testable slices:

1. Python receiver contract and validation: envelope models, token validation, dedupe, batch acknowledgement, and unit tests.
2. Python CLI and display integration: `wifiops probe receive`, QR output, receiver loop, latest-state projection, timeline, and CSV logging.
3. Android project scaffold: Gradle project under `android/wifiops-probe`, Kotlin app, manifest, permissions, network security config, and debug APK build.
4. Android data contract and local store: Kotlin envelope models, Room session/record tables, JSON serialization, export.
5. Android foreground collection service: permission gates, notification, 1-second sampling loop, nullable Wi-Fi field collection, active probes.
6. Android sync engine: health preflight, bearer authorization, ordered batch upload, retry/backoff, per-record acknowledgement handling.
7. Android UI: pairing, session dashboard, sync counts, degraded permission/connectivity states, session history/delete/export.
8. Field-test validation: pair phone to local receiver, roam/disconnect test, offline buffering test, CSV inspection, and documented troubleshooting notes.

## Implementation Defaults

- Minimum Android SDK: Android 10 / API 29.
- Android implementation: Kotlin native app with a foreground service.
- QR scanning: ML Kit Barcode Scanning, with manual entry fallback.
- Android local store: Room over SQLite.
- Receiver HTTP stack: Python standard library `ThreadingHTTPServer`.
- Default sample interval: 1 second during an active walk-test session.

## References

- Android Wi-Fi permissions: https://developer.android.com/develop/connectivity/wifi/wifi-permissions
- Android 14 foreground service types: https://developer.android.com/about/versions/14/changes/fgs-types-required
- Android network security configuration: https://developer.android.com/privacy-and-security/security-config
