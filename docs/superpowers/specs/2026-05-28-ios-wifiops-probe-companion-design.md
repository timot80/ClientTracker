# iOS Wi-Fi Ops Probe Companion Design

## Summary

Build a native iOS companion app that mirrors the Android Wi-Fi Ops Probe workflow to the extent iOS allows. The first version is a foreground-only walk-test probe. It connects to a WifiOps receiver/server, collects iPhone-local network samples once per second while the app is active, stores samples locally before upload, and syncs records using the same receiver API and telemetry JSON contract as Android.

The app should prioritize protocol parity over introducing a separate iOS data model. iOS-unavailable Wi-Fi fields must be explicit through `null` values and `availability` markers so the app and receiver can distinguish platform limits from collection failures.

## Goals

- Mirror Android receiver setup, saved receiver behavior, session lifecycle, counters, history, and upload semantics.
- Use the same receiver pairing payload: `receiver_url`, `session_id`, and `token`.
- Use the same telemetry record schema as Android, with minimal iOS/platform additions only when needed.
- Collect foreground samples every second while a session is running and the app is active.
- Store every sample locally before upload and preserve pending records across app restarts.
- Make iOS platform limits visible instead of silently omitting unavailable fields.
- Keep raw telemetry treated as sensitive operational data.

## Non-Goals

- No background collection in the first version.
- No Android-style nearby Wi-Fi scanning on iOS.
- No direct WLC/controller login from the iPhone.
- No named device registration or stable fleet identity in the first version.
- No raw record export in the first version.
- No redesign of the receiver-side API unless a small compatibility field is required.

## Existing Android Behavior To Mirror

The Android worktree stores the last receiver setup in app preferences and exposes `Use saved receiver`. It stores `receiver_url`, `session_id`, and `token`, starts a foreground service for a session, collects samples once per second, writes records into local Room tables, and uploads pending records to:

```text
POST /api/v1/sessions/{session_id}/records
Authorization: Bearer <token>
```

Android tracks local record status as `pending`, `synced`, or `failed`. Receiver acknowledgements include `accepted`, `duplicate`, and `rejected`; accepted and duplicate records become synced, rejected validation failures become failed, and retryable network/server failures remain pending with retry metadata.

The iOS app should preserve those operational semantics while replacing Android foreground-service behavior with foreground-only iOS collection.

## Architecture

Create a native SwiftUI app under:

```text
ios/WifiOpsProbe/
```

Core modules:

- `PairingPayload`: Parse and validate Android-compatible receiver setup JSON and manual fields.
- `ReceiverClient`: Call `/health` and upload record batches with bearer token auth.
- `TelemetryRecord`: Swift models matching the Android telemetry JSON schema.
- `TelemetryCollector`: Collect iOS-local foreground sample data and explicit availability markers.
- `ActiveProbeRunner`: Run DNS, HTTP, and best-effort gateway probes.
- `ProbeStore`: Persist sessions and records locally with status, retry count, and last error.
- `SyncWorker`: Upload pending records and apply receiver acknowledgements.
- `SessionViewModel`: Own active session state, the foreground one-second timer, counters, latest sample, and user-visible errors.
- SwiftUI screens: `ReceiverSetupView`, `PreflightView`, `SessionView`, and `SessionHistoryView`.

## Pairing And Saved Receiver

Use the same pairing payload shape as Android:

```json
{
  "receiver_url": "http://server:8765",
  "session_id": "walk_1",
  "token": "secret"
}
```

Receiver setup supports:

- Manual receiver URL, session ID, and token fields.
- Pasted setup JSON.
- `Use saved receiver` when a previous setup exists.
- `Change receiver` from the session screen.

Store the token in Keychain. Store non-secret receiver URL and session ID in app storage. Do not introduce named device registration in the first version; Android currently uses the device model as `device_id`, not a durable unique registration identity.

## Screens And Workflow

### Receiver Setup

Shows saved receiver details when available, new receiver fields, and setup JSON entry. Copy should use Android-aligned operational language: `Receiver setup`, `Use saved receiver`, `Set up new receiver`, and `Change receiver`.

### Preflight

Preflight runs before starting a useful session and exposes readiness states similar to Android:

- Wi-Fi connected.
- WifiOps receiver reachable through `/health`.
- Local Network permission if needed for receiver/probe access.
- Wi-Fi information availability for current SSID/BSSID.
- Data disclosure that records may include SSID, BSSID, IP information, probe results, timestamps, session IDs, device model, receiver destination, and upload status.

States should map to Android terms where practical: `Ready`, `Needs action`, `Limited data`, and `Blocked`.

