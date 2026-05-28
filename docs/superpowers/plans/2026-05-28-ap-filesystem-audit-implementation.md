# AP Filesystem Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `wifiops ap filesystems`, a one-shot AP filesystem audit that discovers APs through WLCs, SSHes to APs, runs `sh filesystems`, flags high/full filesystems, and optionally writes CSV.

**Architecture:** Create a focused `ap_filesystem_audit` package with import-safe parser, discovery, scoring, display, export, config, and app orchestration modules. Reuse existing `wifiops.wlc_targets`, `wifiops.concurrency`, AP credential config, and `wifiops` CLI delegation patterns.

**Tech Stack:** Python 3.10+, argparse, dataclasses, fnmatch, csv, Netmiko, PyYAML, Rich, pytest.

---

## Scope

Implement only `wifiops ap filesystems`.

Do not add remediation, file deletion, JSON export, direct AP-only mode without WLC discovery, scheduled monitoring, or integration into AP image rollout tooling.

## File Structure

- Create `ap_filesystem_audit/__init__.py`: package marker.
- Create `ap_filesystem_audit/models.py`: config, AP target, filesystem row, failure, snapshot models.
- Create `ap_filesystem_audit/parser.py`: parser for `sh filesystems`.
- Create `ap_filesystem_audit/discovery.py`: WLC `show ap summary` AP discovery.
- Create `ap_filesystem_audit/scoring.py`: filters, status assignment, sorting, visibility.
- Create `ap_filesystem_audit/display.py`: Rich table/panel rendering.
- Create `ap_filesystem_audit/export.py`: CSV writer.
- Create `ap_filesystem_audit/config.py`: YAML config loader using WLC target resolver and AP credentials.
- Create `ap_filesystem_audit/app.py`: WLC/AP fan-out and command orchestration.
- Create `ap_filesystem_audit/cli.py`: command parser and runner.
- Modify `wifiops/cli.py`: add `wifiops ap filesystems` parser and delegation.
- Modify `pyproject.toml`: include `ap_filesystem_audit*`.
- Modify `config.example.yaml`: document `ap_filesystems` defaults.
- Modify `README.md`: document command usage and CSV export.
- Add tests under `tests/test_ap_filesystem_*.py` and extend `tests/test_wifiops_cli.py`.

---

### Task 1: Models, Parser, And Scoring

**Files:**
- Create: `ap_filesystem_audit/__init__.py`
- Create: `ap_filesystem_audit/models.py`
- Create: `ap_filesystem_audit/parser.py`
- Create: `ap_filesystem_audit/scoring.py`
- Test: `tests/test_ap_filesystem_parser.py`
- Test: `tests/test_ap_filesystem_scoring.py`

- [ ] **Step 1: Write parser tests**

Create `tests/test_ap_filesystem_parser.py`:

```python
from ap_filesystem_audit.parser import parse_filesystems


SAMPLE = """
MBY-CON-SCC1_BAYSIDE_D-7#sh filesystems
Filesystem Size Used Available Use% Mounted on
devtmpfs 883.0M 0 883.0M 0% /dev
/sysroot 885.6M 202.0M 683.5M 23% /
tmpfs 1.0M 44.0K 980.0K 4% /dev/shm
/dev/ubivol/part1 372.1M 79.7M 292.5M 21% /part1
/dev/ubivol/part2 520.1M 81.2M 438.9M 16% /part2
none 95.4M 95.0M 376.0K 100% /tmp
MBY-CON-SCC1_BAYSIDE_D-7#
"""


def test_parse_filesystems_reads_rows_and_ignores_prompts():
    snapshot = parse_filesystems(SAMPLE)

    assert len(snapshot.rows) == 6
    tmp = snapshot.rows[-1]
    assert tmp.filesystem == "none"
    assert tmp.size == "95.4M"
    assert tmp.used == "95.0M"
    assert tmp.available == "376.0K"
    assert tmp.used_percent == 100
    assert tmp.mount == "/tmp"
    assert snapshot.parser_warnings == []


def test_parse_filesystems_records_malformed_table_rows():
    output = """
Filesystem Size Used Available Use% Mounted on
bad row that should not parse
none 95.4M 95.0M 376.0K 100% /tmp
"""

    snapshot = parse_filesystems(output)

    assert len(snapshot.rows) == 1
    assert snapshot.parser_warnings
    assert "bad row" in snapshot.parser_warnings[0]
```

