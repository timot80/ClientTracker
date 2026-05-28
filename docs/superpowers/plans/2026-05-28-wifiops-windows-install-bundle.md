# WifiOps Windows Install Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows zip install bundle for WifiOps with a PowerShell installer, `.cmd` launchers, and offline wheelhouse dependencies.

**Architecture:** Mirror the existing macOS bundle: a repository build script creates a staged bundle with wheels, installer, README, launchers, and config template. The Windows installer creates an app-local venv under `%LOCALAPPDATA%\WifiOps`, installs from the local wheelhouse, preserves config, and runs a post-install check.

**Tech Stack:** Python packaging wheels, PowerShell, Windows batch launchers, pytest script-structure tests.

---

### Task 1: Baseline Guard Fix

**Files:**
- Modify: `ap_filesystem_audit/cli.py`
- Test: `tests/test_ap_filesystem_cli.py`

- [ ] Move `--reload-full-tmp` confirmation validation before `load_config`.
- [ ] Run `pytest tests/test_ap_filesystem_cli.py::test_main_requires_reload_confirmation -q`.
- [ ] Commit the fix.

### Task 2: Windows Packaging Assets

**Files:**
- Create: `packaging/windows/install.ps1`
- Create: `packaging/windows/README.txt`
- Create: `packaging/windows/launchers/*.cmd`
- Test: `tests/test_windows_install_bundle.py`

- [ ] Add tests for installer content, launcher content, and README guidance.
- [ ] Run tests and confirm they fail because files are missing.
- [ ] Add Windows installer and launcher assets.
- [ ] Run tests and confirm they pass.
- [ ] Commit the assets.

### Task 3: Windows Bundle Builder

**Files:**
- Create: `scripts/build-windows-install-bundle.ps1`
- Modify: `README.md`
- Test: `tests/test_windows_install_bundle.py`

- [ ] Add tests for the build script staging behavior and README Windows section.
- [ ] Run tests and confirm they fail.
- [ ] Add the PowerShell build script and README docs.
- [ ] Run tests and confirm they pass.
- [ ] Commit the builder and docs.

### Task 4: Verification

**Files:**
- Modify as needed based on test results.

- [ ] Run `pytest tests/test_windows_install_bundle.py tests/test_ap_filesystem_cli.py tests/test_fresh_install_validation_script.py -q`.
- [ ] Run `pytest -q`.
- [ ] Run `python -m py_compile ap_filesystem_audit/*.py wifiops/*.py`.
- [ ] Report the worktree path and exact commands for building the Windows zip.
