# AP Radio Client Count Accuracy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AP radio monitor display honest and score accurately when WLC total clients and per-slot radio client counts disagree.

**Architecture:** Keep the parser unchanged because it correctly preserves both WLC-reported total clients and per-slot radio clients from `show ap summary load-info`. Update display semantics so the WLC total is labeled as such, add a computed visible slot total, and update scoring so radio balance decisions use comparable slot counts rather than the WLC total gate. Keep changes local to AP radio monitor display/scoring and tests.

**Tech Stack:** Python 3.10+, Rich table rendering, pytest.

---

## Current Diagnosis

The count mismatch is real and is already present in WLC `show ap summary load-info` output. The parser preserves it:

- `ap.total_clients` is parsed from the WLC `Clients` / `Tot-Clients` field in `ap_radio_monitor/parser.py`.
- `slot.clients` values are parsed from individual slot fields in the same row.
- The table currently labels `ap.total_clients` as `Cli`, which implies it should match visible slot counts.
- The scorer currently gates on `ap.total_clients < config.min_total_clients` before fully trusting comparable slot counts.

The parser should not be changed in this work. It is useful to retain both values because the discrepancy itself is operationally meaningful.

## Files

- Modify: `ap_radio_monitor/display.py`
  - Rename `Cli` column to `WLC Tot`.
  - Add `Slot Tot` column computed from visible slot columns.
  - Keep per-slot cells unchanged.
  - Update metadata row cell widths for the added column.
- Modify: `ap_radio_monitor/scoring.py`
  - Use comparable slot total for `min_total_clients` gating.
  - Keep per-slot distribution scoring based on `_comparable_clients`.
- Modify: `tests/test_display.py`
  - Add display tests for `WLC Tot`, `Slot Tot`, and hidden-slot behavior.
  - Update existing header/cell-count assumptions for the added column.
- Modify: `tests/test_scoring.py`
  - Add tests where WLC total is stale/zero but slot counts are present.
  - Add tests where WLC total is nonzero but comparable slot total is zero.
- Optional docs after implementation: `README.md`
  - Clarify `WLC Tot` vs `Slot Tot` if CLI output examples are updated.

Do not modify:

- `ap_radio_monitor/parser.py` unless a new parser bug is independently proven.
- `ap_radio_monitor/models.py` unless implementation review proves a helper function cannot live in display/scoring.
- `config.yaml` or any secret-bearing local config.

## Task 1: Rename `Cli` To `WLC Tot`

**Files:**
- Modify: `ap_radio_monitor/display.py`
- Test: `tests/test_display.py`

- [ ] **Step 1: Write the failing display header test**

Add this test to `tests/test_display.py`:

```python
def test_build_monitor_table_labels_wlc_total_explicitly():
    snapshot = LoadInfoSnapshot(ap_loads=[make_ap("NOC-AP-1", [2, 2, 1, None])])
    console = Console(record=True, width=140)

    console.print(build_monitor_table(snapshot, APBalanceConfig()))
    rendered = console.export_text()

    assert "WLC Tot" in rendered
    assert "Cli" not in rendered
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_display.py::test_build_monitor_table_labels_wlc_total_explicitly -v
```

Expected before implementation:

```text
FAILED ... assert 'WLC Tot' in rendered
```

- [ ] **Step 3: Implement the column rename**

In `ap_radio_monitor/display.py`, change `_add_ap_columns`:

```python
def _add_ap_columns(table: Table, visible_slots: list[int]) -> None:
    table.add_column("AP", no_wrap=True)
    table.add_column("WLC Tot", justify="right", no_wrap=True)
    for slot_number in visible_slots:
        table.add_column(f"S{slot_number}", no_wrap=True)
    table.add_column("Balance", justify="right", no_wrap=True)
```

- [ ] **Step 4: Run the focused display test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_display.py::test_build_monitor_table_labels_wlc_total_explicitly -v
```

Expected:

```text
PASSED
```

- [ ] **Step 5: Run all display tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_display.py -v
```

