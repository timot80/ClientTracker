# Android Probe UX Follow-Up Design

## Summary

Build on the first UX branding pass by making setup and operations more actionable. This slice should improve receiver setup, make preflight checks actionable, add real raw telemetry export, and introduce a small visual theme layer. It should stay bounded and avoid a full navigation rewrite.

## Goals

- Make receiver setup QR-first in the UI flow, while allowing implementation to use paste/import as the first non-camera step if camera scanning would require a larger dependency pass.
- Add explicit preflight recovery actions for permissions, Wi-Fi state, and receiver reachability.
- Export raw telemetry records for a session as JSON using Android share sheet.
- Add a simple Compose theme with Cisco-compatible operational colors and status treatment.
- Add tests around raw export formatting and any policy/helper logic.

## Non-Goals

- No official Cisco logo asset creation.
- No full CameraX scanner if it would require large dependency and permission work in this slice.
- No full multi-screen navigation rewrite.
- No hosted collector work.

## Receiver Setup

The first screen should lead with QR setup language:

- Primary label: `Scan receiver QR code`
- Secondary: `Paste setup JSON`
- Manual fallback: `Enter receiver details`

If camera QR scanning is deferred, the button should be disabled or presented as `Scan receiver QR code (coming next)` only if that is preferable to hiding it. The active implemented path must still make pasted setup JSON easy and prominent.

## Preflight Actions

Each preflight row should show the state, detail, and action label when available:

- `Retry`
- `Open settings`
- `Test again`

Minimum behavior:

- `Open settings` opens app settings.
- `Test again` re-runs receiver reachability and refreshes checks.
- `Retry` refreshes Wi-Fi/preflight state.

## Raw Export

Session history should offer:

- `Export summary`
- `Export records`

`Export records` shares a JSON document containing:

- export metadata
- session ID
- receiver URL
- export timestamp
- record count
- raw record JSON objects, decoded from local `payloadJson`

Export copy must warn that records may include network identifiers, IP information, timestamps, device model, and receiver destination.

## Theme

Add a lightweight Compose theme:

- App background: near white.
- Primary action: Cisco-compatible blue.
- Error: existing Material error or restrained red.
- Warning/limited: amber.
- Success/ready: green.

This is a local theme layer, not a Cisco logo or brand asset implementation.

