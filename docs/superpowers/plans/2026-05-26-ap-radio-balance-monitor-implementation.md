# AP Radio Balance Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone live terminal monitor that polls Catalyst 9800 `show ap summary load-info`, shows each AP radio slot separately, and visually flags skewed client distribution.

**Architecture:** Keep the CLI executable as `ap_radio_monitor.py`, but place import-safe, testable internals in a small `ap_radio_monitor/` package. Pure parser, scoring, filtering, and display functions load without config files or network access; config loading and Netmiko sessions happen only in the CLI/app runner.

**Tech Stack:** Python 3.10+, pytest, PyYAML, Netmiko, Rich.

---

## File Structure

- Create `ap_radio_monitor/__init__.py`: package marker and version string.
- Create `ap_radio_monitor/models.py`: dataclasses for config, AP load rows, snapshots, and balance scores.
- Create `ap_radio_monitor/parser.py`: header-aware parser for `show ap summary load-info`.
- Create `ap_radio_monitor/scoring.py`: AP filtering, slot filtering, balance scoring, and row sorting.
- Create `ap_radio_monitor/display.py`: Rich table/panel rendering and inline bar formatting.
- Create `ap_radio_monitor/config.py`: import-safe YAML config loader with defaults.
- Create `ap_radio_monitor/wlc.py`: WLC SSH wrapper around Netmiko.
- Create `ap_radio_monitor/app.py`: one-shot and live monitor orchestration.
- Create `ap_radio_monitor.py`: executable CLI shim.
- Create `tests/`: pytest coverage for parser, scoring, config, and display helpers.
- Modify `requirements.txt`: add `pytest>=8.0.0`.
- Modify `README.md`: document AP radio monitor usage and config.

## Task 1: Package Skeleton And Models

**Files:**
- Create: `ap_radio_monitor/__init__.py`
- Create: `ap_radio_monitor/models.py`
- Create: `tests/test_models_import.py`

- [ ] **Step 1: Write the failing import-safety test**

```python
from ap_radio_monitor.models import (
    APBalanceConfig,
    APLoad,
    BalanceScore,
    LoadInfoSnapshot,
    RadioSlotLoad,
)


def test_models_import_without_config_or_network_access():
    slot = RadioSlotLoad(slot=0, clients=5, utilization=12)
    ap = APLoad(
        name="NOC-AP-1",
        radio_mac="0c75.bdb5.6380",
        identity_label="Radio Mac",
        slots=3,
        total_clients=5,
        slot_loads=[slot],
    )
    snapshot = LoadInfoSnapshot(ap_loads=[ap])
    config = APBalanceConfig()
    score = BalanceScore(status="OK", max_clients=5, min_clients=5, spread=0, ratio=1.0)

    assert snapshot.ap_loads[0].name == "NOC-AP-1"
    assert config.refresh_seconds == 30
    assert score.status == "OK"
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m pytest tests/test_models_import.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'ap_radio_monitor'`.

- [ ] **Step 3: Implement the minimal package and models**

Create `ap_radio_monitor/__init__.py`:

```python
"""AP radio distribution monitor for Cisco Catalyst 9800 WLCs."""

__version__ = "0.1.0"
```

Create `ap_radio_monitor/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class WLCConfig:
    host: str
    username: str
    password: str
    enable: str = ""


@dataclass(frozen=True)
class APBalanceConfig:
    refresh_seconds: int = 30
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    included_slots: tuple[int, ...] = ()
    excluded_slots: tuple[int, ...] = ()
    only_imbalanced: bool = False
    min_total_clients: int = 1
    ratio_threshold: float = 10.0
    min_difference: int = 20
    include_zero_client_slots: bool = True


@dataclass(frozen=True)
class AppConfig:
    wlc: WLCConfig
    ap_balance: APBalanceConfig = field(default_factory=APBalanceConfig)


@dataclass(frozen=True)
class RadioSlotLoad:
    slot: int
    clients: Optional[int]
    utilization: Optional[int]


@dataclass(frozen=True)
class APLoad:
    name: str
    radio_mac: str
    identity_label: str
    slots: int
    total_clients: int
    slot_loads: list[RadioSlotLoad]
    timestamp: datetime = field(default_factory=datetime.now)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LoadInfoSnapshot:
    ap_loads: list[APLoad] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    parser_warnings: list[str] = field(default_factory=list)
    poll_error: str = ""
    raw_command: str = "show ap summary load-info"


@dataclass(frozen=True)
class BalanceScore:
    status: str
    max_clients: int = 0
    min_clients: int = 0
    spread: int = 0
    ratio: Optional[float] = None
    reason: str = ""
```

- [ ] **Step 4: Run the test and verify it passes**