Expected: existing tests may fail because column counts changed later in this plan; if only this rename is applied, update only assertions that explicitly expected `Cli`.

- [ ] **Step 6: Commit**

```bash
git add ap_radio_monitor/display.py tests/test_display.py
git commit -m "Clarify WLC total client column"
```

## Task 2: Add Computed `Slot Tot` Column

**Files:**
- Modify: `ap_radio_monitor/display.py`
- Test: `tests/test_display.py`

- [ ] **Step 1: Write a failing test for mismatched WLC and slot totals**

Add these helpers to `tests/test_display.py` if not already present:

```python
import re


def make_ap_with_wlc_total(name, wlc_total, clients, utilizations=None):
    utilizations = utilizations or [10 for _ in clients]
    return APLoad(
        name=name,
        radio_mac="0c75.bdb5.6380",
        identity_label="Radio Mac",
        slots=len(clients),
        total_clients=wlc_total,
        slot_loads=[
            RadioSlotLoad(slot=index, clients=value, utilization=utilizations[index])
            for index, value in enumerate(clients)
        ],
    )


def rendered_row_for(rendered: str, ap_name: str) -> str:
    return next(line for line in rendered.splitlines() if ap_name in line)
```

Add this test:

```python
def test_build_monitor_table_shows_wlc_total_and_slot_total_when_counts_disagree():
    ap = make_ap_with_wlc_total("MISMATCH-AP", 0, [1, 0, 0])
    snapshot = LoadInfoSnapshot(
        ap_loads=[ap]
    )
    console = Console(record=True, width=160)

    console.print(build_monitor_table(snapshot, APBalanceConfig()))
    rendered = console.export_text()

    assert "WLC Tot" in rendered
    assert "Slot Tot" in rendered
    assert "MISMATCH-AP" in rendered
    row = rendered_row_for(rendered, "MISMATCH-AP")
    assert re.search(r"MISMATCH-AP.*\b0\b.*\b1\b.*1c", row)
```

Update the display imports in the test file as needed:

```python
from ap_radio_monitor.display import build_monitor_table, render_slot_cell, render_slot_distribution
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_display.py::test_build_monitor_table_shows_wlc_total_and_slot_total_when_counts_disagree -v
```

Expected before implementation:

```text
FAILED ... assert 'Slot Tot' in rendered
```

- [ ] **Step 3: Add display helper for visible slot total**

In `ap_radio_monitor/display.py`, add:

```python
def _visible_slot_total(ap: APLoad, visible_slots: list[int]) -> int:
    visible = set(visible_slots)
    return sum(
        slot.clients
        for slot in ap.slot_loads
        if slot.slot in visible and slot.clients is not None
    )
```

- [ ] **Step 4: Add `Slot Tot` column**

In `_add_ap_columns`, insert the new column after `WLC Tot`:

```python
def _add_ap_columns(table: Table, visible_slots: list[int]) -> None:
    table.add_column("AP", no_wrap=True)
    table.add_column("WLC Tot", justify="right", no_wrap=True)
    table.add_column("Slot Tot", justify="right", no_wrap=True)
    for slot_number in visible_slots:
        table.add_column(f"S{slot_number}", no_wrap=True)
    table.add_column("Balance", justify="right", no_wrap=True)
```

- [ ] **Step 5: Render both total values in each AP row**

In `_ap_row_cells`, include `_visible_slot_total(ap, visible_slots)` immediately after `ap.total_clients`:

```python
def _ap_row_cells(ap: APLoad, score: BalanceScore, visible_slots: list[int]) -> list[Text]:
    style = STATUS_STYLES.get(score.status, "")
    values = [
        ap.name,
        str(ap.total_clients),
        str(_visible_slot_total(ap, visible_slots)),
        *(render_slot_cell(ap, slot_number) for slot_number in visible_slots),
        _balance_text(score),
    ]
    return [Text(value, style=style) for value in values]
```

- [ ] **Step 6: Update column-count helper**

In `_ap_column_count`, account for the new total column:

```python
def _ap_column_count(visible_slots: list[int]) -> int:
    return len(visible_slots) + 4
```

This is required so two-column display and metadata rows remain aligned.

- [ ] **Step 7: Update metadata row alignment**

In `_metadata_row`, add an extra blank cell for `Slot Tot`:

```python
def _metadata_row(label: str, message: str, visible_slots: list[int]) -> list[str]:
    if not visible_slots:
        return [label, "", "", message]
    return [label, "", "", message, *([""] * (len(visible_slots) - 1)), ""]
```

This preserves metadata alignment for both one-column and two-column layouts because `_wide_metadata_row` composes from `_metadata_row` plus `_ap_column_count`.

- [ ] **Step 8: Run focused test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_display.py::test_build_monitor_table_shows_wlc_total_and_slot_total_when_counts_disagree -v
```

Expected:

```text
PASSED
```

- [ ] **Step 9: Add two-column metadata alignment test**

Add this test to catch row-length mistakes for parser warnings, poll errors, hidden summaries, and two-column layout:

```python
def test_two_column_metadata_rows_align_with_slot_total_column():
    snapshot = LoadInfoSnapshot(
        ap_loads=[
            make_ap_with_wlc_total("VISIBLE-AP", 1, [1, 0]),
            make_ap_with_wlc_total("HIDDEN-AP", 0, [0, 0]),
        ],
        parser_warnings=["line 99: skipped malformed row"],
    )
    console = Console(record=True, width=220)

    console.print(
        build_monitor_table(
            snapshot,
            APBalanceConfig(display_columns=2, hide_idle=True),
        )
    )
    rendered = console.export_text()

    assert "Slot Tot" in rendered
    assert "Warning" in rendered
    assert "line 99: skipped malformed row" in rendered
    assert "Hidden by filter" in rendered
```

Expected behavior: this should fail before metadata alignment is fixed if Rich raises a row-length error or if metadata rows render under the wrong columns.

- [ ] **Step 10: Update existing display tests for added column**

Review failures from:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_display.py -v
```

Expected likely updates:

- `test_build_monitor_table_uses_two_side_by_side_row_groups` may need a wider console width if the added column wraps.
- Any assertions that count exact columns should expect one additional column per AP group.
- Assertions around compactness should still require the header to stay under the existing width target if it remains realistic; otherwise adjust the test to check no row wrapping in a 220-column terminal.
- Metadata rows for parser warnings, poll errors, and hidden summaries should still render without Rich row-length errors.

Do not weaken tests that verify slot visibility.

- [ ] **Step 11: Add hidden-slot total test**

Add this test to prove `Slot Tot` means visible slot total:

```python
def test_slot_total_uses_visible_slots_only():
    ap = make_ap_with_wlc_total("HIDDEN-SLOT-AP", 6, [5, 1, 0])
    snapshot = LoadInfoSnapshot(
        ap_loads=[ap]
    )
    console = Console(record=True, width=160)

    console.print(build_monitor_table(snapshot, APBalanceConfig(included_slots=(1, 2))))
    rendered = console.export_text()

    assert "HIDDEN-SLOT-AP" in rendered
    assert "S0" not in rendered
    assert "S1" in rendered
    assert "S2" in rendered
    row = rendered_row_for(rendered, "HIDDEN-SLOT-AP")
    assert re.search(r"HIDDEN-SLOT-AP.*\b6\b.*\b1\b.*1c", row)
```

- [ ] **Step 12: Add auto-excluded slot total display test**

Add this test to prove `clients=None` slots, which are used for auto-excluded admin-down radios, do not contribute to `Slot Tot` and still render as unavailable:

```python
def test_slot_total_ignores_auto_excluded_none_slots():
    ap = make_ap_with_wlc_total("AUTO-EXCLUDED-AP", 6, [None, 1, 0])
    snapshot = LoadInfoSnapshot(ap_loads=[ap])
    console = Console(record=True, width=160)

    console.print(build_monitor_table(snapshot, APBalanceConfig(included_slots=(0, 1, 2))))
    rendered = console.export_text()

    row = rendered_row_for(rendered, "AUTO-EXCLUDED-AP")
    assert "--" in row
    assert re.search(r"AUTO-EXCLUDED-AP.*\b6\b.*\b1\b.*--.*1c", row)
```

