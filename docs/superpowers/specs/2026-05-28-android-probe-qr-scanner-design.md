# Android Probe QR Scanner Design

## Summary

Enable the receiver setup QR workflow in the Android probe app. The scanner should decode the same receiver setup JSON currently accepted by the paste field, then move the operator into the active session view. Paste JSON and manual entry remain available as fallbacks.

## Goals

- Add camera permission and a camera preview scanner.
- Decode QR codes using ML Kit Barcode Scanning.
- Parse decoded text using the existing `PairingPayload.parse` contract.
- Stop scanning after a valid receiver setup payload is accepted.
- Show clear retry/error text for invalid QR contents.
- Preserve saved receiver, paste JSON, and manual receiver setup flows.

## Non-Goals

- No custom QR payload format changes.
- No scanner styling beyond a functional preview surface.
- No official Cisco visual assets.
- No receiver token validation changes.

## UX

`Receiver setup` starts with an enabled `Scan receiver QR code` action. Tapping it asks for camera permission if needed and shows a full-width preview with:

- `Cancel scan`
- concise error text for invalid QR contents

When a valid receiver setup payload is detected, the scanner closes and calls the same pairing success path as paste/manual setup.