Run: `python -m pytest tests/test_models_import.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ap_radio_monitor tests/test_models_import.py
git commit -m "feat: add ap radio monitor models"
```

## Task 2: Header-Aware Load-Info Parser

**Files:**
- Create: `ap_radio_monitor/parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write failing parser tests**

```python
import pytest

from ap_radio_monitor.parser import LoadInfoParseError, parse_load_info


OBSERVED_OUTPUT = """
NOC-MBY-SSO-1#sh ap summary load-info
Load for five secs: 1%/0%; one minute: 2%; five minutes: 2%
Time source is NTP, 16:06:31.133 PDT Tue May 26 2026

AP Name                           Radio Mac       Slots  Clients       Slot0                   Slot1                   Slot2                   Slot3
                                                                Clients  Utilisation(%)  Clients  Utilisation(%)  Clients  Utilisation(%)  Clients  Utilisation(%)
---------------------------------------------------------------------------------------------------------------------------------------------------------------------

NOC-AP-MBY-1                      0c75.bdb5.6380   3      2       0        43              1        3               1        8               NA       NA
"""


DOCUMENTED_OUTPUT = """
WTP-Mac         AP-Name          Tot-Slots Tot-Clients  Slot0                  Slot1                   Slot2
                                                        Clients Utilisation(%) Clients Utilisation(%)  Clients Utilisation(%)
---------------------------------------------------------------------------------------------------------------
0c75.bdb5.6380  NOC-AP-MBY-1     3         2            0       43             1       3               1       8
"""


def test_parse_observed_ap_name_first_output():
    snapshot = parse_load_info(OBSERVED_OUTPUT)

    ap = snapshot.ap_loads[0]
    assert ap.name == "NOC-AP-MBY-1"
    assert ap.radio_mac == "0c75.bdb5.6380"
    assert ap.identity_label == "Radio Mac"
    assert ap.slots == 3
    assert ap.total_clients == 2
    assert [(slot.slot, slot.clients, slot.utilization) for slot in ap.slot_loads] == [
        (0, 0, 43),
        (1, 1, 3),
        (2, 1, 8),
        (3, None, None),
    ]


def test_parse_documented_wtp_mac_first_output():
    snapshot = parse_load_info(DOCUMENTED_OUTPUT)

    ap = snapshot.ap_loads[0]
    assert ap.name == "NOC-AP-MBY-1"
    assert ap.radio_mac == "0c75.bdb5.6380"
    assert ap.identity_label == "WTP-Mac"
    assert ap.total_clients == 2
    assert [(slot.slot, slot.clients, slot.utilization) for slot in ap.slot_loads] == [
        (0, 0, 43),
        (1, 1, 3),
        (2, 1, 8),
    ]


def test_parse_records_warning_when_total_disagrees_with_slot_sum():
    output = OBSERVED_OUTPUT.replace("   3      2       0", "   3      1       0")
    snapshot = parse_load_info(output)

    assert snapshot.ap_loads[0].total_clients == 1
    assert snapshot.ap_loads[0].warnings
    assert "slot sum 2 differs from total clients 1" in snapshot.parser_warnings[0]


def test_parse_skips_malformed_rows_but_keeps_valid_rows():
    output = OBSERVED_OUTPUT + "\\nthis row is not valid\\n"
    snapshot = parse_load_info(output)

    assert len(snapshot.ap_loads) == 1
    assert snapshot.parser_warnings


def test_parse_raises_for_unsupported_output():
    with pytest.raises(LoadInfoParseError, match="load-info header"):
        parse_load_info("Invalid input detected at '^' marker.")
```

- [ ] **Step 2: Run parser tests and verify they fail**

Run: `python -m pytest tests/test_parser.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'ap_radio_monitor.parser'`.

- [ ] **Step 3: Implement parser**

Implement `LoadInfoParseError` and `parse_load_info(output: str) -> LoadInfoSnapshot`.

Required behavior:

- Detect `AP Name` with `Radio Mac` as observed format.
- Detect `WTP-Mac` with `AP-Name` as documented format.
- Ignore command echoes, prompts, load/time lines, separators, and blank lines.
- Parse AP rows from the right side:
  - collect slot client/utilization pairs where values are integers or `NA`;
  - then read `slots` and `total_clients`;
  - then assign AP name/MAC according to detected header order.
- Return `LoadInfoSnapshot`.
- Skip malformed rows after the header and add parser warnings.
- Raise `LoadInfoParseError` when no supported header or no valid AP rows are found.

- [ ] **Step 4: Run parser tests and verify they pass**

Run: `python -m pytest tests/test_parser.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ap_radio_monitor/parser.py tests/test_parser.py
git commit -m "feat: parse wlc ap radio load info"
```

## Task 3: Filtering, Scoring, Sorting, And Bars

**Files:**
- Create: `ap_radio_monitor/scoring.py`
- Create: `ap_radio_monitor/display.py`
- Create: `tests/test_scoring.py`
- Create: `tests/test_display.py`

- [ ] **Step 1: Write failing scoring and display tests**

```python
from ap_radio_monitor.display import render_slot_distribution
from ap_radio_monitor.models import APBalanceConfig, APLoad, RadioSlotLoad
from ap_radio_monitor.scoring import filter_aps, score_ap, sort_rows


