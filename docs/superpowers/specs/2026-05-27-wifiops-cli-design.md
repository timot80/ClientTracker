# WifiOps CLI Design

## Summary

`wifiops` is the active command-line direction for this repository and supersedes the older unified client tracker package spec as the user-facing CLI design. The current version is an installable command-line entrypoint and thin router over the existing, tested CLIs:

- `client_tracker.cli` for Catalyst 9800 client tracking and local endpoint telemetry.
- `ap_radio_monitor.cli` for Catalyst 9800 AP radio client distribution monitoring.

The existing script workflows remain supported:

```bash
python client_tracker.py ...
python ap_radio_monitor.py ...
```

`wifiops` adds one discoverable command tree without removing the current script shims. The underlying packages remain responsible for tracker, monitor, parser, config, display, and polling behavior.

## Relationship To Earlier Specs

This spec supersedes the older [Unified Client Tracker Design](2026-05-26-unified-client-tracker-design.md) for user-facing CLI direction. The unified client tracker package remains an implementation component under `client_tracker`, but new command UX, packaging, and operator workflow decisions should be captured here first.

The older spec remains useful as implementation history for the `client_tracker` package. Going forward:

- `wifiops` is the preferred operator entrypoint.
- `client_tracker.py` and `ap_radio_monitor.py` remain backward-compatible shims.
- New provider groups, local-client commands, preflight checks, and packaging changes belong in this WifiOps spec.

## Updated Code Baseline

This design is grounded in the current `ClientTracker` code as of 2026-05-27:

- `client_tracker.py` is an executable shim that imports `client_tracker.cli.main`.
- `ap_radio_monitor.py` is an executable shim that imports `ap_radio_monitor.cli.main`.
- `wifiops` is implemented as a package with `wifiops/__init__.py` and `wifiops/cli.py`.
- `pyproject.toml` defines the installable console script `wifiops = "wifiops.cli:main"`.
- `client_tracker.cli` supports `mac`, `--mode infra|local|combined`, `--log`, `--interval`, and `--check`.
- `client_tracker.cli` uses a fixed config path at `ClientTracker/config.yaml`.
- `client_tracker.cli` defaults mode to `infra` when a MAC is supplied and `local` when no MAC is supplied.
- `client_tracker.cli` defaults intervals by mode: `infra=5.0`, `local=1.0`, and `combined=2.0`.
- `client_tracker.config` supports environment overrides for WLC and AP credentials.
- `client_tracker.local` uses `sudo -n wdutil info` as the macOS local telemetry source.
- `client_tracker.local` auto-detects the repo-owned macOS SSID/BSSID helper at `~/Applications/client-tracker-wifi-identity.app` when `local.identity_helper_path` is blank.
- The macOS helper source lives under `macos/WifiIdentityHelper` and is built by `scripts/build-macos-wifi-identity-helper.sh`.
- `ap_radio_monitor.cli` supports `--config`, `--refresh`, `--once`, `--only-imbalanced`, `--only-problem`, `--show-idle`, `--hide-idle`, `--limit`, and `--busy-idle-util`.
- `ap_radio_monitor.config` requires a config file and loads `wlc` plus optional `ap_balance` settings.
- Current CLI parser tests live in `tests/test_cli.py`.
- `wifiops` tests live in `tests/test_wifiops_cli.py`.

## Goals

- Maintain one installable command named `wifiops`.
- Keep `wifiops` as a routing layer in the first version.
- Preserve all existing script entrypoints and behavior.
- Expose current Catalyst 9800 and local-client functionality through grouped subcommands.
- Keep the command tree extensible for future Meraki commands.
- Make help text discoverable at the top level and at each command group.
- Keep tests import-safe and independent of WLC, AP, Meraki, and local Wi-Fi access.
- Put new operator-facing CLI design in `wifiops` first, using `client_tracker` and `ap_radio_monitor` as implementation packages.

## Non-Goals

- No Meraki implementation in the first version.
- No config format migration in the first version.
- No global config profile support in the first version.
- No change to `client_tracker.cli.CONFIG_PATH`.
- No removal, rename, or behavior change for `client_tracker.py` or `ap_radio_monitor.py`.
- No shell completion in the first version.
- No standalone binary packaging beyond standard Python package entrypoints.
- No duplication of client tracker or AP radio monitor business logic inside `wifiops`.

## Command Name

Use:

```bash
wifiops
```

Rejected names:

- `airctl`: already used by unrelated tools.
- `wlc-tools` and `c9800-tools`: too narrow for local-client and future Meraki tooling.
- `wireless-tools`: descriptive but long and generic.

## Command Tree

Initial commands:

