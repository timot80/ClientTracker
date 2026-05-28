# AP Filesystem Full Tmp Reload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add guarded AP reload support when `/tmp` is exactly `100%` used.

**Architecture:** Extend the AP filesystem audit config and snapshot models with reload options/results. Reuse the existing AP SSH session so collection and optional reload happen in one connection, then surface reload status in the Rich display and CSV export.

**Tech Stack:** Python, argparse, Netmiko, Rich, pytest.

---

### Task 1: CLI Guard And Config

**Files:**
- Modify: `ap_filesystem_audit/models.py`
- Modify: `ap_filesystem_audit/cli.py`
- Test: `tests/test_ap_filesystem_cli.py`
- Test: `tests/test_wifiops_cli.py`

- [ ] Add `reload_full_tmp` and `confirm_reload_full_tmp` booleans to `APFilesystemAuditConfig`.
- [ ] Add `--reload-full-tmp` and `--confirm-reload-full-tmp`.
- [ ] Add validation that `--reload-full-tmp` requires `--confirm-reload-full-tmp`.
- [ ] Run focused CLI tests and commit.

### Task 2: Reload Execution

**Files:**
- Modify: `ap_filesystem_audit/models.py`
- Modify: `ap_filesystem_audit/app.py`
- Test: `tests/test_ap_filesystem_app.py`

- [ ] Add `APReloadResult` with WLC/AP identity, action, and output.
- [ ] After parsing rows, trigger reload only when a row has `mount == "/tmp"` and `used_percent == 100`.
- [ ] Send `reload` with `send_command_timing`, then send `"\r"` when confirmation is requested.
- [ ] Treat reload exceptions or missing confirmation as failures.
- [ ] Run focused app tests and commit.

### Task 3: Display And CSV

**Files:**
- Modify: `ap_filesystem_audit/display.py`
- Modify: `ap_filesystem_audit/export.py`
- Test: `tests/test_ap_filesystem_display.py`
- Test: `tests/test_ap_filesystem_export.py`

- [ ] Render reload results when present.
- [ ] Add `reload_action` and `reload_output` CSV fields.
- [ ] Run focused display/export tests and commit.

### Task 4: Verification

**Files:**
- Modify as needed based on test failures.

- [ ] Run `pytest tests/test_ap_filesystem_*.py tests/test_wifiops_cli.py -q`.
- [ ] Run `pytest -q`.
- [ ] Run CLI help smoke.
- [ ] Do not run live reload without an explicit target and operator confirmation.
