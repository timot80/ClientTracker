# WifiOps Installer Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a macOS install bundle that installs WifiOps from a bundled wheelhouse, creates app-local launchers and config, and stays ready for a future Windows no-Python-knowledge installer.

**Architecture:** Add a shared config path helper so installed launchers can point all commands at `~/Applications/WifiOps/config.yaml`. Add macOS packaging assets under `packaging/macos/`, a repository build script that creates a self-contained Python wheelhouse and zip artifact, and tests that validate script behavior and artifact structure without depending on a real user install.

**Tech Stack:** Python 3.10+, setuptools wheels, POSIX shell, macOS `.command` installer, pytest.

---

## File Structure

- Create: `wifiops/config_paths.py`
  - Owns `WIFIOPS_CONFIG` lookup and default config path resolution.
- Modify: `wifiops/cli.py`
  - Uses shared config default and delegates check/local commands with config override.
- Modify: `client_tracker/cli.py`
  - Uses shared config default and accepts optional `--config`.
- Modify: `ap_radio_monitor/cli.py`, `ap_port_audit/cli.py`, `ap_filesystem_audit/cli.py`
  - Use shared config default.
- Create: `packaging/macos/install.command`
  - Installs from bundled wheelhouse into `~/Applications/WifiOps`.
- Create: `packaging/macos/README.txt`
  - End-user bundle instructions.
- Create: `packaging/macos/launchers/*`
  - App-local launcher scripts.
- Create: `scripts/build-macos-install-bundle.sh`
  - Builds `dist/wifiops-macos-<version>.zip`.
- Modify: `scripts/validate-fresh-install.sh`
  - Covers AP filesystem import/help.
- Modify: `README.md`
  - Adds easy install bundle section.
- Create: `tests/test_config_paths.py`
- Modify: `tests/test_wifiops_cli.py`
- Create: `tests/test_macos_install_bundle.py`
- Modify: `tests/test_fresh_install_validation_script.py`

## Tasks

### Task 1: Shared Config Path Override

- [ ] Write failing tests in `tests/test_config_paths.py` for default path and `WIFIOPS_CONFIG`.
- [ ] Write failing delegation tests in `tests/test_wifiops_cli.py` showing `wifiops check` and `wifiops client local` pass `--config <env path>` to `client_tracker.cli.main`.
- [ ] Add `wifiops/config_paths.py`.
- [ ] Update CLI modules to use `default_config_path(__file__)`.
- [ ] Update `client_tracker.cli` to accept `--config` and use it for `load_config` and check output.
- [ ] Update `wifiops.cli` to add `--config` for `check`, `client local`, and delegated client modes, preserving existing behavior.
- [ ] Run `python -m pytest tests/test_config_paths.py tests/test_wifiops_cli.py tests/test_cli.py -q`.
- [ ] Commit: `feat: support app-local wifiops config paths`.

### Task 2: macOS Packaging Assets

- [ ] Write failing script-shape and launcher tests in `tests/test_macos_install_bundle.py`.
- [ ] Add `packaging/macos/install.command` with strict shell safety, Python version check, exact one WifiOps wheel check, app-local venv install using `--no-index --find-links`, config preservation, launcher copy, and final `wifiops-check`.
- [ ] Add launchers that resolve `APP_DIR` from their installed location, export `WIFIOPS_CONFIG`, and pass through arguments.
- [ ] Add `packaging/macos/README.txt`.
- [ ] Run `python -m pytest tests/test_macos_install_bundle.py -q`.
- [ ] Commit: `feat: add macos install bundle assets`.

### Task 3: Bundle Builder

- [ ] Extend `tests/test_macos_install_bundle.py` with builder tests for expected bundle layout strings and zip creation behavior.
- [ ] Add `scripts/build-macos-install-bundle.sh` to build a WifiOps wheel, download dependency wheels into `wheels/`, stage installer assets, copy `config.example.yaml`, and create `dist/wifiops-macos-<version>.zip`.
- [ ] Run `python -m pytest tests/test_macos_install_bundle.py -q`.
- [ ] Run `scripts/build-macos-install-bundle.sh`.
- [ ] Commit: `feat: build macos wifiops install bundle`.

### Task 4: Validation And Docs

- [ ] Update `scripts/validate-fresh-install.sh` to import `ap_filesystem_audit` and run `wifiops ap filesystems --help`.
- [ ] Update `tests/test_fresh_install_validation_script.py` accordingly.
- [ ] Add README easy-install instructions.
- [ ] Run `scripts/validate-fresh-install.sh`.
- [ ] Run `python -m pytest -q`.
- [ ] Commit: `docs: document wifiops install bundle`.

## Self-Review

- Spec coverage: Covers config path resolution, correct AP filesystem command, full wheelhouse, macOS installer assets, launchers, builder, fresh-install validation, and docs.
- Specificity scan: All tasks name concrete files, commands, and verification steps.
- Type consistency: Command names and file paths match the current codebase and amended design spec.
