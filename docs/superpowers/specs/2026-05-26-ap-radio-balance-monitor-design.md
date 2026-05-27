# AP Radio Balance Monitor Design

## Summary

Build a standalone live terminal monitor for Cisco Catalyst 9800 Wireless LAN Controllers that highlights AP radio client distribution across radio slots. The monitor will use one SSH session to the WLC, poll `show ap summary load-info`, parse AP-level radio load data, apply configurable AP filters, and render a Rich live view with visual per-slot client bars.

This tool will live beside the current single-client roaming tracker rather than being folded into it immediately. That keeps the first version focused on AP/radio balance without changing the existing `client_tracker.py` workflow.

## Goals

- List APs from a Catalyst 9800 WLC using SSH CLI polling.
- Show each AP radio slot separately with client count and utilization percentage.
- Make client imbalance visually obvious with per-slot bars.
- Support YAML include/exclude AP filters.
- Support optional slot include/exclude filters for environments where some slots should not be compared.
- Run as a live refreshing monitor by default.
- Sort imbalanced APs to the top.
- Keep parser logic testable without live WLC access.
- Avoid AP SSH sessions in the first version; the WLC command already contains the needed radio-slot load data.

## Non-Goals

- No web UI or graphical dashboard in the first version.
- No AP-level SSH polling.
- No band-name inference as a primary data model. The WLC reports slot numbers, so the monitor will display `Slot 0`, `Slot 1`, `Slot 2`, and `Slot 3`.
- No historical database.
- No automatic remediation, RF profile changes, or client steering actions.
- No integration into the unified client tracker command in the first version.

## Command Line

The first version will add:

```bash
python ap_radio_monitor.py
python ap_radio_monitor.py --refresh 30
python ap_radio_monitor.py --once
python ap_radio_monitor.py --only-imbalanced
python ap_radio_monitor.py --only-problem
python ap_radio_monitor.py --show-idle
python ap_radio_monitor.py --hide-idle
python ap_radio_monitor.py --limit 75
python ap_radio_monitor.py --busy-idle-util 20
python ap_radio_monitor.py --config config.yaml
```

Behavior:

- Default mode is live refresh.
- `--refresh` overrides the config refresh interval.
- `--once` prints one snapshot and exits.
- `--only-imbalanced` hides APs that are currently balanced.
- `--only-problem` shows `IMBALANCED`, `BUSY-IDLE`, `WARNING`, and `NO DATA` rows.
- `--show-idle` includes all `IDLE` rows.
- `--hide-idle` hides clean `IDLE` rows but still shows `BUSY-IDLE`.
- `--limit` caps displayed AP rows after priority sorting.
- `--busy-idle-util` sets the utilization threshold for zero-client APs to become `BUSY-IDLE`.
- `--config` allows alternate config files for different WLCs or AP groups.

## Configuration

The monitor will use the existing `wlc` credentials from `config.yaml`:

```yaml
wlc:
  host: "192.0.2.10"
  username: "admin"
  password: "changeme"
  enable: "changeme"
```

It will add an optional `ap_balance` section:

```yaml
ap_balance:
  refresh_seconds: 30
  include:
    - "NOC-*"
    - "LAB-*"
  exclude:
    - "*-TEST"
  included_slots: []
  excluded_slots: []
  only_imbalanced: false
  only_problem: false
  show_idle: false
  hide_idle: false
  limit: 75
  min_total_clients: 1
  busy_idle_utilization: 20
  imbalance:
    ratio_threshold: 10
    min_difference: 20
    include_zero_client_slots: true
```

Defaults:

- `refresh_seconds`: `30`
- `include`: empty list, meaning include all APs.
- `exclude`: empty list.
- `included_slots`: empty list, meaning include all numeric slots.
- `excluded_slots`: empty list.
- `only_imbalanced`: `false`
- `only_problem`: `false`
- `show_idle`: `false`
- `hide_idle`: `false`
- `limit`: `75`
- `min_total_clients`: `1`
- `busy_idle_utilization`: `20`
- `ratio_threshold`: `10`
- `min_difference`: `20`
- `include_zero_client_slots`: `true`

AP name patterns use shell-style wildcard matching, such as `NOC-*` and `*-TEST`.

## Data Source

The WLC polling command is:

```text
show ap summary load-info
```

Observed local input:

```text
AP Name                           Radio Mac       Slots  Clients       Slot0                   Slot1                   Slot2                   Slot3
                                                                Clients  Utilisation(%)  Clients  Utilisation(%)  Clients  Utilisation(%)  Clients  Utilisation(%)
---------------------------------------------------------------------------------------------------------------------------------------------------------------------

NOC-AP-MBY-1                      0c75.bdb5.6380   3      2       0        43              1        3               1        8               NA       NA
```