```bash
wifiops c9800 radio
wifiops c9800 radio --once
wifiops c9800 radio --refresh 30
wifiops c9800 radio --only-imbalanced
wifiops c9800 radio --only-problem
wifiops c9800 radio --show-idle
wifiops c9800 radio --hide-idle
wifiops c9800 radio --limit 75
wifiops c9800 radio --busy-idle-util 20
wifiops c9800 radio --config config.yaml

wifiops c9800 client aa:bb:cc:dd:ee:ff
wifiops c9800 client aa:bb:cc:dd:ee:ff --mode infra
wifiops c9800 client aa:bb:cc:dd:ee:ff --mode combined
wifiops c9800 client aa:bb:cc:dd:ee:ff --log roam.csv
wifiops c9800 client aa:bb:cc:dd:ee:ff --interval 5

wifiops client local
wifiops client local --interval 1
wifiops client local --log local.csv
wifiops client identity

wifiops check
```

Reserved future commands:

```bash
wifiops meraki aps
wifiops meraki clients
wifiops meraki client <mac>
wifiops doctor
wifiops version
```

`wifiops meraki` should not appear as an implemented command in the first version unless it only prints a clear "not implemented" message. Prefer omitting it until there is real Meraki behavior.

## Provider-First Layout

Provider-backed tools live under provider names:

- `wifiops c9800 ...`
- `wifiops meraki ...` in a future version

Local endpoint tools live under:

- `wifiops client ...`

Reasons:

- Catalyst 9800 and Meraki will have different authentication, config, APIs, data models, and failure modes.
- Provider-first help remains scannable as the toolkit grows.
- Local endpoint telemetry is not tied to a controller or cloud provider.

## Packaging

`pyproject.toml` exists at the `ClientTracker` project root with a console script:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "wifiops"
version = "0.1.0"
description = "Wireless operations CLI tools for Cisco Catalyst 9800 and local client telemetry"
requires-python = ">=3.10"
dependencies = [
  "netmiko>=4.3.0",
  "pyyaml>=6.0",
  "rich>=13.7.0",
  "colorama>=0.4.6",
]

[project.scripts]
wifiops = "wifiops.cli:main"

[tool.setuptools.packages.find]
include = ["ap_radio_monitor*", "client_tracker*", "wifiops*"]
```

Use setuptools package discovery for the existing packages and the new `wifiops` package. Keep `pytest` out of runtime dependencies; tests can continue using the existing `requirements.txt` unless the project later splits runtime and dev requirements.

Install locally with:

```bash
pip install .
wifiops --help
```

Editable development install:

```bash
pip install -e .
wifiops c9800 radio --once --config config.yaml
```

## Module Layout

Current files:

- `wifiops/__init__.py`: package marker and `__version__`.
- `wifiops/cli.py`: top-level argument parser, subcommand parser, and delegation router.

Reuse existing modules:

- `ap_radio_monitor.cli`
- `client_tracker.cli`

Do not move existing modules in the first version. The package layout should remain:

```text
ClientTracker/
  ap_radio_monitor.py
  client_tracker.py
  ap_radio_monitor/
  client_tracker/
  wifiops/
```

## Routing Behavior

The router delegates to existing `main(argv)` functions with translated arguments.

`wifiops c9800 radio ...` delegates to:

```python
ap_radio_monitor.cli.main(argv)
```

The forwarded arguments are exactly the arguments after `radio`.

`wifiops c9800 client <mac> ...` delegates to:

```python
client_tracker.cli.main(translated_argv)
```

Translation rules:

- Preserve the positional MAC.
- If `--mode` is omitted, append `--mode infra`.
- Allow only `--mode infra` and `--mode combined`.
- Preserve `--log`.
- Preserve `--interval`.

Examples:

```text
wifiops c9800 client aa:bb:cc:dd:ee:ff
-> client_tracker.cli.main(["aa:bb:cc:dd:ee:ff", "--mode", "infra"])

