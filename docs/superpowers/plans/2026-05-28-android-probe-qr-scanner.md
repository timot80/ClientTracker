# Android Probe QR Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable QR receiver setup in the Android probe app.

**Architecture:** Add CameraX preview support in a focused Compose component. Keep QR parsing delegated to `PairingPayload.parse`; do not introduce a new payload contract.

**Tech Stack:** Kotlin, Jetpack Compose, CameraX, ML Kit Barcode Scanning, Android runtime permissions.

---

## Tasks

- [ ] Add CameraX dependencies and camera permission.
- [ ] Add a `QrScannerView` Compose component that binds `Preview` and `ImageAnalysis` to lifecycle.
- [ ] Decode QR/barcode raw values with ML Kit.
- [ ] Wire `PairScreen` scan action to camera permission and scanner view.
- [ ] Preserve paste/manual setup fallbacks.
- [ ] Run `ANDROID_HOME=/Users/timotbar/Library/Android/sdk ./gradlew :app:testDebugUnitTest`.
- [ ] Run `ANDROID_HOME=/Users/timotbar/Library/Android/sdk ./gradlew :app:lintDebug`.

