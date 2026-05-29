# Android Probe UX And Branding Design

## Summary

Improve the Android probe app so it reads as a Cisco-internal operational tool and supports field walk-test work without guesswork. The first implementation should stay focused on product clarity: preflight readiness, receiver setup language, live session status, safer history/export/delete behavior, foreground notification context, and privacy-aware telemetry disclosure.

Use `Wi-Fi Ops Probe` for operational UI unless a separate Cisco naming approval confirms `Cisco Wi-Fi Ops Probe`. Cisco identity may appear through approved internal assets in app catalog, splash/about, or launcher contexts, but the app must not invent modified Cisco logos, lockups, or decorative Cisco-branded artwork.

## Goals

- Replace ambiguous pairing language with receiver setup terminology.
- Add a preflight model that explains readiness, blockers, degraded states, and recovery actions before a session starts.
- Show live walk-test status that reflects the telemetry the app already collects.
- Treat Wi-Fi telemetry and exports as sensitive operational data.
- Improve notification trust while a foreground session is running.
- Align copy with Cisco-style product language: concise, operational, sentence case, and standards-based `Wi-Fi` terminology.

## Non-Goals

- No official Cisco logo asset creation in this implementation.
- No custom QR camera scanner implementation in this first UX pass.
- No full redesign of the Android navigation stack.
- No hosted collector or cloud workflow changes.
- No changes to receiver-side telemetry contract.

## Brand And Language

User-facing language should use:

- `Wi-Fi`, not `WiFi`, except where package names or existing command names require otherwise.
- `Receiver setup`, not `Pair receiver`, for the screen concept.
- `Change receiver`, not `Pair`, for changing the active receiver.
- `Start session` and `Stop session` for the main test lifecycle.
- `Export records` when raw telemetry leaves the app.

Branding should be restrained. Use a Cisco-compatible neutral operational UI with clear status colors and no decorative over-branding. If official Cisco assets are added later, they must come from approved internal brand sources.

## Information Architecture

Primary app surfaces:

- Receiver setup: saved receiver, new receiver entry, pairing JSON fallback, receiver test result.
- Preflight: permission, Wi-Fi, receiver, data disclosure, and notification readiness.
- Active session: live Wi-Fi identity, signal, probe, upload, and collection status.
- Session history: saved sessions, export entry points, delete safeguards.

The first implementation may keep the existing single-activity Compose structure, but labels and state models should map to this IA.

## Preflight Requirements

Before starting a session, the app should be able to represent these checks:

- Nearby Wi-Fi permission: required for SSID, BSSID, RSSI, and channel collection on supported Android versions.
- Location permission: required where Android uses location permission to expose Wi-Fi identity.
- Background location: required only when collecting while the screen is off or the app is backgrounded.
- Notifications: recommended; denial is a degraded state, not a hard blocker.
- Wi-Fi connected: required for useful walk-test telemetry.
- Receiver reachable: required for live uploads; local collection can continue if the receiver later becomes unreachable.

State labels:

- `Ready`
- `Needs action`
- `Limited data`
- `Blocked`

Recovery actions:

- `Retry`
- `Open settings`
- `Test again`

The UI must disclose that records can include SSID, BSSID, RSSI, channel, IP information, probe results, timestamps, session IDs, device model, receiver destination, and upload status.

## Active Session Requirements

The active session view should prioritize what a walking operator needs:

- Current network SSID and BSSID when available.
- Signal RSSI.
- Channel and band when available.
- Last sample time or `No sample yet`.
- Last upload status.
- Receiver reachability.
- Gateway, DNS, and HTTP probe state.
- Data availability state when Android returns redacted or unavailable values.
- Collection counters: collected, pending, synced, failed.

Availability states should use clear language:

- `Available`
- `Limited`
- `Redacted`
- `Unavailable`

Example degraded copy:

- `SSID unavailable. Android returned redacted Wi-Fi data. Check Wi-Fi and location permissions.`
- `Last upload failed. Samples are still being collected locally.`
- `Notifications are off. Collection can continue, but session status may not appear while the app is backgrounded.`

## Receiver Setup Requirements

Receiver setup should make saved and new receiver choices explicit.

Required copy and behavior:

- Saved receiver should be shown as a deliberate option: `Use saved receiver`.
- New setup should use `Set up new receiver`.
- The session screen action should be `Change receiver`.
- A receiver test result should distinguish unreachable receiver from authentication failure when the underlying API supports it.

The first implementation may use the existing health endpoint check as a reachability proxy and leave full token validation for a later receiver-auth endpoint.

## History, Export, And Delete Requirements

History should not imply persistence is missing. Empty state copy should read:

`No sessions yet. Completed sessions will appear here.`

Delete should not be silent:

- Non-active deletes require confirmation or a future undo pattern.
- Active-session deletes must warn that collection will stop.
- Deleting history should not clear saved receiver details unless the operator explicitly chooses that.

Export should be explicit:

- `Export records` for raw telemetry.
- `Export summary` for counters-only output.
- Export copy must warn that records may contain network identifiers and device/session metadata.

The first implementation may rename the existing summary export to avoid implying raw telemetry export exists.

## Notification Requirements

Foreground notification should communicate active collection status:

- Title: `Wi-Fi Ops Probe running`.
- Text should include session identity and collection/upload status.
- Tapping the notification should reopen the active session.
- Include a `Stop session` action when practical.
- Use degraded text for upload failure or limited Wi-Fi identity.

## Accessibility And Android UX

- Long receiver URLs, BSSIDs, and session IDs must wrap, truncate, or expose copy affordances.
- Repeated actions should be contextual, for example `Delete session <id>`.
- Status changes should be suitable for TalkBack/live-region announcements in later work.
- Notification permission denial should show `Limited notification status`, not a blocked session.

## First Implementation Slice

Implement a bounded first pass:

- App label and visible copy use `Wi-Fi Ops Probe` and `Wi-Fi`.
- Manifest permission declarations reflect the privacy model: `NEARBY_WIFI_DEVICES` uses `neverForLocation`; fine location is max SDK 32 when practical.
- Runtime permission policy stops requesting fine location on Android 13+ when Nearby Wi-Fi is used.
- Add a testable preflight/readiness model.
- Update receiver setup, active session, history, and notification text to the approved labels and warnings.
- Surface current sample fields in the session UI if they are available from local records without changing the telemetry contract.