wifiops c9800 client aa:bb:cc:dd:ee:ff --mode combined --interval 2
-> client_tracker.cli.main(["aa:bb:cc:dd:ee:ff", "--mode", "combined", "--interval", "2"])
```

`wifiops client local ...` delegates to:

```python
client_tracker.cli.main(translated_argv)
```

Translation rules:

- Always include `--mode local`.
- Preserve `--log`.
- Preserve `--interval`.
- Do not accept a MAC under `wifiops client local`.

Example:

```text
wifiops client local --interval 1
-> client_tracker.cli.main(["--mode", "local", "--interval", "1"])
```

`wifiops client identity` is the preferred place for macOS helper lifecycle management. It should build/install and/or run the repo-owned helper without requiring users to know the app bundle path. If implemented as part of the first local-client hardening pass, it should wrap:

```bash
scripts/build-macos-wifi-identity-helper.sh
~/Applications/client-tracker-wifi-identity.app/Contents/MacOS/client-tracker-wifi-identity
```

If the command is not implemented yet, it should either be omitted from the parser or return a clear non-zero "not implemented" message. Do not silently no-op.

`wifiops check` delegates to:

```python
client_tracker.cli.main(["--check"])
```

This keeps the first version aligned with the existing client tracker setup check. A later `wifiops doctor` can validate AP radio monitor config and provider-specific dependencies.

## macOS Local Telemetry

macOS local telemetry depends on two pieces:

- `sudo -n wdutil info` for RF and IP telemetry.
- The repo-owned `client-tracker-wifi-identity.app` helper for SSID/BSSID when macOS redacts `wdutil` output.

`wifiops client local` and `wifiops c9800 client --mode combined` perform a sudo preflight on macOS before delegating to `client_tracker.cli`. If `sudo -n -v` is not ready, `wifiops` exits before opening the live UI and tells the user to run:

```bash
sudo -v
```

The sudo preflight is not required for `wifiops c9800 client --mode infra`.

The helper is not a third-party runtime dependency. It is built from source in this repo:

```bash
scripts/build-macos-wifi-identity-helper.sh
```

The installed helper app is launched through LaunchServices so macOS Location Services permission attaches to the app bundle:

```bash
open -W -n ~/Applications/client-tracker-wifi-identity.app --args --output <tempfile>
```

When `client_tracker` itself is running with sudo, it launches that helper as `SUDO_USER` and writes helper output through a temp file owned by the original user.

## Argument Surface

`wifiops c9800 radio` accepts the current AP radio monitor options:

- `--config`
- `--refresh`
- `--once`
- `--only-imbalanced`
- `--only-problem`
- `--show-idle`
- `--hide-idle`
- `--limit`
- `--busy-idle-util`

The mutual exclusions from `ap_radio_monitor.cli` must be preserved:

- `--only-imbalanced` conflicts with `--only-problem`.
- `--show-idle` conflicts with `--hide-idle`.

`wifiops c9800 client` accepts:

- positional `mac`
- `--mode infra|combined`
- `--log`
- `--interval`

`wifiops client local` accepts:

- `--log`
- `--interval`

`wifiops client identity` should accept no first implementation options unless we add explicit sub-actions such as `--install` or `--check`.

`wifiops check` accepts no first-version options.

## Error Handling

- `wifiops --help` exits successfully and shows top-level groups.
- `wifiops c9800 --help`, `wifiops c9800 radio --help`, `wifiops c9800 client --help`, and `wifiops client --help` show scoped help.
- Unknown commands print parser help and exit non-zero through `argparse`.
- Invalid `wifiops c9800 client --mode local` is rejected by the `wifiops` parser before delegation.
- On macOS, `wifiops client local` and `wifiops c9800 client --mode combined` reject execution before delegation when sudo is not primed.
- On macOS, `wifiops c9800 client --mode infra` does not require local sudo preflight.
- Delegated command runtime failures keep the existing behavior of the underlying tool.
- The router should return integer exit codes where delegated CLIs return them.
- If a delegated CLI calls `sys.exit`, the router does not catch it unless a test needs to assert it.

## Backward Compatibility

These commands continue to work:

```bash
python ap_radio_monitor.py --once
python ap_radio_monitor.py --once --config config.yaml
python client_tracker.py aa:bb:cc:dd:ee:ff
python client_tracker.py --mode local
python client_tracker.py aa:bb:cc:dd:ee:ff --mode combined --log roam.csv
```

The first `wifiops` implementation only adds a package and console script. It does not change the script shims.

## Testing

`tests/test_wifiops_cli.py` covers the router.

Unit tests should patch delegated `main` functions so no network, WLC, AP, or local wireless access is required.

Required tests:

- `wifiops --help` exits successfully and mentions `c9800`, `client`, and `check`.
- `wifiops c9800 radio --once --config config.yaml` delegates to `ap_radio_monitor.cli.main` with `["--once", "--config", "config.yaml"]`.
- `wifiops c9800 radio --only-problem --hide-idle --limit 10 --busy-idle-util 25` delegates with those exact arguments.
- `wifiops c9800 client aa:bb:cc:dd:ee:ff` delegates to `client_tracker.cli.main` with `["aa:bb:cc:dd:ee:ff", "--mode", "infra"]`.
- `wifiops c9800 client aa:bb:cc:dd:ee:ff --mode combined --interval 2` preserves mode and interval.
- `wifiops c9800 client aa:bb:cc:dd:ee:ff --mode local` exits with a parser error.
- `wifiops client local --interval 1 --log local.csv` delegates to `client_tracker.cli.main` with `["--mode", "local", "--interval", "1", "--log", "local.csv"]`.
- `wifiops client local` exits before delegation on macOS when sudo is not ready.
- `wifiops c9800 client <mac> --mode combined` exits before delegation on macOS when sudo is not ready.
- `wifiops c9800 client <mac>` in infra mode does not require macOS sudo preflight.
- `wifiops check` delegates to `client_tracker.cli.main(["--check"])`.
- Existing tests in `tests/test_cli.py` continue passing.

Manual validation:

```bash
pip install -e .
wifiops --help
wifiops c9800 --help
wifiops c9800 radio --help
wifiops c9800 client --help
wifiops client --help
wifiops c9800 radio --once --config config.yaml
sudo -v
wifiops client local --interval 1
python ap_radio_monitor.py --once --config config.yaml
python client_tracker.py --mode local
```

## Future Extensions

- Add `wifiops meraki ...` commands with Meraki Dashboard API config.
- Add config profile selection, such as `wifiops --profile lab c9800 radio`.
- Add shell completion.
- Add `wifiops doctor` to validate all configured providers and local telemetry prerequisites.
- Add `wifiops version`.
