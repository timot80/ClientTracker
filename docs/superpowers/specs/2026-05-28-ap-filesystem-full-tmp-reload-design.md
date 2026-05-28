# AP Filesystem Full Tmp Reload Design

## Goal

Add an explicit remediation option to `wifiops ap filesystems` that reloads APs only when their `/tmp` filesystem is exactly `100%` used.

## Command Behavior

The audit remains read-only by default. Reload is enabled only when both flags are present:

```bash
wifiops ap filesystems --reload-full-tmp --confirm-reload-full-tmp
```

`--reload-full-tmp` without `--confirm-reload-full-tmp` exits with an error before discovery or AP login. The reload condition is intentionally narrow: at least one parsed filesystem row must have `mount == "/tmp"` and `used_percent == 100`.

Rows for other mounts at `100%` are still reported as filesystem issues, but they do not trigger reload. APs with parser failures, SSH failures, or no parsed filesystem rows are not reloaded.

## Reload Flow

For each AP, the command connects once, runs `terminal length 0`, runs `sh filesystems`, parses the output, then checks whether `/tmp` is full. If reload is enabled and the condition matches, it sends `reload`, waits for the confirmation prompt, and sends a raw carriage return.

Reload output is retained in the in-memory snapshot and exported to CSV. Any reload failure is treated as a command failure so the process exits non-zero.

## Output And CSV

CLI output keeps the existing filesystem table and adds a reload results table when reload mode is used. CSV exports add reload fields to each filesystem row:

- `reload_action`: empty, `skipped`, `triggered`, or `failed`
- `reload_output`: device response or failure detail

## Testing

Tests cover:

- CLI flag validation.
- Reload triggers only for `/tmp` at `100%`.
- Reload does not trigger for other full mounts.
- Reload command confirmation sends raw carriage return.
- CSV includes reload result fields.
