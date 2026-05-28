# WifiOps Windows Install Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows zip install bundle for WifiOps with a PowerShell installer, `.cmd` launchers, and offline wheelhouse dependencies.

**Architecture:** Mirror the existing macOS bundle: a repository build script creates a staged bundle with wheels, installer, README, launchers, and config template. The Windows installer creates an app-local venv under `%LOCALAPPDATA%\WifiOps` by default, supports `WIFIOPS_INSTALL_DIR` for custom paths, installs from the local wheelhouse without internet downloads, preserves config, and runs a post-install check.

**Tech Stack:** Python packaging wheels, PowerShell, Windows batch launchers, pytest script-structure tests.

---

### Task 1: Baseline Guard Fix

**Files:**
- Modify: `ap_filesystem_audit/cli.py`
- Test: `tests/test_ap_filesystem_cli.py`

- [x] Move `--reload-full-tmp` confirmation validation before `load_config`.
- [x] Run `pytest tests/test_ap_filesystem_cli.py::test_main_requires_reload_confirmation -q`.
- [x] Commit the fix.

### Task 2: Windows Packaging Assets

**Files:**
- Create: `packaging/windows/install.ps1`
- Create: `packaging/windows/README.txt`
- Create: `packaging/windows/launchers/*.cmd`
- Test: `tests/test_windows_install_bundle.py`

- [x] Add tests for installer content, launcher content, and README guidance.
- [x] Run tests and confirm they fail because files are missing.
- [x] Add Windows installer and launcher assets.
- [x] Run tests and confirm they pass.
- [x] Commit the assets.

### Task 3: Windows Bundle Builder

**Files:**
- Create: `scripts/build-windows-install-bundle.ps1`
- Modify: `README.md`
- Test: `tests/test_windows_install_bundle.py`

- [x] Add tests for the build script staging behavior and README Windows section.
- [x] Run tests and confirm they fail.
- [x] Add the PowerShell build script and README docs.
- [x] Run tests and confirm they pass.
- [x] Commit the builder and docs.

### Task 4: Verification

**Files:**
- Modify as needed based on test results.

- [x] Run `pytest tests/test_windows_install_bundle.py tests/test_macos_install_bundle.py tests/test_ap_filesystem_cli.py -q`.
- [x] Run `pytest -q`.
- [x] Run `python -m py_compile ap_filesystem_audit/*.py wifiops/*.py client_tracker/*.py ap_port_audit/*.py ap_radio_monitor/*.py`.
- [x] Report the worktree path and exact commands for building the Windows zip.

### Review Follow-Up

- [x] Windows admin review requested.
- [x] Developer review requested.
- [x] Removed online `pip install --upgrade pip` from `packaging/windows/install.ps1`.
- [x] Updated `.cmd` launchers to derive `WIFIOPS_APP_DIR` from `%~dp0\..`.
- [x] Updated the builder to read `pyproject.toml` through `$RootDir`.
- [x] Added regression coverage for the review findings.
- [x] Re-ran focused and full test suites.
- [x] Windows admin review approved.
- [x] Developer review approved.

### Remaining Manual Validation

- [ ] Run one real Windows smoke test with PowerShell before distributing a new bundle to operators.
