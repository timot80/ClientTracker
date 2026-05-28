# WifiOps Windows Install Bundle Design

## Goal

Add a Windows install bundle for WifiOps that mirrors the macOS offline wheelhouse approach and gives operators a PowerShell installer plus `.cmd` launchers.

## Scope

The Windows bundle should:

- Build a `dist/wifiops-windows-<version>.zip` artifact.
- Include a local wheelhouse with the WifiOps wheel and runtime dependencies.
- Install into `%LOCALAPPDATA%\WifiOps` by default.
- Preserve an existing `config.yaml`.
- Copy `config.example.yaml` as a template.
- Create launchers for common commands.
- Run `wifiops-check.cmd` after install.

The first Windows bundle does not build an MSI, EXE, or embed Python. It requires Python 3.10+ to already be available as `py` or `python`.

## Installer Behavior

`packaging/windows/install.ps1` is the user entrypoint. It should:

1. Resolve the bundle directory.
2. Locate Python 3.10+ using `py -3` first, then `python`.
3. Create `%LOCALAPPDATA%\WifiOps\.venv`.
4. Install the bundled WifiOps wheel with `--no-index --find-links`.
5. Copy launchers into `%LOCALAPPDATA%\WifiOps\bin`.
6. Copy `templates\config.example.yaml` to the install directory.
7. Create `config.yaml` only when missing.
8. Run `bin\wifiops-check.cmd`.

## Launchers

Windows launchers should be `.cmd` wrappers that set:

```cmd
WIFIOPS_APP_DIR=%LOCALAPPDATA%\WifiOps
WIFIOPS_CONFIG=%WIFIOPS_APP_DIR%\config.yaml
```

and then call the installed venv entrypoint.

Required launchers:

- `wifiops.cmd`
- `wifiops-check.cmd`
- `wifiops-ap-radio.cmd`
- `wifiops-ap-ports.cmd`
- `wifiops-ap-filesystem.cmd`
- `wifiops-client-local.cmd`
- `wifiops-setup.cmd`

## Validation

Tests should verify:

- Windows packaging files exist and contain the expected install flow.
- The build script stages installer, launchers, config template, and wheelhouse.
- README documents Windows installation.
- The AP filesystem reload confirmation guard runs before config loading so fresh installs report the correct guard error.