- [ ] **Step 2: Write scoring tests**

Create `tests/test_ap_filesystem_scoring.py`:

```python
from ap_filesystem_audit.models import APFilesystemAuditConfig, APFilesystemRow, APTarget
from ap_filesystem_audit.scoring import filter_ap_targets, row_status, visible_rows


def fs_row(ap_name="AP-1", used_percent=95):
    return APFilesystemRow(
        wlc_name="wlc-1",
        wlc_host="192.0.2.10",
        ap_name=ap_name,
        ap_host="10.0.0.1",
        filesystem="none",
        mount="/tmp",
        size="95.4M",
        used="95.0M",
        available="376.0K",
        used_percent=used_percent,
    )


def test_row_status_flags_full_high_and_ok():
    assert row_status(fs_row(used_percent=100), APFilesystemAuditConfig()) == "FULL"
    assert row_status(fs_row(used_percent=95), APFilesystemAuditConfig()) == "HIGH"
    assert row_status(fs_row(used_percent=94), APFilesystemAuditConfig()) == "OK"


def test_visible_rows_default_shows_only_problem_rows():
    rows = [fs_row("OK", 10), fs_row("FULL", 100)]

    assert [row.ap_name for row in visible_rows(rows, APFilesystemAuditConfig())] == ["FULL"]


def test_visible_rows_all_includes_ok_rows():
    rows = [fs_row("OK", 10), fs_row("FULL", 100)]

    assert [row.ap_name for row in visible_rows(rows, APFilesystemAuditConfig(show_all=True))] == ["OK", "FULL"]


def test_filter_ap_targets_applies_exact_then_wildcard_filters():
    targets = [
        APTarget(wlc_name="wlc-1", wlc_host="192.0.2.10", name="MBY-1", host="10.0.0.1"),
        APTarget(wlc_name="wlc-1", wlc_host="192.0.2.10", name="MBY-TEST", host="10.0.0.2"),
        APTarget(wlc_name="wlc-1", wlc_host="192.0.2.10", name="OTHER-1", host="10.0.0.3"),
    ]

    config = APFilesystemAuditConfig(include=("MBY-*",), exclude=("*TEST",))

    assert [target.name for target in filter_ap_targets(targets, config)] == ["MBY-1"]
    assert [target.name for target in filter_ap_targets(targets, APFilesystemAuditConfig(ap_names=("OTHER-1",)))] == ["OTHER-1"]
    assert [target.host for target in filter_ap_targets(targets, APFilesystemAuditConfig(ap_hosts=("10.0.0.2",)))] == ["10.0.0.2"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
pytest tests/test_ap_filesystem_parser.py tests/test_ap_filesystem_scoring.py -q
```

Expected: FAIL because `ap_filesystem_audit` does not exist.

- [ ] **Step 4: Implement models**

Create `ap_filesystem_audit/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `ap_filesystem_audit/models.py` with these dataclasses:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from wifiops.wlc_targets import WlcTarget


@dataclass(frozen=True)
class APCredentials:
    username: str
    password: str
    enable: str = ""


@dataclass(frozen=True)
class APFilesystemAuditConfig:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    ap_names: tuple[str, ...] = ()
    ap_hosts: tuple[str, ...] = ()
    min_used_percent: int = 95
    show_all: bool = False
    ap_concurrency: int = 20
    output: str = ""


@dataclass(frozen=True)
class APFilesystemConfig:
    wlc_targets: list[WlcTarget]
    ap_credentials: APCredentials
    audit: APFilesystemAuditConfig = field(default_factory=APFilesystemAuditConfig)
    wlc_concurrency: int = 3


@dataclass(frozen=True)
class APTarget:
    wlc_name: str
    wlc_host: str
    name: str
    host: str


@dataclass(frozen=True)
class APFilesystemRow:
    wlc_name: str = ""
    wlc_host: str = ""
    ap_name: str = ""
    ap_host: str = ""
    filesystem: str = ""
    mount: str = ""
    size: str = ""
    used: str = ""
    available: str = ""
    used_percent: int | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class APFilesystemFailure:
    wlc_name: str = ""
    wlc_host: str = ""
    ap_name: str = ""
    ap_host: str = ""
    message: str = ""


@dataclass(frozen=True)
class APFilesystemSnapshot:
    rows: list[APFilesystemRow] = field(default_factory=list)
    failures: list[APFilesystemFailure] = field(default_factory=list)
    parser_warnings: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
```

