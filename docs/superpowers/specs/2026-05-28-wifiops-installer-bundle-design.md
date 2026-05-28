# WifiOps Installer Bundle Design

## Purpose

Make WifiOps installable by operators who should not need to understand Python, `pip`, virtual environments, package metadata, or PATH setup.

The first deliverable is a macOS-focused install bundle with a one-command or double-clickable installer. The design must leave a clean path to a later Windows bundle where users download something, run it, and get launchers without knowing Python exists.

## Users

- Wireless engineers who are comfortable running operational tools but do not want to debug Python packaging.
- Less technical Windows users who need a guided install and obvious launch points.
- Maintainers who need a repeatable release artifact that can be tested before distribution.

## Recommendation

Build a CLI bundle first, with launcher shortcuts and guided setup, not a GUI.

WifiOps already uses terminal workflows and Rich live tables. A GUI would create a separate product surface for configuration, progress, credentials, logs, and platform packaging. A CLI bundle preserves the current application behavior while removing Python setup friction.

## Scope

### In Scope For The First Implementation

- A repository-owned bundle builder for macOS release artifacts.
- A macOS installer script that:
  - Creates an app-local install directory.
  - Creates a private virtual environment.
  - Installs WifiOps from a bundled wheel, not from the source checkout.
  - Installs or offers to install the macOS Wi-Fi identity helper.
  - Creates launcher scripts for common workflows.
  - Runs `wifiops check` at the end.
- A release bundle layout that can later support Windows without redesign.
- Tests that validate bundle contents and installer script behavior without requiring a real end-user install.
- Documentation for creating and using the macOS bundle.

### Out Of Scope For The First Implementation

- A GUI launcher.
- A Windows installer implementation.
- Code signing, notarization, MSI creation, or enterprise software distribution tooling.
- Bundling Python itself on macOS.
- Storing real credentials or shipping a populated `config.yaml`.

## Bundle Layout

The generated macOS artifact should be a zip file with this structure:

```text
wifiops-macos/
  install.command
  README.txt
  wheels/
    wifiops-<version>-py3-none-any.whl
  launchers/
    wifiops
    wifiops-setup
    wifiops-check
    wifiops-ap-radio
    wifiops-ap-ports
    wifiops-ap-filesystem
    wifiops-client-local
  templates/
    config.example.yaml
```

`install.command` is the user entrypoint. It should also work when invoked from Terminal as `./install.command`.

The installed app-local directory should default to:

```text
~/Applications/WifiOps/
  .venv/
  bin/
    wifiops
    wifiops-setup
    wifiops-check
    wifiops-ap-radio
    wifiops-ap-ports
    wifiops-ap-filesystem
    wifiops-client-local
  config.example.yaml
```

The installer should not overwrite an existing `config.yaml`. If a config file is absent, it should copy `config.example.yaml` as a starting point or tell the user exactly where it is.

## Installer Behavior

The macOS installer should:

1. Resolve its own bundle directory.
2. Verify `python3` is available and is Python 3.10 or newer.
3. Create `~/Applications/WifiOps/.venv`.
4. Upgrade `pip` in that private venv.
5. Install the bundled `wifiops` wheel with `--force-reinstall`.
6. Copy launcher scripts into `~/Applications/WifiOps/bin`.
7. Copy `config.example.yaml` into `~/Applications/WifiOps/config.example.yaml`.
8. Offer to build/install the macOS Wi-Fi identity helper when the helper source and build script are present in the bundle or source checkout.
9. Run `~/Applications/WifiOps/bin/wifiops-check`.
10. Print final commands and paths.

The installer should be idempotent. Re-running it should refresh the venv package and launcher scripts while preserving user config and keyring data.

## Launcher Behavior

Launchers should be small shell scripts that call the venv-owned `wifiops` executable. They should avoid depending on shell startup files or global PATH state.

Recommended launchers:

- `wifiops`: direct pass-through to the installed CLI.
- `wifiops-setup`: prints config location, runs `wifiops credentials show-profiles`, and shows the credential setup command.
- `wifiops-check`: runs `wifiops check`.
- `wifiops-ap-radio`: runs `wifiops c9800 radio`.
- `wifiops-ap-ports`: runs `wifiops c9800 ap-ports`.
- `wifiops-ap-filesystem`: runs `wifiops c9800 ap-filesystem`.
- `wifiops-client-local`: runs `wifiops client local`.

Launcher scripts should pass through all user arguments.

## Windows Path

The first implementation should keep bundle concepts platform-neutral:

- A build step creates an artifact directory.
- A platform installer lays down an app-local runtime.
- Launchers call a single installed `wifiops` command.
- Config templates are copied but user config is preserved.
- Validation runs from the installed artifact, not from the source tree.

The later Windows implementation should target a download-and-run experience:

```text
wifiops-windows/
  install-windows.ps1
  wifiops.exe
  README.txt
  templates/
    config.example.yaml
```

The expected Windows implementation is a bundled executable, likely produced by PyInstaller or an equivalent packager. The installer should create Start Menu or Desktop shortcuts for setup, checks, and common workflows.

## Build Script

Add a bundle builder script such as:

```text
scripts/build-macos-install-bundle.sh
```

The builder should:

1. Clean a temporary bundle staging directory.
2. Build a WifiOps wheel.
3. Copy the wheel, installer, launchers, README, and config template into the staging directory.
4. Zip the staging directory into `dist/wifiops-macos-<version>.zip`.
5. Run a structural validation of the zip contents.

The builder may reuse logic from `scripts/validate-fresh-install.sh`, but release bundle creation and install validation should remain separate commands.

## Testing

Tests should cover:

- The bundle builder creates the expected staging layout.
- The installer script contains the key safety behaviors:
  - resolves its own directory,
  - creates an app-local venv,
  - installs from `wheels/wifiops-*.whl`,
  - preserves existing config,
  - runs `wifiops-check`.
- Launcher scripts call the installed venv executable and pass through arguments.
- The generated artifact includes `install.command`, launchers, wheel, README, and config template.

Integration validation should include:

```bash
scripts/build-macos-install-bundle.sh
scripts/validate-fresh-install.sh
python -m pytest -q
```

## Error Handling

The installer should fail early with clear messages when:

- `python3` is missing.
- Python is older than 3.10.
- No bundled wheel is present.
- The venv cannot be created.
- Package installation fails.

It should not continue after a partial package install failure. It should print the install directory and the command that failed.

## Documentation

The README should gain a short "Easy Install Bundle" section:

```text
Download wifiops-macos-<version>.zip, unzip it, then double-click install.command.
After install, run ~/Applications/WifiOps/bin/wifiops-check.
```

The bundle README should be more explicit and include:

- What gets installed.
- Where files go.
- How to run setup.
- How to run each common tool.
- How to uninstall by removing `~/Applications/WifiOps`.

## Acceptance Criteria

- A macOS zip bundle can be built from a clean checkout.
- A user can install WifiOps from that zip without running `pip` manually.
- Re-running the installer preserves local config.
- Common commands are exposed through launchers.
- The existing fresh-install validator still passes.
- The full test suite passes.