Cisco documented command-reference input uses a different identity column order:

```text
WTP-Mac         AP-Name          Tot-Slots Tot-Clients  Slot0                  Slot1                   Slot2
                                                        Clients Utilisation(%) Clients Utilisation(%)  Clients Utilisation(%)
---------------------------------------------------------------------------------------------------------------
0c75.bdb5.6380  NOC-AP-MBY-1     3         2            0       43             1       3               1       8
```

The parser will extract:

- AP name
- WTP/radio MAC, preserving the column label when known
- slot count
- total clients
- per-slot client count
- per-slot utilization percentage
- timestamp of the poll

The utilization percentage is radio/channel utilization for that slot. It is supporting RF context, not the basis for client-balance scoring.

The parser must be header-aware because observed WLC output and Cisco documented output may place AP name and MAC columns in different order. It will detect whether the identity columns are `AP Name`/`Radio Mac` or `WTP-Mac`/`AP-Name`, parse slot client/utilization pairs from the right side of each row, then assign identity fields from the detected header.

If total clients does not match the sum of numeric slot clients, the monitor keeps the WLC total as the authoritative total, keeps the slot values for radio distribution, and records a parser warning visible in the monitor footer.

## Data Model

`RadioSlotLoad`:

- `slot`: integer slot number
- `clients`: integer or `None` when WLC reports `NA`
- `utilization`: integer percentage or `None` when WLC reports `NA`

`APLoad`:

- `name`
- `radio_mac`
- `identity_label`
- `slots`
- `total_clients`
- `slot_loads`: sorted list of `RadioSlotLoad` entries by slot number
- `timestamp`
- `warnings`

`LoadInfoSnapshot`:

- `timestamp`
- `ap_loads`
- `parser_warnings`
- `poll_error`
- `raw_command`

`BalanceScore`:

- `status`: `OK`, `WARNING`, `IMBALANCED`, `IDLE`, `BUSY-IDLE`, or `INSUFFICIENT_DATA`
- `max_clients`
- `min_clients`
- `spread`
- `ratio`
- `reason`

## Distribution Logic

The monitor scores client balance across numeric radio slots only. Slots reported as `NA` are ignored.

`included_slots` and `excluded_slots` are applied before scoring. If `included_slots` is non-empty, only those slot numbers are considered. Any slot in `excluded_slots` is removed after the include filter.

If an AP's `total_clients` is below `min_total_clients`, zero-client APs are classified as `IDLE` or `BUSY-IDLE`; nonzero APs below the minimum are `INSUFFICIENT_DATA`.

Zero-client APs:

- `IDLE`: all active numeric slots have zero clients and every active utilization value is below `busy_idle_utilization`.
- `BUSY-IDLE`: all active numeric slots have zero clients and at least one active utilization value is at or above `busy_idle_utilization`.

`BUSY-IDLE` means the AP/radio is seeing channel activity while no clients are associated. It is not a definitive radio failure; it is an operational signal worth keeping visible.

When `include_zero_client_slots` is true, active zero-client slots are included in spread calculations. Ratio calculations use the smallest nonzero client count to avoid divide-by-zero, and `0 vs N` is represented through spread and reason text.

When `include_zero_client_slots` is false, zero-client slots are ignored for both spread and ratio.

If fewer than two comparable numeric slots remain after filtering, the status is `INSUFFICIENT_DATA`.

An AP is `IMBALANCED` when either condition is true:

- ratio is at least `ratio_threshold`
- spread is at least `min_difference`

An AP is `WARNING` when it is below the imbalanced thresholds but still noticeably skewed, using conservative fixed defaults:

- ratio is at least half the `ratio_threshold`
- or spread is at least half the `min_difference`

Otherwise the AP is `OK`.

`BalanceScore.status` values are `OK`, `WARNING`, `IMBALANCED`, `IDLE`, `BUSY-IDLE`, and `INSUFFICIENT_DATA`.

Examples:

- `1, 50, 0` with zeros included: imbalanced because spread is `50` and ratio is `50:1`.
- `1, 50, NA`: imbalanced because spread is `49` and ratio is `50:1`.
- `0, 50, NA`: imbalanced because spread is `50`; ratio is shown as `N/A`.
- `12, 18, 0`: usually OK or warning depending on thresholds.
- `0, 0, 0` with utilization `0, 0, 0`: `IDLE`.
- `0, 0, 0` with utilization `43, 31, 8`: `BUSY-IDLE`.
- `7, NA, NA`: insufficient data because fewer than two comparable slots remain.