- [ ] **Step 5: Implement parser and scoring**

Create `ap_filesystem_audit/parser.py` implementing `parse_filesystems(output: str) -> APFilesystemSnapshot`.

Create `ap_filesystem_audit/scoring.py` implementing:

```python
def row_status(row: APFilesystemRow, config: APFilesystemAuditConfig) -> str
def filter_ap_targets(targets: list[APTarget], config: APFilesystemAuditConfig) -> list[APTarget]
def visible_rows(rows: list[APFilesystemRow], config: APFilesystemAuditConfig) -> list[APFilesystemRow]
def sort_rows(rows: list[APFilesystemRow], config: APFilesystemAuditConfig) -> list[APFilesystemRow]
```

Use `fnmatchcase` for include/exclude. Exact `ap_names` and `ap_hosts` should apply before wildcard include/exclude.

- [ ] **Step 6: Run parser and scoring tests**

Run:

```bash
pytest tests/test_ap_filesystem_parser.py tests/test_ap_filesystem_scoring.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add ap_filesystem_audit/__init__.py ap_filesystem_audit/models.py ap_filesystem_audit/parser.py ap_filesystem_audit/scoring.py tests/test_ap_filesystem_parser.py tests/test_ap_filesystem_scoring.py
git commit -m "Add AP filesystem parser and scoring"
```

---

### Task 2: Discovery, Config, And AP Collection

**Files:**
- Create: `ap_filesystem_audit/discovery.py`
- Create: `ap_filesystem_audit/config.py`
- Create: `ap_filesystem_audit/app.py`
- Test: `tests/test_ap_filesystem_discovery.py`
- Test: `tests/test_ap_filesystem_config.py`
- Test: `tests/test_ap_filesystem_app.py`

- [ ] **Step 1: Write discovery/config/app tests**

Create `tests/test_ap_filesystem_discovery.py`:

```python
from ap_filesystem_audit.discovery import discover_aps_from_wlc, parse_show_ap_summary
from ap_radio_monitor.models import WLCConfig
from wifiops.wlc_targets import WlcTarget


def test_parse_show_ap_summary_extracts_names_and_ips():
    output = """
AP Name                           Slots AP Model              Ethernet MAC     Radio MAC        Location        Country IP Address
-----------------------------------------------------------------------------------------------------
MBY-AP-1                          2     C9120AXI-B            aaaa.bbbb.cccc   dddd.eeee.ffff   default         US      10.1.2.3
MBY-AP-2                          2     C9120AXI-B            aaaa.bbbb.cccd   dddd.eeee.fff0   default         US      10.1.2.4
"""

    aps = parse_show_ap_summary(output, WlcTarget("wlc-1", WLCConfig(host="192.0.2.10", username="u", password="p")))

    assert [(ap.name, ap.host, ap.wlc_name) for ap in aps] == [
        ("MBY-AP-1", "10.1.2.3", "wlc-1"),
        ("MBY-AP-2", "10.1.2.4", "wlc-1"),
    ]


def test_discover_aps_from_wlc_runs_show_ap_summary(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.commands = []

        def check_enable_mode(self):
            return True

        def send_command(self, command, **kwargs):
            self.commands.append((command, kwargs))
            if command == "terminal length 0":
                return ""
            return "MBY-AP-1 2 model mac radio loc US 10.1.2.3"

        def disconnect(self):
            pass

    fake = FakeConnection()
    monkeypatch.setattr("ap_filesystem_audit.discovery.ConnectHandler", lambda **_kwargs: fake)

    aps = discover_aps_from_wlc(WlcTarget("wlc-1", WLCConfig(host="192.0.2.10", username="u", password="p")))

    assert aps[0].name == "MBY-AP-1"
    assert fake.commands[0][0] == "terminal length 0"
    assert fake.commands[1][0] == "show ap summary"
```

