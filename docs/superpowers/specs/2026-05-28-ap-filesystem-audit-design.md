# AP Filesystem Audit Design

## Goal

Add a `wifiops ap filesystems` command that discovers APs through configured WLCs, SSHes directly to each AP, runs `sh filesystems`, and flags full or nearly-full AP filesystems.

The motivating case is an AP where `/tmp` is full:

```text
none 95.4M 95.0M 376.0K 100% /tmp
```

The first version should be a one-shot audit command. It should not remediate filesystems or delete files.

## Fit Review

This command fits under a new `wifiops ap` namespace because it operates directly on APs after WLC discovery. It should not live under `wifiops c9800` because the WLC is only the discovery source; the command being audited is executed on AP SSH sessions.

The implementation should reuse existing project patterns:

- `wlcs:` and `wlc:` config handling from the multi-WLC `ap-ports` work.
- `--wlc` and `--wlc-concurrency` for controller selection and discovery fan-out.
- `ap:` config for AP SSH credentials.
- AP discovery from `show ap summary`, matching the AP rollout inventory script.
- bounded AP SSH fan-out, named `--ap-concurrency`, consistent with `--wlc-concurrency`.
- problem-only output by default, with `--all` for inventory-style output.
- AP name filters using the same wildcard semantics as AP radio and AP port commands.

The existing `scripts/ap-image-inventory.py` has useful discovery and direct AP SSH patterns, but the new command should be a first-class `wifiops` command with import-safe modules and tests rather than another ad hoc rollout script.

## Command Shape

Primary usage:

```bash
wifiops ap filesystems --config config.yaml
```

Filters and targeting:

```bash
wifiops ap filesystems --wlc wlc-89
wifiops ap filesystems --wlc wlc-89 --wlc wlc-93
wifiops ap filesystems --include "MBY-*"
wifiops ap filesystems --exclude "*TEST*"
wifiops ap filesystems --ap-name MBY-CON-SCC1_BAYSIDE_D-7
wifiops ap filesystems --ap-host 10.1.2.3
```

Display and thresholds:

```bash
wifiops ap filesystems --min-used-percent 95
wifiops ap filesystems --all
```

Concurrency:

```bash
wifiops ap filesystems --wlc-concurrency 3
wifiops ap filesystems --ap-concurrency 20
```

CSV export:

```bash
wifiops ap filesystems --output ap-filesystems.csv
wifiops ap filesystems --all --output ap-filesystems-all.csv
```

## Configuration

The command uses existing WLC config:

```yaml
wlcs:
  - name: wlc-89
    host: 10.23.76.89
    credential_profile: c9800-admin
```

It uses existing AP credentials:

```yaml
ap:
  username: admin
  password: ap-secret
  enable: ap-enable
```

Optional command defaults:

```yaml
ap_filesystems:
  include: ["MBY-*"]
  exclude: []
  min_used_percent: 95
  show_all: false
  ap_concurrency: 20
```

WLC discovery concurrency should use the existing global `wifiops.wlc_concurrency` default, with CLI override:

```yaml
wifiops:
  wlc_concurrency: 3
```

CLI flags override YAML values.

## Discovery And Filtering

Data flow:

1. Resolve WLC targets from `wlcs:` or backward-compatible `wlc:`.
2. Apply `--wlc` selection if provided.
3. Run `show ap summary` on selected WLCs.
4. Parse AP name and AP IP address from the summary output.
5. Deduplicate APs by AP name and IP address.
6. Apply exact filters:
   - `--ap-name`, repeatable
   - `--ap-host`, repeatable
7. Apply wildcard AP name filters:
   - `--include`, repeatable
   - `--exclude`, repeatable
8. SSH directly to each remaining AP.
9. Run `sh filesystems`.
10. Parse filesystem rows and render problem rows unless `--all` is set.

Filter order should be deterministic:

1. WLC selection.
2. exact AP name/IP selection.
3. include wildcards.
4. exclude wildcards.

If exact AP filters are provided, the command should only inspect those APs. Exact filters should still allow discovery by WLC first; direct AP-only operation without WLC discovery is out of scope for the first version.

## Parser

Ignore AP prompt lines such as:

```regex
^[A-Za-z0-9_.:-]+[>#]\s*$
```

Detect the table header:

```regex
^Filesystem\s+Size\s+Used\s+Available\s+Use%\s+Mounted\s+on$
```

Parse filesystem rows:

```python
FS_ROW_RE = re.compile(
    r"^(?P<filesystem>\\S+)\\s+"
    r"(?P<size>\\S+)\\s+"
    r"(?P<used>\\S+)\\s+"
    r"(?P<available>\\S+)\\s+"
    r"(?P<used_percent>\\d+)%\\s+"
    r"(?P<mount>\\S+)$"
)
```

The parser should keep rows like:

```text
devtmpfs 883.0M 0 883.0M 0% /dev
/dev/ubivol/part1 372.1M 79.7M 292.5M 21% /part1
none 95.4M 95.0M 376.0K 100% /tmp
```

Parser warnings should be retained for malformed filesystem-looking rows without failing the entire AP audit.

## Status Rules

For each filesystem row:

- `FULL`: `used_percent == 100`
- `HIGH`: `used_percent >= min_used_percent`
- `OK`: `used_percent < min_used_percent`
- `UNKNOWN`: row could not be parsed

Default `min_used_percent` is `95`.

The command should show only `FULL`, `HIGH`, and `UNKNOWN` rows by default. `--all` should include `OK` rows.

## Output

Render a Rich table with columns:

- WLC
- AP
- AP IP
- Filesystem
- Mount
- Size
- Used
- Available
- Use%
- Status
- Notes

Default title should show visible rows and total filesystem rows, for example:

```text
3 shown / 94 filesystems | AP Filesystem Audit
```

If no problem rows are found, print a success panel:

```text
No AP filesystem issues found
```

Partial AP failures should be shown in a footer/error section while successful AP results remain visible.

## CSV Export

The command should support CSV export with:

```bash
--output PATH
```

CSV export should write the same visibility set as the terminal by default:

- without `--all`, write problem filesystem rows plus failure rows
- with `--all`, write all parsed filesystem rows plus failure rows

CSV fields:

- `record_type`: `filesystem` or `failure`
- `wlc_name`
- `wlc_host`
- `ap_name`
- `ap_host`
- `filesystem`
- `mount`
- `size`
- `used`
- `available`
- `used_percent`
- `status`
- `notes`
- `error`

For filesystem rows, `error` is empty. For failure rows, filesystem fields are empty and `error` contains the WLC/AP failure reason.

The CSV writer should create parent directories when needed and overwrite the target path. Export failure should return non-zero and print a clear error.

## Failure Handling

WLC discovery failures:

- include WLC name and failure reason in the output
- continue with other WLCs
- return non-zero if any selected WLC fails

AP SSH or command failures:

- include AP name, AP IP, source WLC, and failure reason
- continue with other APs
- return non-zero if any selected AP fails

Parser behavior:

- APs with command output but no filesystem rows should be reported as AP failures.
- Malformed individual lines should become parser warnings if at least one row parses.

Exit code:

- `0` when all selected WLC/AP checks completed and no collection failures occurred, even if high/full filesystems were found.
- `1` when any selected WLC or AP failed to collect/parse.

This matches the current AP port audit behavior: problem rows are findings, not command failures.

## Concurrency

Use two bounded concurrency pools:

- WLC discovery: default `3`, from `wifiops.wlc_concurrency`, override `--wlc-concurrency`.
- AP filesystem checks: default `20`, from `ap_filesystems.ap_concurrency`, override `--ap-concurrency`.

AP concurrency should be clamped to at least `1`. It should not cancel in-flight AP checks when one AP fails.

## Module Structure

Add an import-safe package:

- `ap_filesystem_audit/models.py`: config, AP target, filesystem rows, failures, snapshots.
- `ap_filesystem_audit/parser.py`: `sh filesystems` parser.
- `ap_filesystem_audit/discovery.py`: WLC `show ap summary` discovery.
- `ap_filesystem_audit/scoring.py`: filters, status assignment, sorting.
- `ap_filesystem_audit/display.py`: Rich rendering.
- `ap_filesystem_audit/export.py`: CSV export.
- `ap_filesystem_audit/app.py`: orchestration.
- `ap_filesystem_audit/config.py`: YAML/config loader using existing WLC target resolver and AP credentials.
- `ap_filesystem_audit/cli.py`: command-specific argparse and runner.

Wire it through `wifiops ap filesystems`.

## Testing

Tests should cover:

- parsing the provided `sh filesystems` sample
- `FULL`, `HIGH`, and `OK` status assignment
- problem-only default output
- `--all` output
- include/exclude wildcard filters
- exact `--ap-name` and `--ap-host` filters
- WLC target selection with `--wlc`
- `--wlc-concurrency` and `--ap-concurrency`
- WLC discovery parses AP names and IPs from `show ap summary`
- AP SSH command dispatch runs `sh filesystems`
- AP collection failures are rendered and return non-zero
- WLC discovery failures are rendered and return non-zero
- successful findings return zero
- CSV export writes problem rows and failures by default
- CSV export with `--all` writes OK rows too
- CSV export failure returns non-zero
- `wifiops ap filesystems` delegation

## Out Of Scope

- deleting files or remediating full filesystems
- direct AP target mode without WLC discovery
- JSON export
- scheduled monitoring
- WLC-side commands for filesystem information
- integrating this into AP image rollout tooling