### Active Session

The active session screen shows:

- Receiver URL and session ID.
- Running or stopped state.
- Receiver reachability.
- Latest sample: SSID, BSSID, IP information, availability, and last sample time.
- Probe results: DNS and receiver HTTP health, with gateway probe best effort.
- Last upload status.
- Counters: collected, pending, synced, and failed.
- Actions: `Start session`, `Stop session`, `Change receiver`, and `Session history`.

### Session History

History shows local sessions with counters. Empty state copy should mirror Android: `No sessions yet. Completed sessions will appear here.`

Supported first-version actions:

- Export summary with counters only.
- Delete session with confirmation.

Raw record export remains out of scope because raw records can contain network identifiers and device/session metadata.

## Telemetry Contract

iOS uses Android's telemetry record structure as the shared API contract:

```text
schema_version
session_id
device_id
record_id
sequence_number
record_type
client_timestamp
app_version
payload
```

Do not add top-level fields in the first version. Platform details belong in the existing payload fields: `manufacturer` is `Apple`, and `model` identifies the iPhone model. This keeps the receiver-side contract identical to Android for the first iOS slice.

The payload mirrors Android fields:

```text
ssid
bssid
rssi
frequency_mhz
channel
tx_link_mbps
rx_link_mbps
ipv4_address
ipv6_addresses
ip_addresses
gateway
dns
manufacturer
model
probes
availability
```

Expected iOS field behavior:

- `ssid` and `bssid`: collect from current-network APIs when iOS permission and capabilities allow.
- `rssi`, `frequency_mhz`, `channel`, `tx_link_mbps`, and `rx_link_mbps`: normally unavailable locally on iOS; leave `null` and mark as `ios_unavailable` in `availability`.
- `ip_addresses`, DNS, and network path: collect what iOS exposes.
- `gateway`: best effort.
- `probes`: DNS and receiver HTTP health are in scope; gateway TCP probe is best effort.
- `manufacturer`: `Apple`.
- `model`: iPhone model identifier or friendly model string.

Missing values must not render as blank. The app and server should distinguish `Unavailable on iOS`, `Permission unavailable`, `No Wi-Fi network`, and `Receiver unreachable` where the collector can tell them apart.

## Foreground Collection

The first version is foreground-only:

- Start collection only after receiver setup and preflight.
- Collect one sample per second while the app is active and the session is running.
- Pause or stop collection when the app backgrounds, locks, or quits.
- On return to foreground, show the prior session and let the user restart collection.
- Keep unsynced records queued and sync them when the app is active again.

This intentionally does not claim parity with Android foreground-service collection while backgrounded.

## Local Storage

Use a local persistence layer with two logical tables:

- `sessions`: session ID, receiver URL, token reference or secure-token key, device ID, created time, stopped time.
- `records`: record ID, session ID, sequence number, record type, payload JSON, sync status, retry count, last error, created time.

Record IDs should follow the Android-compatible pattern:

```text
{session_id}-{sequence_number}
```

Sequence numbers continue from the local max for that session if a session is resumed.

## Sync And Error Handling

`SyncWorker` uploads pending records in batches using the Android receiver contract:

```json
{
  "records": []
}
```

Receiver acknowledgement handling:

- `accepted`: mark matching pending records as `synced`.
- `duplicate`: mark matching pending records as `synced`.
- `rejected`: mark matching pending records as `failed` with the receiver error.

HTTP/network behavior:

- Auth failures remain visible and stop useful upload until receiver setup is corrected.
- Non-retryable validation errors become `failed`.
- Retryable network and server errors remain `pending`, increment `retry_count`, and store `last_error`.

The UI should show counters and last upload status in the same terms as Android: collected, pending, synced, and failed.

## Testing

Initial tests should cover:

- Pairing JSON compatibility with Android.
- Manual pairing normalization and validation.
- Telemetry JSON encoding with Android-compatible keys.
- iOS availability markers for locally unavailable RF fields.
- Receiver acknowledgement handling for accepted, duplicate, and rejected records.
- Retryable failures remaining pending.
- Non-retryable validation failures becoming failed.
- Session counters derived from local record state.

## Implementation Notes

- Use Apple's current-network APIs for SSID/BSSID access and request the required app capability/permission during implementation. If the capability is unavailable in a development build, the collector records explicit availability markers and the rest of the session still works.
- Keep the first-version receiver contract identical to Android. Do not require receiver changes for top-level iOS metadata.
- Set `device_id` to the iPhone model identifier or friendly model string in the first version to mirror Android's model-based behavior. A durable app-generated install ID can be considered later if WifiOps needs stable per-device identity.