Create `tests/test_ap_filesystem_config.py`:

```python
from ap_filesystem_audit.config import load_config


def test_load_config_reads_wlcs_ap_credentials_and_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wifiops:
  wlc_concurrency: 4
wlcs:
  - name: wlc-1
    host: 192.0.2.10
    username: wlc-user
    password: wlc-pass
ap:
  username: ap-user
  password: ap-pass
  enable: ap-enable
ap_filesystems:
  include: ["MBY-*"]
  exclude: ["*TEST*"]
  min_used_percent: 90
  show_all: true
  ap_concurrency: 7
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.wlc_targets[0].name == "wlc-1"
    assert config.ap_credentials.username == "ap-user"
    assert config.ap_credentials.password == "ap-pass"
    assert config.ap_credentials.enable == "ap-enable"
    assert config.audit.include == ("MBY-*",)
    assert config.audit.exclude == ("*TEST*",)
    assert config.audit.min_used_percent == 90
    assert config.audit.show_all is True
    assert config.audit.ap_concurrency == 7
    assert config.wlc_concurrency == 4
```

Create `tests/test_ap_filesystem_app.py`:

```python
from rich.console import Console

from ap_filesystem_audit.app import collect_ap_filesystems, run_audit
from ap_filesystem_audit.models import APFilesystemAuditConfig, APCredentials, APTarget
from ap_radio_monitor.models import WLCConfig
from wifiops.wlc_targets import WlcTarget


FILESYSTEM_OUTPUT = """
Filesystem Size Used Available Use% Mounted on
none 95.4M 95.0M 376.0K 100% /tmp
"""


def test_collect_ap_filesystems_runs_sh_filesystems(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.commands = []

        def check_enable_mode(self):
            return True

        def send_command(self, command, **kwargs):
            self.commands.append((command, kwargs))
            if command == "terminal length 0":
                return ""
            return FILESYSTEM_OUTPUT

        def disconnect(self):
            pass

    fake = FakeConnection()
    monkeypatch.setattr("ap_filesystem_audit.app.ConnectHandler", lambda **_kwargs: fake)
    target = APTarget("wlc-1", "192.0.2.10", "AP-1", "10.1.2.3")

    snapshot = collect_ap_filesystems(target, APCredentials("u", "p"), APFilesystemAuditConfig())

    assert snapshot.rows[0].ap_name == "AP-1"
    assert snapshot.rows[0].mount == "/tmp"
    assert fake.commands[-1][0] == "sh filesystems"


def test_run_audit_renders_failures_and_returns_nonzero(monkeypatch):
    def fake_discover(_target):
        return [APTarget("wlc-1", "192.0.2.10", "AP-1", "10.1.2.3")]

    def fake_collect(_ap, _creds, _config):
        raise RuntimeError("ssh failed")

    monkeypatch.setattr("ap_filesystem_audit.app.discover_aps_from_wlc", fake_discover)
    monkeypatch.setattr("ap_filesystem_audit.app.collect_ap_filesystems", fake_collect)
    console = Console(record=True, width=160)

    exit_code = run_audit(
        [WlcTarget("wlc-1", WLCConfig(host="192.0.2.10", username="u", password="p"))],
        APCredentials("ap-u", "ap-p"),
        APFilesystemAuditConfig(),
        wlc_concurrency=1,
        console=console,
    )

    rendered = console.export_text()
    assert exit_code == 1
    assert "AP-1" in rendered
    assert "ssh failed" in rendered
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_ap_filesystem_discovery.py tests/test_ap_filesystem_config.py tests/test_ap_filesystem_app.py -q
```

Expected: FAIL because discovery/config/app modules do not exist.

- [ ] **Step 3: Implement discovery/config/app**

Implement:

- `parse_show_ap_summary(output, target) -> list[APTarget]`
- `discover_aps_from_wlc(target) -> list[APTarget]`
- `load_config(path) -> APFilesystemConfig`
- `collect_ap_filesystems(target, creds, config) -> APFilesystemSnapshot`
- `run_audit(wlc_targets, ap_credentials, audit_config, wlc_concurrency, console) -> int`

Use `ConnectHandler(... device_type="cisco_ios" ...)`, prompt regex `r"[>#]"`, and command `sh filesystems` for APs.

`run_audit` should:

- run WLC discovery through `run_bounded`
- deduplicate APs by `(name, host)`
- filter APs through `filter_ap_targets`
- run AP collection through `run_bounded`
- render with `build_filesystem_table`
- return `1` if any WLC/AP failure exists, else `0`

- [ ] **Step 4: Run discovery/config/app tests**

Run:

```bash
pytest tests/test_ap_filesystem_discovery.py tests/test_ap_filesystem_config.py tests/test_ap_filesystem_app.py -q
```

Expected: PASS after Task 3 display stubs exist. If needed, create a minimal `build_filesystem_table` stub in Task 3 before full display implementation.

- [ ] **Step 5: Commit**

```bash
git add ap_filesystem_audit/discovery.py ap_filesystem_audit/config.py ap_filesystem_audit/app.py tests/test_ap_filesystem_discovery.py tests/test_ap_filesystem_config.py tests/test_ap_filesystem_app.py
git commit -m "Add AP filesystem discovery and collection"
```

---

### Task 3: Display And CSV Export

**Files:**
- Create: `ap_filesystem_audit/display.py`
- Create: `ap_filesystem_audit/export.py`
- Test: `tests/test_ap_filesystem_display.py`
- Test: `tests/test_ap_filesystem_export.py`

- [ ] **Step 1: Write display and export tests**

Create `tests/test_ap_filesystem_display.py`:

```python
from rich.console import Console

from ap_filesystem_audit.display import build_filesystem_table
from ap_filesystem_audit.models import APFilesystemAuditConfig, APFilesystemFailure, APFilesystemRow, APFilesystemSnapshot


def row(ap_name="AP-1", used_percent=100):
    return APFilesystemRow(
        wlc_name="wlc-1",
        wlc_host="192.0.2.10",
        ap_name=ap_name,
        ap_host="10.1.2.3",
        filesystem="none",
        mount="/tmp",
        size="95.4M",
        used="95.0M",
        available="376.0K",
        used_percent=used_percent,
    )


def test_build_filesystem_table_renders_problem_rows():
    console = Console(record=True, width=180)

    console.print(build_filesystem_table(APFilesystemSnapshot(rows=[row()]), APFilesystemAuditConfig()))

    rendered = console.export_text()
    assert "AP-1" in rendered
    assert "/tmp" in rendered
    assert "FULL" in rendered


def test_build_filesystem_table_renders_no_issue_panel():
    console = Console(record=True, width=140)

    console.print(build_filesystem_table(APFilesystemSnapshot(rows=[row(used_percent=10)]), APFilesystemAuditConfig()))

    assert "No AP filesystem issues found" in console.export_text()


def test_build_filesystem_table_renders_failures():
    console = Console(record=True, width=180)
    snapshot = APFilesystemSnapshot(
        failures=[APFilesystemFailure(wlc_name="wlc-1", wlc_host="192.0.2.10", ap_name="AP-1", ap_host="10.1.2.3", message="ssh failed")]
    )

    console.print(build_filesystem_table(snapshot, APFilesystemAuditConfig()))

    rendered = console.export_text()
    assert "AP-1" in rendered
    assert "ssh failed" in rendered
```

Create `tests/test_ap_filesystem_export.py`:

```python
import csv

from ap_filesystem_audit.export import write_csv
from ap_filesystem_audit.models import APFilesystemAuditConfig, APFilesystemFailure, APFilesystemRow, APFilesystemSnapshot


def row(ap_name="AP-1", used_percent=100):
    return APFilesystemRow(
        wlc_name="wlc-1",
        wlc_host="192.0.2.10",
        ap_name=ap_name,
        ap_host="10.1.2.3",
        filesystem="none",
        mount="/tmp",
        size="95.4M",
        used="95.0M",
        available="376.0K",
        used_percent=used_percent,
    )


def test_write_csv_exports_visible_problem_rows_and_failures(tmp_path):
    path = tmp_path / "out" / "filesystems.csv"
    snapshot = APFilesystemSnapshot(
        rows=[row("OK", 10), row("FULL", 100)],
        failures=[APFilesystemFailure(wlc_name="wlc-1", ap_name="AP-FAIL", ap_host="10.1.2.4", message="ssh failed")],
    )

    write_csv(path, snapshot, APFilesystemAuditConfig())

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [item["record_type"] for item in rows] == ["filesystem", "failure"]
    assert rows[0]["ap_name"] == "FULL"
    assert rows[1]["error"] == "ssh failed"


def test_write_csv_all_includes_ok_rows(tmp_path):
    path = tmp_path / "filesystems.csv"

    write_csv(path, APFilesystemSnapshot(rows=[row("OK", 10)]), APFilesystemAuditConfig(show_all=True))

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["ap_name"] == "OK"
    assert rows[0]["status"] == "OK"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_ap_filesystem_display.py tests/test_ap_filesystem_export.py -q
```

Expected: FAIL because display/export modules are incomplete or absent.

- [ ] **Step 3: Implement display and export**

Implement `build_filesystem_table(snapshot, config)` with the columns from the spec.

Implement `write_csv(path, snapshot, config)` with fields:

```python
CSV_FIELDS = [
    "record_type", "wlc_name", "wlc_host", "ap_name", "ap_host",
    "filesystem", "mount", "size", "used", "available",
    "used_percent", "status", "notes", "error",
]
```

CSV output should use `visible_rows(snapshot.rows, config)` and always include failures.

- [ ] **Step 4: Run display/export tests**

Run:

```bash
pytest tests/test_ap_filesystem_display.py tests/test_ap_filesystem_export.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ap_filesystem_audit/display.py ap_filesystem_audit/export.py tests/test_ap_filesystem_display.py tests/test_ap_filesystem_export.py
git commit -m "Add AP filesystem display and CSV export"
```

---

### Task 4: CLI And WifiOps Wiring

**Files:**
- Create: `ap_filesystem_audit/cli.py`
- Modify: `wifiops/cli.py`
- Modify: `pyproject.toml`
- Modify: `config.example.yaml`
- Test: `tests/test_ap_filesystem_cli.py`
- Modify: `tests/test_wifiops_cli.py`

- [ ] **Step 1: Write CLI and delegation tests**

Create `tests/test_ap_filesystem_cli.py`:

```python
from unittest.mock import Mock, patch

from ap_filesystem_audit.cli import main, parse_args
from ap_filesystem_audit.models import APFilesystemAuditConfig, APFilesystemConfig, APCredentials


def test_parse_args_supports_filesystem_options():
    args = parse_args([
        "--config", "config.yaml",
        "--wlc", "wlc-1",
        "--include", "MBY-*",
        "--exclude", "*TEST*",
        "--ap-name", "AP-1",
        "--ap-host", "10.1.2.3",
        "--min-used-percent", "90",
        "--all",
        "--wlc-concurrency", "4",
        "--ap-concurrency", "10",
        "--output", "out.csv",
    ])

    assert args.wlc == ["wlc-1"]
    assert args.include == ["MBY-*"]
    assert args.exclude == ["*TEST*"]
    assert args.ap_name == ["AP-1"]
    assert args.ap_host == ["10.1.2.3"]
    assert args.min_used_percent == 90
    assert args.all is True
    assert args.wlc_concurrency == 4
    assert args.ap_concurrency == 10
    assert args.output == "out.csv"


def test_main_loads_config_applies_overrides_and_runs_audit():
    loaded = Mock()
    loaded.wlc_targets = [Mock(name="wlc-1")]
    loaded.ap_credentials = APCredentials("u", "p")
    loaded.audit = APFilesystemAuditConfig()
    loaded.wlc_concurrency = 3
    run_audit = Mock(return_value=0)

    with (
        patch("ap_filesystem_audit.cli.load_config", return_value=loaded),
        patch("ap_filesystem_audit.cli.run_audit", run_audit),
    ):
        assert main(["--config", "config.yaml", "--include", "MBY-*", "--output", "out.csv"]) == 0

    passed_config = run_audit.call_args.args[2]
    assert passed_config.include == ("MBY-*",)
    assert passed_config.output == "out.csv"
```

