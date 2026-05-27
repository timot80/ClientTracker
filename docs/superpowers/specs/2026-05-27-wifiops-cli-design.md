# WifiOps CLI Design

## Summary

Create `wifiops`, a shareable command-line interface for wireless operations tools. The CLI will provide one stable entrypoint for current Catalyst 9800 tools and leave room for future Meraki and local-client toolsets.

The first version will route to existing functionality:

- AP radio distribution monitor from `ap_radio_monitor`.
- Catalyst 9800 client tracker from `client_tracker`.
- Local client telemetry through the existing client tracker local mode.

Existing script entrypoints remain supported so current workflows do not break.

## Goals

- Add one installable command named `wifiops`.
- Use an extensible command tree for provider-specific and local-client tools.
- Keep existing commands working:
  - `python client_tracker.py ...`
  - `python ap_radio_monitor.py ...`
- Preserve current config behavior in the first version.
- Make help text discoverable and grouped by toolset.
- Keep the implementation import-safe and testable without WLC, Meraki, or local wireless access.

## Non-Goals

- No Meraki implementation in the first CLI version.
- No config format migration in the first CLI version.
- No removal or rename of existing scripts.
- No shell completion in the first version.
- No binary packaging beyond standard Python package entrypoints.

## Command Name

Use:

```bash
wifiops
```

Rejected names:

- `airctl`: already used by several unrelated tools.
- `wlc-tools` and `c9800-tools`: too narrow for future Meraki and local-client tooling.
- `wireless-tools`: descriptive but long and generic.

## Command Tree

Initial commands:

```bash
wifiops c9800 radio
wifiops c9800 radio --once
wifiops c9800 radio --refresh 30
wifiops c9800 radio --only-imbalanced
wifiops c9800 radio --config config.yaml

wifiops c9800 client aa:bb:cc:dd:ee:ff
wifiops c9800 client aa:bb:cc:dd:ee:ff --mode infra
wifiops c9800 client aa:bb:cc:dd:ee:ff --mode combined
wifiops c9800 client aa:bb:cc:dd:ee:ff --log roam.csv
wifiops c9800 client aa:bb:cc:dd:ee:ff --interval 5

wifiops client local
wifiops client local --interval 1
wifiops client local --log local.csv

wifiops check
```

Future commands:

```bash
wifiops meraki aps
wifiops meraki clients
wifiops meraki client <mac>
wifiops client identity
```

## Provider-First Layout

Provider-backed tools live under provider names:

- `wifiops c9800 ...`
- `wifiops meraki ...`

Local tools live under:

- `wifiops client ...`

Reasoning:

- Catalyst 9800 and Meraki have different auth, config, APIs, and output models.
- Provider-first help is easier to scan as the toolkit grows.
- Local client commands are not tied to any controller or cloud provider.

## Packaging

Add `pyproject.toml` with a console script:

```toml
[project.scripts]
wifiops = "wifiops.cli:main"
```

The package will use existing project dependencies:

- `netmiko`
- `pyyaml`
- `rich`

`pytest` remains a development/test dependency for now unless the project later separates runtime and dev extras.

Users can install locally with:

```bash
pip install .
wifiops --help
```

Editable development install:

```bash
pip install -e .
wifiops c9800 radio --once
```

## Module Layout

Create:

- `wifiops/__init__.py`: package marker and version string.
- `wifiops/cli.py`: top-level argument parser and command router.

Reuse existing modules:

- `ap_radio_monitor.cli`
- `client_tracker.cli`

The router should delegate to existing `main(argv)` functions rather than duplicating business logic.

Expected routing:

- `wifiops c9800 radio ...` delegates to `ap_radio_monitor.cli.main(...)`.
- `wifiops c9800 client <mac> ...` delegates to `client_tracker.cli.main(...)` with `--mode infra` or `--mode combined`.
- `wifiops client local ...` delegates to `client_tracker.cli.main(...)` with `--mode local`.
- `wifiops check` delegates to `client_tracker.cli.main(["--check"])` for the first version.

## Backward Compatibility

These commands continue to work:

```bash
python ap_radio_monitor.py --once
python client_tracker.py aa:bb:cc:dd:ee:ff
python client_tracker.py --mode local
```

The first `wifiops` implementation only adds a new entrypoint. It does not remove or alter the existing script shims.

## Argument Mapping

`wifiops c9800 radio` accepts the same user-facing options as `ap_radio_monitor.py`:

- `--config`
- `--refresh`
- `--once`
- `--only-imbalanced`

`wifiops c9800 client` accepts the relevant infrastructure options:

- positional `mac`
- `--mode infra|combined`, default `infra`
- `--log`
- `--interval`

`wifiops client local` accepts local-client options:

- `--log`
- `--interval`

## Error Handling

- Unknown command prints command-specific help and exits non-zero.
- Delegated command errors keep the existing behavior from the underlying tool.
- `wifiops --help` shows top-level groups and examples.
- `wifiops c9800 --help`, `wifiops c9800 radio --help`, and `wifiops client --help` show scoped help.

## Testing

Unit tests will cover:

- `wifiops --help` exits successfully and mentions `c9800`, `client`, and `check`.
- `wifiops c9800 radio --once --config config.yaml` delegates to `ap_radio_monitor.cli.main` with the expected argv.
- `wifiops c9800 client <mac>` delegates to `client_tracker.cli.main` with `--mode infra`.
- `wifiops c9800 client <mac> --mode combined --interval 2` preserves mode and interval.
- `wifiops client local --interval 1` delegates to `client_tracker.cli.main` with `--mode local`.
- `wifiops check` delegates to `client_tracker.cli.main(["--check"])`.
- Existing script tests continue passing.

Manual validation:

```bash
pip install -e .
wifiops --help
wifiops c9800 radio --once --config config.yaml
wifiops client local --interval 1
python ap_radio_monitor.py --once --config config.yaml
python client_tracker.py --mode local
```

## Future Extensions

- Add `wifiops meraki ...` commands with Meraki Dashboard API config.
- Add config profile selection, such as `wifiops --profile lab c9800 radio`.
- Add shell completion.
- Add `wifiops doctor` or expand `wifiops check` to validate all configured providers.
- Add `wifiops version`.