def make_ap(name, clients):
    return APLoad(
        name=name,
        radio_mac="0c75.bdb5.6380",
        identity_label="Radio Mac",
        slots=len(clients),
        total_clients=sum(value for value in clients if value is not None),
        slot_loads=[
            RadioSlotLoad(slot=index, clients=value, utilization=10)
            for index, value in enumerate(clients)
        ],
    )


def test_filter_aps_uses_include_and_exclude_patterns():
    aps = [make_ap("NOC-AP-1", [1, 2]), make_ap("LAB-AP-1", [1, 2]), make_ap("NOC-TEST", [1, 2])]
    config = APBalanceConfig(include=("NOC-*",), exclude=("*-TEST",))

    assert [ap.name for ap in filter_aps(aps, config)] == ["NOC-AP-1"]


def test_score_flags_one_vs_fifty_as_imbalanced():
    score = score_ap(make_ap("NOC-AP-1", [1, 50, 0]), APBalanceConfig())

    assert score.status == "IMBALANCED"
    assert score.spread == 50
    assert score.ratio == 50.0


def test_score_zero_vs_fifty_uses_spread_without_ratio():
    score = score_ap(make_ap("NOC-AP-1", [0, 50, None]), APBalanceConfig())

    assert score.status == "IMBALANCED"
    assert score.spread == 50
    assert score.ratio is None


def test_score_returns_insufficient_data_for_all_zero_or_one_slot():
    assert score_ap(make_ap("ZERO", [0, 0, 0]), APBalanceConfig()).status == "INSUFFICIENT_DATA"
    assert score_ap(make_ap("ONE", [7, None, None]), APBalanceConfig()).status == "INSUFFICIENT_DATA"


def test_slot_filters_limit_comparable_slots():
    config = APBalanceConfig(included_slots=(1, 2))
    score = score_ap(make_ap("NOC-AP-1", [50, 4, 5]), config)

    assert score.status == "OK"
    assert score.spread == 1


def test_sort_rows_places_imbalanced_first():
    aps = [make_ap("OK", [10, 12]), make_ap("BAD", [1, 50]), make_ap("WARN", [4, 14])]
    rows = sort_rows([(ap, score_ap(ap, APBalanceConfig())) for ap in aps])

    assert [ap.name for ap, _score in rows] == ["BAD", "WARN", "OK"]


def test_render_slot_distribution_uses_relative_bars_and_na_marker():
    ap = make_ap("NOC-AP-1", [1, 50, None])

    rendered = render_slot_distribution(ap, width=12)

    assert "S0 1 cl / 10% util" in rendered
    assert "S1 50 cl / 10% util" in rendered
    assert "S2 --" in rendered
    assert "████" in rendered
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m pytest tests/test_scoring.py tests/test_display.py -v`

Expected: FAIL because `scoring.py` and `display.py` do not exist.

- [ ] **Step 3: Implement scoring and bar rendering**

Implement:

- `filter_aps(aps, config)`.
- `score_ap(ap, config)`.
- `sort_rows(rows)`.
- `render_slot_distribution(ap, width=16)`.
- `build_monitor_table(snapshot, config)` returning a Rich renderable.

Use severity order `IMBALANCED`, `WARNING`, `OK`, `INSUFFICIENT_DATA`. Warning thresholds are half the configured imbalanced thresholds.

- [ ] **Step 4: Run tests and verify they pass**

Run: `python -m pytest tests/test_scoring.py tests/test_display.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ap_radio_monitor/scoring.py ap_radio_monitor/display.py tests/test_scoring.py tests/test_display.py
git commit -m "feat: score and render radio distribution"
```

## Task 4: Config Loader And CLI

**Files:**
- Create: `ap_radio_monitor/config.py`
- Create: `ap_radio_monitor.py`
- Create: `tests/test_config.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing config and CLI tests**

