# Android Probe UX Follow-Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add actionable preflight controls, raw record export, QR-first setup copy, and a lightweight operational theme.

**Architecture:** Extend the existing single-activity Compose app. Keep helper logic testable with small Kotlin functions and DAO queries. Avoid large navigation and camera-scanner work in this slice.

**Tech Stack:** Kotlin, Jetpack Compose Material 3, Room, kotlinx.serialization, Android share sheet, JUnit.

---

## Tasks

### Task 1: Raw Record Export

- [ ] Add DAO query for all records in a session ordered by sequence number.
- [ ] Add a testable helper that builds raw export JSON from session metadata and record payload JSON strings.
- [ ] Add unit tests proving export JSON includes session metadata, record count, and raw records.
- [ ] Wire `Export records` in `SessionHistoryScreen` and `MainActivity`.

### Task 2: Actionable Preflight

- [ ] Update `SessionScreen` to show action buttons for `PreflightCheck.recoveryAction`.
- [ ] Add callbacks for retry, open settings, and test receiver.
- [ ] Wire callbacks in `MainActivity`.
- [ ] Keep start behavior: request required runtime permissions first, then block on remaining blocking checks.

### Task 3: QR-First Receiver Setup Copy

- [ ] Update `PairScreen` IA to lead with `Scan receiver QR code`, `Paste setup JSON`, and `Enter receiver details`.
- [ ] Do not implement camera scanning unless it is small and safe; if deferred, make paste JSON the primary implemented action.

### Task 4: Lightweight Theme

- [ ] Create `ui/theme/WifiOpsTheme.kt`.
- [ ] Replace default `MaterialTheme` in `MainActivity`.
- [ ] Keep colors restrained and operational.

### Verification

Run from `android/wifiops-probe`:

```bash
ANDROID_HOME=/Users/timotbar/Library/Android/sdk ./gradlew :app:testDebugUnitTest
ANDROID_HOME=/Users/timotbar/Library/Android/sdk ./gradlew :app:lintDebug
```

