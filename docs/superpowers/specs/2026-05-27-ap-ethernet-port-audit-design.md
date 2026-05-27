# AP Ethernet Port Audit Design

## Goal

Add a `wifiops c9800 ap-ports` command that audits Catalyst 9800 AP Ethernet uplinks and flags ports that are negotiated below the expected speed or running half duplex.

The command should use the existing WLC config and credential resolution paths, run one WLC command, parse the output into structured AP port rows, and render a concise terminal table that defaults to problem rows only.

## User Workflow

Primary examples:

```bash
wifiops c9800 ap-ports --config config.yaml
wifiops c9800 ap-ports --include "MBY-*"
wifiops c9800 ap-ports --exclude "*TEST*"
wifiops c9800 ap-ports --all
wifiops c9800 ap-ports --speed-threshold 1000
```

Default behavior shows only AP ports with a problem. `--all` includes healthy rows for inventory or validation.

## WLC Data Source

The primary command is:

```text
show ap ethernet statistics
```

The parser will treat each section beginning with `AP Name : <name>` as the current AP. Interface rows below that section contain:

```text
Interface Name      Status  Speed       Duplex  Rx Packets    Tx Packets    Discarded Packets
GigabitEthernet0    UP       5000 Mbps   Full    160345        47098         0
```

The initial parser will support speeds reported as `<number> Mbps` and duplex values such as `Full` and `Half`. Rows that do not match the expected format should be retained as parse warnings rather than crashing the whole command.

## Status Rules

Each AP interface row gets one or more status labels:

- `LOW-SPEED`: parsed speed is lower than the configured threshold.
- `HALF-DUPLEX`: duplex parses as half duplex.
- `UNKNOWN`: speed or duplex cannot be parsed.
- `OK`: speed is at or above threshold and duplex is full.

The default speed threshold is `1000 Mbps`. This catches 100 Mbps and 10 Mbps links while allowing current 2.5 Gbps and 5 Gbps AP uplinks to pass. The threshold is configurable with `--speed-threshold`.

If a row has multiple problems, the status column should show all relevant labels, for example `LOW-SPEED, HALF-DUPLEX`.

## Filtering

The command supports AP name filters that match the AP radio monitor conventions:

- `--include PATTERN`, repeatable
- `--exclude PATTERN`, repeatable

Patterns use shell-style wildcards. Includes are applied first when present, then excludes.

Filtering happens after parsing and before display. Parse warnings remain visible in the footer even if the malformed row would have been filtered out only when its AP name can be determined.

## Output

Render a Rich table with these columns:

- AP
- Interface
- Link Status
- Speed
- Duplex
- Port Status
- Notes

Problem rows should sort before healthy rows. Within each status group, sort by AP name and interface name for stable output.

When no problem rows exist and `--all` is not set, print a short success panel such as `No AP Ethernet port issues found`.

## Architecture

Add a small `ap_port_audit` package with import-safe modules:

- `models.py`: dataclasses for config, port rows, audit snapshots, and parse warnings.
- `parser.py`: parser for `show ap ethernet statistics`.
- `scoring.py`: AP filtering, status assignment, and sorting.
- `display.py`: Rich table/panel rendering.
- `wlc.py`: WLC session wrapper that runs `show ap ethernet statistics`.
- `config.py`: config loader that reuses the shared WLC credential resolver.
- `cli.py`: command-specific argparse handling and one-shot runner.

Wire `wifiops c9800 ap-ports` to this package. Do not add live polling in the first version; this is an audit command.

## Configuration

The command should work from existing `wlc` configuration:

```yaml
wlc:
  host: "10.0.0.10"
  username: "netops-admin"
  credential_profile: "c9800-admin"
```

Optional command defaults may live under:

```yaml
ap_ports:
  include: ["MBY-*"]
  exclude: ["*-TEST"]
  show_all: false
  speed_threshold: 1000
```

CLI flags override YAML values.

## Error Handling

Connection and command failures should produce a clear non-zero CLI error.

Parser failures for individual rows should be warnings attached to the snapshot. The command should still render rows it can parse. If no AP/interface rows can be parsed at all, return a non-zero error with an excerpt of the WLC output.

Unknown speed or duplex values should not fail the command. They should produce an `UNKNOWN` status so the operator can inspect them.

## Testing

Add unit tests for:

- Parsing the provided `show ap ethernet statistics` sample.
- LOW-SPEED detection below the default threshold.
- HALF-DUPLEX detection.
- UNKNOWN detection for missing or malformed speed/duplex.
- Problem-only default output.
- `--all` output including healthy rows.
- Include and exclude AP filters.
- CLI config loading and CLI override behavior.
- WLC command dispatch using `show ap ethernet statistics`.
- `wifiops c9800 ap-ports` delegation.

Run the full test suite before completion.

## Out Of Scope

- Live polling mode.
- Switch-side CDP/LLDP lookup.
- Per-AP model expected speed rules.
- Export formats such as CSV or JSON.
- Remediation or configuration changes.