- [ ] **Step 13: Run display suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_display.py -v
```

Expected:

```text
PASSED
```

- [ ] **Step 14: Commit**

```bash
git add ap_radio_monitor/display.py tests/test_display.py
git commit -m "Show WLC and slot client totals separately"
```

## Task 3: Score Balance Using Comparable Slot Total

**Files:**
- Modify: `ap_radio_monitor/scoring.py`
- Test: `tests/test_scoring.py`

- [ ] **Step 1: Write a failing test for WLC total zero but slot clients present**

Add this helper to `tests/test_scoring.py` if needed:

```python
def make_ap_with_wlc_total(name, wlc_total, clients, utilizations=None):
    utilizations = utilizations or [10 for _ in clients]
    return APLoad(
        name=name,
        radio_mac="0c75.bdb5.6380",
        identity_label="Radio Mac",
        slots=len(clients),
        total_clients=wlc_total,
        slot_loads=[
            RadioSlotLoad(slot=index, clients=value, utilization=utilizations[index])
            for index, value in enumerate(clients)
        ],
    )
```

Add this test:

```python
def test_score_uses_slot_total_when_wlc_total_is_zero_but_slots_have_clients():
    ap = make_ap_with_wlc_total("STALE-WLC-TOTAL", 0, [1, 0, 0])

    score = score_ap(ap, APBalanceConfig())

    assert score.status == "OK"
    assert score.max_clients == 1
    assert score.min_clients == 0
    assert score.spread == 1
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_scoring.py::test_score_uses_slot_total_when_wlc_total_is_zero_but_slots_have_clients -v
```

Expected before implementation:

```text
FAILED ... status == 'IDLE' or 'INSUFFICIENT_DATA'
```

- [ ] **Step 3: Change the min-client gate**

In `score_ap`, compute `comparable_total` and use it instead of `ap.total_clients`:

```python
def score_ap(ap: APLoad, config: APBalanceConfig) -> BalanceScore:
    """Score radio client distribution for one AP."""
    comparable = _comparable_clients(ap, config)
    comparable_total = sum(comparable)
    if comparable_total < config.min_total_clients:
        if comparable and all(value == 0 for value in comparable):
            return _zero_client_score(ap, config)
        return BalanceScore(status="INSUFFICIENT_DATA", reason="below minimum clients")
```

Do not change the existing `len(comparable) < 2` behavior in this task.

- [ ] **Step 4: Run focused scoring test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_scoring.py::test_score_uses_slot_total_when_wlc_total_is_zero_but_slots_have_clients -v
```

Expected:

```text
PASSED
```

- [ ] **Step 5: Write a failing test for filtered slot totals**

Add this test to prove the threshold gate follows comparable slots, not hidden slots:

```python
def test_score_min_clients_uses_filtered_comparable_slot_total():
    ap = make_ap_with_wlc_total("FILTERED", 50, [50, 0, 0])

    score = score_ap(ap, APBalanceConfig(included_slots=(1, 2), min_total_clients=1))

    assert score.status == "IDLE"
    assert score.reason == "zero clients"
```

- [ ] **Step 6: Run the filtered-total test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_scoring.py::test_score_min_clients_uses_filtered_comparable_slot_total -v
```

Expected after Step 4:

```text
PASSED
```

- [ ] **Step 7: Add include-zero-disabled behavior test**

Add this test to document the exact behavior when zero-client slots are excluded from comparability:

```python
def test_score_min_clients_honors_include_zero_client_slots_false():
    ap = make_ap_with_wlc_total("ZERO-EXCLUDED", 50, [50, 0, 0])

    score = score_ap(
        ap,
        APBalanceConfig(
            included_slots=(1, 2),
            min_total_clients=1,
            include_zero_client_slots=False,
        ),
    )

    assert score.status == "INSUFFICIENT_DATA"
    assert score.reason == "below minimum clients"