Append to `tests/test_wifiops_cli.py`:

```python
def test_ap_filesystems_delegates_to_ap_filesystem_audit():
    fs_main = Mock(return_value=0)

    with patch("ap_filesystem_audit.cli.main", fs_main):
        exit_code = main(["ap", "filesystems", "--config", "config.yaml", "--include", "MBY-*"])

    assert exit_code == 0
    fs_main.assert_called_once_with(["--config", "config.yaml", "--include", "MBY-*"])
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
pytest tests/test_ap_filesystem_cli.py tests/test_wifiops_cli.py::test_ap_filesystems_delegates_to_ap_filesystem_audit -q
```

Expected: FAIL because CLI wiring is not present.

- [ ] **Step 3: Implement CLI and wifiops delegation**

Create `ap_filesystem_audit/cli.py` with `parse_args(argv=None)` and `main(argv=None)`.

`main` should:

- load config
- select WLCs using `select_wlc_targets`
- apply CLI overrides using `dataclasses.replace`
- call `run_audit(selected_targets, config.ap_credentials, audit_config, wlc_concurrency, console)`

In `wifiops/cli.py`, add:

```python
ap = subcommands.add_parser("ap", help="Access point tools")
ap_subcommands = ap.add_subparsers(dest="ap_command", required=True)
filesystems = ap_subcommands.add_parser("filesystems", help="Audit AP filesystem usage")
```

Add all filesystem CLI options and delegate:

```python
if args.command == "ap" and args.ap_command == "filesystems":
    from ap_filesystem_audit.cli import main as filesystems_main
    return _exit_code(filesystems_main(_delegated_args(argv, "filesystems")))
```

Update `pyproject.toml` package include to add `ap_filesystem_audit*`.

Update `config.example.yaml` with:

```yaml
ap_filesystems:
  include: []
  exclude: []
  min_used_percent: 95
  show_all: false
  ap_concurrency: 20
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
pytest tests/test_ap_filesystem_cli.py tests/test_wifiops_cli.py::test_ap_filesystems_delegates_to_ap_filesystem_audit -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ap_filesystem_audit/cli.py wifiops/cli.py pyproject.toml config.example.yaml tests/test_ap_filesystem_cli.py tests/test_wifiops_cli.py
git commit -m "Wire AP filesystem audit CLI"
```

---

### Task 5: Documentation And Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README usage**

Add a concise section for:

```bash
wifiops ap filesystems --config config.yaml
wifiops ap filesystems --include "MBY-*"
wifiops ap filesystems --ap-name MBY-CON-SCC1_BAYSIDE_D-7
wifiops ap filesystems --min-used-percent 95
wifiops ap filesystems --output ap-filesystems.csv
wifiops ap filesystems --all --output ap-filesystems-all.csv
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
pytest tests/test_ap_filesystem_*.py tests/test_wifiops_cli.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full suite**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 4: Commit docs and final fixes**

```bash
git add README.md
git commit -m "Document AP filesystem audit command"
```

If verification required small code fixes, include those files in this commit and mention them in the commit body.

---

## Self-Review

- Spec coverage: The plan covers WLC discovery, AP SSH collection, parser patterns, filters, concurrency, display, CSV export, exit codes, and `wifiops ap filesystems` delegation.
- Scope control: The plan excludes remediation, direct AP-only mode, JSON export, scheduling, and rollout integration.
- Type consistency: `APFilesystemAuditConfig`, `APCredentials`, `APTarget`, `APFilesystemRow`, `APFilesystemFailure`, and `APFilesystemSnapshot` are introduced before later tasks use them.
- Test coverage: The plan includes parser, scoring, discovery, config, app orchestration, display, export, CLI, and delegation tests.
