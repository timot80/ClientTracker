# Android Probe UX Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the first UX/branding pass for the Android Wi-Fi Ops Probe app.

**Architecture:** Keep the current single-activity Compose app and add small, testable policy/view-model helpers instead of a full navigation rewrite. Update manifest/configuration, copy, notification behavior, and session UI state in place.

**Tech Stack:** Kotlin, Jetpack Compose Material 3, Android foreground service, Room, kotlinx.serialization, JUnit.

---

## File Structure

- Modify `android/wifiops-probe/app/src/main/AndroidManifest.xml`: app label and Wi-Fi permission flags.
- Modify `android/wifiops-probe/app/src/main/java/com/wifiops/probe/PermissionPolicy.kt`: runtime permission policy and preflight status model.
- Modify `android/wifiops-probe/app/src/test/java/com/wifiops/probe/PermissionPolicyTest.kt`: regression tests for Android 13+ permission behavior and notification degraded state.
- Modify `android/wifiops-probe/app/src/main/java/com/wifiops/probe/MainActivity.kt`: use shared permission policy, expose latest record summary to UI, rename export behavior.
- Modify `android/wifiops-probe/app/src/main/java/com/wifiops/probe/ui/PairScreen.kt`: receiver setup copy and saved receiver affordance.
- Modify `android/wifiops-probe/app/src/main/java/com/wifiops/probe/ui/SessionScreen.kt`: active session dashboard copy and latest telemetry summary.
- Modify `android/wifiops-probe/app/src/main/java/com/wifiops/probe/ui/SessionHistoryScreen.kt`: safer labels and privacy-aware export copy.
- Modify `android/wifiops-probe/app/src/main/java/com/wifiops/probe/service/ProbeForegroundService.kt`: notification title/text and stop action if feasible.
- Modify `android/wifiops-probe/app/src/main/java/com/wifiops/probe/data/ProbeRecordDao.kt`: add query for latest record if needed.

## Tasks

### Task 1: Permission And Preflight Policy

- [ ] Add failing tests that Android 13+ runtime permissions include Nearby Wi-Fi and notifications but not fine location.
- [ ] Add failing tests that notification denial is represented as `Limited data`, not `Blocked`.
- [ ] Update `PermissionPolicy.kt` with `PreflightState`, `PreflightCheck`, and copy constants for Wi-Fi/location/notification states.
- [ ] Update `AndroidManifest.xml` so `NEARBY_WIFI_DEVICES` uses `android:usesPermissionFlags="neverForLocation"` and fine location is limited to Android 12L and below.
- [ ] Run `ANDROID_HOME=/Users/timotbar/Library/Android/sdk ./gradlew :app:testDebugUnitTest`.

### Task 2: Receiver Setup And Session Copy

- [ ] Add or update UI tests if feasible for copy-producing helpers; otherwise keep changes in composables and verify compilation.
- [ ] Update `PairScreen.kt` headings/actions from pairing language to receiver setup language.
- [ ] Update `SessionScreen.kt` actions to `Start session`, `Stop session`, `Change receiver`, and `Session history`.
- [ ] Update empty/error/session copy to use `Wi-Fi` and operational language.
- [ ] Run `ANDROID_HOME=/Users/timotbar/Library/Android/sdk ./gradlew :app:testDebugUnitTest`.

### Task 3: Active Session Dashboard Data

- [ ] Add DAO support for latest record by session.
- [ ] Add a lightweight `LatestTelemetrySummary` UI model that decodes the latest local record payload.
- [ ] Surface network, BSSID, signal, channel, last sample, last upload/receiver state, and data availability in `SessionScreen.kt`.
- [ ] Keep null/redacted values explicit instead of blank.
- [ ] Run `ANDROID_HOME=/Users/timotbar/Library/Android/sdk ./gradlew :app:testDebugUnitTest`.

### Task 4: History, Export, And Notification

- [ ] Change history empty state to `No sessions yet. Completed sessions will appear here.`
- [ ] Rename existing summary share to `Export summary` and add copy warning that raw records may contain network identifiers when raw export is implemented.
- [ ] Add safer delete labels; confirmation may remain future work if it requires broader state changes.
- [ ] Update foreground notification title to `Wi-Fi Ops Probe running`; include session and collection status.
- [ ] Add notification tap-to-open and stop action if feasible without broad architecture changes.
- [ ] Run `ANDROID_HOME=/Users/timotbar/Library/Android/sdk ./gradlew :app:lintDebug :app:testDebugUnitTest`.

## Acceptance Criteria

- User-facing copy uses `Wi-Fi`, not `WiFi`, except package/database/internal identifiers.
- The main app label is `Wi-Fi Ops Probe`.
- Android 13+ runtime permissions do not request fine location in the standard permission dialog.
- Notification permission denial can be represented as degraded/limited.
- Receiver setup, session, history, and notification labels match the spec.
- Active session shows at least latest SSID/BSSID/RSSI/channel availability when local records exist.
- Lint and unit tests pass with `ANDROID_HOME=/Users/timotbar/Library/Android/sdk`.

