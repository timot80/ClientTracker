# Multi-WLC Command Aggregation Design

## Goal

Add multi-controller support for WLC-backed `wifiops` commands, starting with `wifiops c9800 ap-ports`.

The first implementation should let operators define multiple Catalyst 9800 WLCs in config, run `ap-ports` across all configured WLCs by default, optionally target one or more named WLCs, aggregate successful results, and report partial failures clearly.

## Scope

First command:

- `wifiops c9800 ap-ports`

Shared foundation:

- multi-WLC config parsing
- named WLC selection
- bounded concurrent execution
- partial failure reporting

Deferred commands:

- `wifiops c9800 radio`
- `wifiops c9800 client`

Those commands should keep current single-WLC behavior until they get their own design pass. The shared foundation should be shaped so they can adopt it later without duplicating config and selection logic.

## Configuration

Current single-WLC config remains valid:

```yaml
wlc:
  host: "10.0.0.10"
  credential_profile: "c9800-admin"
```

New multi-WLC config:

```yaml
wlcs:
  - name: "mby-1"
    host: "10.0.0.10"
    credential_profile: "c9800-admin"
  - name: "mby-2"
    host: "10.0.0.11"
    credential_profile: "c9800-admin"
```

If only `wlc:` exists, the resolver returns a one-item WLC set. The generated target name should be `default` unless the `wlc:` mapping contains an explicit `name`.

If `wlcs:` exists, `ap-ports` treats it as the default selected WLC set and runs all entries unless the operator narrows selection with `--wlc`.

If both `wlc:` and `wlcs:` exist, `wlcs:` wins for multi-WLC-aware commands. This avoids silently running one controller when the operator has defined a controller set.

## Credentials

Each WLC entry supports the same credential fields as the existing `wlc:` block:

- `username`
- `password`
- `enable`
- `credential_profile`
- `password_keyring`
- `enable_keyring`
- `read_timeout`

The common case is one shared credential profile:

```yaml
credentials:
  profiles:
    c9800-admin:
      username: "netops-admin"
      password_keyring: "wifiops:profile:c9800-admin:password"
      enable_keyring: "wifiops:profile:c9800-admin:enable"

wlcs:
  - name: "mby-1"
    host: "10.0.0.10"
    credential_profile: "c9800-admin"
  - name: "mby-2"
    host: "10.0.0.11"
    credential_profile: "c9800-admin"
```

Implementation should reuse `wifiops.credentials.resolve_credentials` rather than adding a second credential system.

## CLI Behavior

Default multi-WLC behavior for `ap-ports`:

```bash
wifiops c9800 ap-ports --config config.yaml
```

When `wlcs:` exists, this runs all configured WLCs.

Targeted WLC selection:

```bash
wifiops c9800 ap-ports --config config.yaml --wlc mby-1
wifiops c9800 ap-ports --config config.yaml --wlc mby-1 --wlc mby-2
```

Concurrency override:

```bash
wifiops c9800 ap-ports --config config.yaml --wlc-concurrency 5
```

Optional YAML default:

```yaml
wifiops:
  wlc_concurrency: 3
```

Default concurrency is `3`.

## AP Ports Output

`ap-ports` output should add a `WLC` column when multi-WLC execution is active. The source WLC must be visible for every AP port row.

For one selected WLC, either rendering style is acceptable:

- keep the `WLC` column for consistency, or
- omit it to preserve compact output

The first implementation should prefer consistency and always include `WLC` when the command is using the multi-WLC path.

Rows should keep existing `ap-ports` behavior:

- problem-only by default
- `--all` includes healthy rows
- `--include` and `--exclude` filter AP names
- `--speed-threshold` controls `LOW-SPEED`
- `LOW-SPEED`, `HALF-DUPLEX`, and `UNKNOWN` statuses remain unchanged

## Failure Handling

Partial failure behavior:

- successful WLC results are still displayed
- failed WLCs are shown in a footer/error section with WLC name and error
- command returns non-zero when any selected WLC fails
- command returns non-zero when all selected WLCs fail

If a WLC connects but produces unparseable `show ap ethernet statistics` output, treat that WLC as failed for exit-code purposes and include its parse error in the failure section.

If no AP port problems are found but one WLC failed, display the successful no-issues state plus the failed WLC section and return non-zero.

## Execution Model

Run WLCs concurrently with a bounded worker pool.

Default concurrency:

```text
3
```

The limit applies to selected WLCs only. If the operator selects one WLC, the command uses one worker.

Failures in one worker should not cancel other in-flight WLCs. Each worker returns either a successful snapshot or a structured failure record.

## Architecture

Add shared multi-WLC infrastructure under `wifiops`, for example:

- `wifiops/wlc_targets.py`: parse single `wlc:` and multi `wlcs:` config into named WLC targets.
- `wifiops/concurrency.py`: small bounded execution helper for WLC target fan-out.

Extend `ap_port_audit` with aggregation-aware models and rendering:

- add WLC identity to AP port rows or wrap rows with source WLC metadata
- render WLC-specific parser warnings and failures
- aggregate snapshots from multiple WLC targets

Avoid pushing multi-WLC logic into `ap_radio_monitor` or `client_tracker` in this change.

## Backward Compatibility

Existing commands and configs continue to work:

```yaml
wlc:
  host: "192.0.2.10"
  credential_profile: "c9800-admin"
```

Existing command:

```bash
wifiops c9800 ap-ports --config config.yaml
```

With only `wlc:`, this still runs one WLC. With `wlcs:`, this runs all WLCs.

## Testing

Tests should cover:

- single `wlc:` config resolves to one target named `default`
- single `wlc:` with `name` uses that name
- `wlcs:` config resolves all named targets
- `wlcs:` wins when both `wlc:` and `wlcs:` exist
- duplicate WLC names are rejected
- missing WLC names are rejected
- `--wlc` selects one or more named WLCs
- unknown selected WLC name returns a clear error
- default concurrency is `3`
- CLI `--wlc-concurrency` overrides YAML
- `ap-ports` aggregates successful rows from multiple WLCs
- output includes WLC names
- partial failure displays successful results and failed WLCs
- partial failure returns non-zero
- full failure returns non-zero

## Out Of Scope

- Multi-WLC live `radio` monitoring.
- Multi-WLC `client` lookup.
- Controller grouping by site, region, or tag.
- Automatic WLC discovery.
- CSV or JSON export.
- Retry policies beyond existing command/session behavior.