Sorting severity order is `IMBALANCED`, `BUSY-IDLE`, `WARNING`, `OK`, `IDLE`, `INSUFFICIENT_DATA`. Within a severity, sort by spread descending, then ratio descending, treating `None` ratio as lower than any numeric ratio. `BUSY-IDLE` rows sort by highest slot utilization.

Default large-list behavior:

- Apply AP include/exclude filters first.
- Score all remaining APs.
- Sort by the severity order above.
- Display up to `limit` AP rows by default.
- Always prioritize problem states before clean `IDLE` rows.
- If `show_idle` is true, include idle APs in sorted order until the limit is reached.
- If `hide_idle` is true, omit `IDLE` rows but keep `BUSY-IDLE`.
- If `only_problem` is true, show only `IMBALANCED`, `BUSY-IDLE`, `WARNING`, and `INSUFFICIENT_DATA`.
- If `only_imbalanced` is true, preserve the existing behavior and show only `IMBALANCED`.

## Terminal Display

Default display is a compact Rich live table with one AP per row:

```text
Last 16:08:12 | 71 APs | Showing 71 | AP Radio

AP                         Cli  S0      S1      S2      S3  Balance
NOC-AP-MBY-1                 9  2c 4%   1c 3%   6c 1%   --  WARNING 6:1 Δ6
MBY-CON-SCC1_BAYSIDE_A-32    0  0c 43%  0c 31%  0c 8%   --  BUSY-IDLE
MBY-CON-SCC1_BAYSIDE_A-33    0  0c 0%   0c 0%   0c 0%   --  IDLE
```

Slot text is compact:

```text
0c 43%
```

Visual rules:

- `NA` slots render as `--`.
- `OK` rows use green status.
- `WARNING` rows use yellow status.
- `IMBALANCED` rows use red status.
- `BUSY-IDLE` rows use yellow or magenta status.
- `IDLE` rows use dim status.
- `INSUFFICIENT_DATA` rows use dim status.
- The table does not expand to fill very wide terminals.
- The title shows total AP count, displayed AP count, and last poll time.
- If rows are hidden by `limit` or filters, show a summary footer with hidden counts by status.

## Error Handling

- WLC connection/authentication failure exits with a clear error.
- Poll failure keeps the monitor running and shows the last successful data plus a visible poll error.
- Parser failure shows a parse error panel with a short excerpt of the unexpected output.
- Malformed rows are skipped and recorded as parser warnings; valid rows from the same poll still render.
- Unsupported command output or missing load-info headers is treated as a poll parse error with a visible message.
- AP rows with incomplete data render `--` for missing fields.
- Ctrl+C closes the WLC SSH session cleanly.

## Testing

Unit tests will cover:

- Parsing `show ap summary load-info` with Slot0-Slot3 data.
- Parsing Cisco documented `WTP-Mac`/`AP-Name` order.
- Parsing observed local `AP Name`/`Radio Mac` order.
- Parsing Slot0-Slot2 data.
- Parsing `NA` slot values.
- Skipping command echo, prompt text, and blank lines.
- Returning parser warnings for malformed rows among valid rows.
- Returning a parse error for unsupported command output.
- Preserving AP names with hyphens and mixed text.
- AP include/exclude filtering.
- Slot include/exclude filtering.
- Balance scoring for `1 vs 50`, `0 vs 50`, all-zero, and balanced cases.
- `IDLE` scoring for zero-client APs with low utilization.
- `BUSY-IDLE` scoring for zero-client APs with high utilization.
- Priority sorting places `BUSY-IDLE` above `WARNING` and `IDLE` below active `OK`.
- Display limiting hides lower-priority rows and reports hidden counts.
- Insufficient-data scoring for one comparable slot, no numeric slots, and totals below `min_total_clients`.
- Bar rendering does not crash on empty or missing slot data.

Manual validation:

- Run `python ap_radio_monitor.py --once` against a WLC.
- Run live mode and confirm refreshes do not reconnect every cycle.
- Confirm Ctrl+C cleans up the SSH session.

## Future Extensions

- Add CSV snapshot logging.
- Add a detail view that expands one AP into one line per slot.
- Add band labels when reliable WLC output is available to map slot to band.
- Add a mode that alerts only when an AP changes balance status.
- Integrate shared config/session helpers with the broader ClientTracker package after the planned refactor.