```

Rationale: with `include_zero_client_slots=False`, selected zero-client slots are intentionally removed from `_comparable_clients`, leaving no comparable clients for the threshold gate.

- [ ] **Step 8: Add auto-excluded slot scoring test**

Add this test to prove `None` slots do not create insufficient data when other comparable slots have clients:

```python
def test_score_ignores_auto_excluded_none_slots():
    ap = make_ap_with_wlc_total("AUTO-EXCLUDED", 6, [None, 1, 0])

    score = score_ap(ap, APBalanceConfig(included_slots=(0, 1, 2)))

    assert score.status == "OK"
    assert score.max_clients == 1
    assert score.min_clients == 0
    assert score.spread == 1
```

- [ ] **Step 9: Run scoring suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_scoring.py -v
```

Expected:

```text
PASSED
```

- [ ] **Step 10: Commit**

```bash
git add ap_radio_monitor/scoring.py tests/test_scoring.py
git commit -m "Score AP balance from slot client totals"
```

## Task 4: Integration Verification

**Files:**
- No required code changes.
- Optional docs update: `README.md` if the rendered example still shows `Cli`.

- [ ] **Step 1: Run AP monitor focused suites**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_display.py tests/test_scoring.py tests/test_parser.py tests/test_app.py -v
```

Expected:

```text
PASSED
```

- [ ] **Step 2: Run full suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -v
```

Expected:

```text
PASSED
```

- [ ] **Step 3: Manual dry run against live WLC**

Run:

```bash
python3 ap_radio_monitor.py --once --config config.yaml
```

Expected:

- Header shows `WLC Tot` and `Slot Tot`.
- Per-slot cells remain `Nc U%`.
- Rows where WLC total and slot total disagree are no longer visually ambiguous.
- Balance status reflects slot distribution, not stale WLC total.

- [ ] **Step 4: Optional WifiOps dry run**

If `wifiops` is installed or runnable in editable mode, run:

```bash
python3 -m wifiops.cli c9800 radio --once --config config.yaml
```

Expected: same rendered table semantics as `ap_radio_monitor.py`.

- [ ] **Step 5: Commit any docs-only output updates**

Only if README examples are updated:

```bash
git add README.md
git commit -m "Document AP radio client total columns"
```

## Architecture Review Checklist

Reviewers should verify:

- Parser remains a faithful representation of raw WLC output.
- `WLC Tot` is never used as the source of truth for radio balance decisions.
- `Slot Tot` is computed from the same visible slot set shown in the row.
- Scoring threshold logic uses comparable slot counts and respects `included_slots`, `excluded_slots`, and `include_zero_client_slots`.
- Two-column display still aligns metadata, row cells, and right-side table groups.
- No local config, credentials, rollout target lists, or generated artifacts are committed.

## Code Writer Handoff

Implement tasks in order. Do not combine display and scoring changes in one commit because display semantics and scoring semantics are independently reviewable. Be careful with the current branch state: there may already be AP monitor changes in `ap_radio_monitor/scoring.py`, `tests/test_display.py`, and `tests/test_scoring.py`. Work with those changes; do not revert them.

Before editing, run:

```bash
git status --short --branch
git diff -- ap_radio_monitor/scoring.py tests/test_display.py tests/test_scoring.py
```

## Code Reviewer Handoff

Review with a bug-risk stance. Highest-risk areas:

- Rich table column alignment after adding `Slot Tot`.
- `score_ap` behavior for single comparable slots and zero-client APs.
- Hidden-slot semantics: `Slot Tot` must not imply all physical radios when config only displays a subset.
- Regression risk for `only_problem`, `hide_idle`, and two-column display.

Ask the code writer to provide:

- Before/after screenshot or captured Rich text from `ap_radio_monitor.py --once`.
- Focused pytest output for display, scoring, parser, and app tests.
- Full pytest output.