```python
import pytest

from ap_radio_monitor.config import load_config
from ap_radio_monitor import __version__


def test_load_config_applies_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wlc:
  host: "192.0.2.10"
  username: "admin"
  password: "secret"
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.wlc.host == "192.0.2.10"
    assert config.wlc.enable == ""
    assert config.ap_balance.refresh_seconds == 30
    assert config.ap_balance.ratio_threshold == 10


def test_load_config_reads_ap_balance_options(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wlc:
  host: "192.0.2.10"
  username: "admin"
  password: "secret"
ap_balance:
  refresh_seconds: 15
  include: ["NOC-*"]
  exclude: ["*-TEST"]
  included_slots: [1, 2]
  excluded_slots: [0]
  only_imbalanced: true
  min_total_clients: 5
  imbalance:
    ratio_threshold: 8
    min_difference: 12
    include_zero_client_slots: false
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.ap_balance.refresh_seconds == 15
    assert config.ap_balance.include == ("NOC-*",)
    assert config.ap_balance.excluded_slots == (0,)
    assert config.ap_balance.include_zero_client_slots is False


def test_load_config_requires_wlc_credentials(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("wlc: {host: 192.0.2.10}\\n", encoding="utf-8")

    with pytest.raises(ValueError, match="wlc.username"):
        load_config(path)
```

```python
from ap_radio_monitor import __version__
from ap_radio_monitor import __version__ as imported_version


def test_version_import_is_available():
    assert imported_version == __version__
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m pytest tests/test_config.py tests/test_cli.py -v`

Expected: FAIL because config loader and CLI import surface are incomplete.

- [ ] **Step 3: Implement config and CLI parser**

Implement:

- `load_config(path)` with defaults from the spec.
- Validation for `wlc.host`, `wlc.username`, and `wlc.password`.
- `parse_args(argv=None)` in `ap_radio_monitor.py` supporting `--config`, `--refresh`, `--once`, and `--only-imbalanced`.
- Keep network setup out of import time.

- [ ] **Step 4: Run tests and verify they pass**

Run: `python -m pytest tests/test_config.py tests/test_cli.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ap_radio_monitor/config.py ap_radio_monitor.py tests/test_config.py tests/test_cli.py
git commit -m "feat: load ap radio monitor config"
```

## Task 5: WLC Session And App Runner

**Files:**
- Create: `ap_radio_monitor/wlc.py`
- Create: `ap_radio_monitor/app.py`
- Modify: `ap_radio_monitor.py`
- Create: `tests/test_app.py`

- [ ] **Step 1: Write failing app tests**

```python
from ap_radio_monitor.app import collect_once
from ap_radio_monitor.models import APBalanceConfig


class FakeWLC:
    def __init__(self, output):
        self.output = output
        self.closed = False

    def get_load_info(self):
        return self.output

    def disconnect(self):
        self.closed = True


def test_collect_once_parses_output_from_wlc_session():
    output = """
AP Name                           Radio Mac       Slots  Clients       Slot0                   Slot1
                                                                Clients  Utilisation(%)  Clients  Utilisation(%)
-----------------------------------------------------------------------------------------------------
NOC-AP-1                          0c75.bdb5.6380   2      51      1        5               50       80
"""
    snapshot = collect_once(FakeWLC(output), APBalanceConfig())

    assert snapshot.ap_loads[0].name == "NOC-AP-1"
    assert snapshot.ap_loads[0].total_clients == 51
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m pytest tests/test_app.py -v`

Expected: FAIL because `ap_radio_monitor.app` does not exist.

- [ ] **Step 3: Implement WLC wrapper and app runner**

Implement:

- `WLCLoadInfoSession.connect()`.
- `WLCLoadInfoSession.get_load_info()` sending `show ap summary load-info`.
- `WLCLoadInfoSession.disconnect()`.
- `collect_once(session, config)`.
- `run_once(config, console)`.
- `run_live(config, console, refresh_seconds)`.
- Ctrl+C cleanup in the CLI `main()`.

- [ ] **Step 4: Run app tests and verify they pass**

Run: `python -m pytest tests/test_app.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ap_radio_monitor/wlc.py ap_radio_monitor/app.py ap_radio_monitor.py tests/test_app.py
git commit -m "feat: add ap radio monitor runner"
```

## Task 6: Documentation And Full Verification

**Files:**
- Modify: `README.md`
- Modify: `requirements.txt`

- [ ] **Step 1: Add pytest dependency**

Add to `requirements.txt`:

```text
pytest>=8.0.0
```

- [ ] **Step 2: Document usage**

Add README sections for:

- `python ap_radio_monitor.py`
- `python ap_radio_monitor.py --once`
- `python ap_radio_monitor.py --refresh 30`
- `python ap_radio_monitor.py --only-imbalanced`
- `ap_balance` YAML config
- explanation that utilization percentage is radio/channel utilization, not client percentage

- [ ] **Step 3: Run full verification**

Run:

```bash
python -m pytest -v
python -m py_compile client_tracker.py ap_radio_monitor.py ap_radio_monitor/*.py
```

Expected: all tests pass and py_compile exits 0.

- [ ] **Step 4: Commit**

```bash
git add README.md requirements.txt
git commit -m "docs: document ap radio monitor"
```
