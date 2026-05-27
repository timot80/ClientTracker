# AP Ethernet Port Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `wifiops c9800 ap-ports` to audit Catalyst 9800 AP Ethernet port speed and duplex from `show ap ethernet statistics`.

**Architecture:** Build a focused `ap_port_audit` package that mirrors the import-safe shape of `ap_radio_monitor`: models, parser, scoring/filtering, display, config, WLC session, app runner, and CLI. Wire `wifiops c9800 ap-ports` as a delegated command, reusing the existing WLC credential resolver and Rich terminal rendering.

**Tech Stack:** Python 3.10+, argparse, dataclasses, fnmatch, Netmiko, PyYAML, Rich, pytest.

---

## Fit Review

The feature fits best as a new `ap_port_audit` package instead of extending `ap_radio_monitor`. Radio balance is a live per-slot client/utilization monitor; AP port audit is a one-shot wired uplink health check. Keeping them separate avoids mixing display, scoring, and polling semantics while still sharing the same WLC config model and `wifiops` entrypoint.

The command belongs under `wifiops c9800` because it talks to a Catalyst 9800 WLC and should use the same config/keyring login flow as `wifiops c9800 radio` and `wifiops c9800 client`.

## File Structure

- Create `ap_port_audit/__init__.py`: package version marker.
- Create `ap_port_audit/models.py`: `APPortAuditConfig`, `APPortConfig`, `APPortRow`, and `APPortSnapshot`.
- Create `ap_port_audit/parser.py`: parser for `show ap ethernet statistics`.
- Create `ap_port_audit/scoring.py`: include/exclude filtering, issue detection, and row sorting.
- Create `ap_port_audit/display.py`: Rich table/panel rendering.
- Create `ap_port_audit/config.py`: YAML config loader using `wifiops.credentials.resolve_credentials`.
- Create `ap_port_audit/wlc.py`: Netmiko wrapper that runs `show ap ethernet statistics`.
- Create `ap_port_audit/app.py`: one-shot orchestration and error handling.
- Create `ap_port_audit/cli.py`: command parser and CLI runner.
- Modify `wifiops/cli.py`: add `wifiops c9800 ap-ports` and delegate args.
- Modify `pyproject.toml`: include `ap_port_audit*` in package discovery.
- Modify `config.example.yaml`: document optional `ap_ports` settings.
- Add tests under `tests/test_ap_port_*.py` and extend `tests/test_wifiops_cli.py`.

---

### Task 1: Models And Parser

**Files:**
- Create: `ap_port_audit/__init__.py`
- Create: `ap_port_audit/models.py`
- Create: `ap_port_audit/parser.py`
- Test: `tests/test_ap_port_parser.py`

- [ ] **Step 1: Write parser/model tests**

Create `tests/test_ap_port_parser.py`:

```python
from ap_port_audit.parser import parse_ethernet_statistics


SAMPLE_OUTPUT = """
AP Name : MBY-CON-SCC1_BAYSIDE_B-51

Interface Name      Status  Speed       Duplex  Rx Packets    Tx Packets    Discarded Packets
------------------------------------------------------------------------------------------------
GigabitEthernet0    UP       5000 Mbps   Full    160345        47098         0

AP Name : MBY-CON-SCC1_BAYSIDE_B-57

Interface Name      Status  Speed       Duplex  Rx Packets    Tx Packets    Discarded Packets
------------------------------------------------------------------------------------------------
GigabitEthernet0    UP       2500 Mbps   Full    6840          1455          0
"""


def test_parse_ethernet_statistics_reads_ap_sections_and_ports():
    snapshot = parse_ethernet_statistics(SAMPLE_OUTPUT)

    assert snapshot.raw_command == "show ap ethernet statistics"
    assert len(snapshot.rows) == 2
    assert snapshot.rows[0].ap_name == "MBY-CON-SCC1_BAYSIDE_B-51"
    assert snapshot.rows[0].interface == "GigabitEthernet0"
    assert snapshot.rows[0].link_status == "UP"
    assert snapshot.rows[0].speed_mbps == 5000
    assert snapshot.rows[0].speed_text == "5000 Mbps"
    assert snapshot.rows[0].duplex == "Full"
    assert snapshot.rows[0].rx_packets == 160345
    assert snapshot.rows[0].tx_packets == 47098
    assert snapshot.rows[0].discarded_packets == 0
    assert snapshot.parser_warnings == []


def test_parse_ethernet_statistics_keeps_unknown_speed_and_duplex():
    output = """
AP Name : TEST-AP

Interface Name      Status  Speed       Duplex  Rx Packets    Tx Packets    Discarded Packets
------------------------------------------------------------------------------------------------
GigabitEthernet0    UP       Unknown     Auto    1             2             3
"""

    snapshot = parse_ethernet_statistics(output)

    assert len(snapshot.rows) == 1
    assert snapshot.rows[0].speed_mbps is None
    assert snapshot.rows[0].speed_text == "Unknown"
    assert snapshot.rows[0].duplex == "Auto"


def test_parse_ethernet_statistics_records_malformed_rows():
    output = """
AP Name : TEST-AP
Interface Name      Status  Speed       Duplex  Rx Packets    Tx Packets    Discarded Packets
------------------------------------------------------------------------------------------------
this is not a valid interface row
"""

    snapshot = parse_ethernet_statistics(output)

    assert snapshot.rows == []
    assert snapshot.parser_warnings
    assert "TEST-AP" in snapshot.parser_warnings[0]
```

- [ ] **Step 2: Run parser tests to verify they fail**

Run: `pytest tests/test_ap_port_parser.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'ap_port_audit'`.

- [ ] **Step 3: Create models**

Create `ap_port_audit/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `ap_port_audit/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ap_radio_monitor.models import WLCConfig


@dataclass(frozen=True)
class APPortAuditConfig:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    show_all: bool = False
    speed_threshold: int = 1000


@dataclass(frozen=True)
class APPortConfig:
    wlc: WLCConfig
    ap_ports: APPortAuditConfig = field(default_factory=APPortAuditConfig)


@dataclass(frozen=True)
class APPortRow:
    ap_name: str
    interface: str
    link_status: str
    speed_text: str
    speed_mbps: int | None
    duplex: str
    rx_packets: int | None = None
    tx_packets: int | None = None
    discarded_packets: int | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class APPortSnapshot:
    rows: list[APPortRow] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    parser_warnings: list[str] = field(default_factory=list)
    poll_error: str = ""
    error_excerpt: str = ""
    raw_command: str = "show ap ethernet statistics"
```

- [ ] **Step 4: Implement parser**

Create `ap_port_audit/parser.py`:

```python
from __future__ import annotations

import re

from ap_port_audit.models import APPortRow, APPortSnapshot


AP_NAME_RE = re.compile(r"^AP Name\s*:\s*(?P<name>.+?)\s*$")
SPEED_RE = re.compile(r"^(?P<speed>\d+)\s+Mbps$", re.IGNORECASE)


def parse_ethernet_statistics(output: str) -> APPortSnapshot:
    rows: list[APPortRow] = []
    warnings: list[str] = []
    current_ap = ""
    in_table = False

    for line_number, line in enumerate(output.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        ap_match = AP_NAME_RE.match(stripped)
        if ap_match:
            current_ap = ap_match.group("name")
            in_table = False
            continue
        if stripped.startswith("Interface Name"):
            in_table = True
            continue
        if set(stripped) == {"-"}:
            continue
        if not in_table:
            continue
        parts = stripped.split()
        if len(parts) < 7 or not current_ap:
            warnings.append(f"line {line_number}: skipped malformed row for {current_ap or 'unknown AP'}: {stripped}")
            continue
        interface = parts[0]
        link_status = parts[1]
        speed_text = " ".join(parts[2:-4])
        duplex = parts[-4]
        speed_mbps = _parse_speed_mbps(speed_text)
        rows.append(
            APPortRow(
                ap_name=current_ap,
                interface=interface,
                link_status=link_status,
                speed_text=speed_text,
                speed_mbps=speed_mbps,
                duplex=duplex,
                rx_packets=_parse_int(parts[-3]),
                tx_packets=_parse_int(parts[-2]),
                discarded_packets=_parse_int(parts[-1]),
            )
        )

    return APPortSnapshot(rows=rows, parser_warnings=warnings)


def _parse_speed_mbps(value: str) -> int | None:
    match = SPEED_RE.match(value.strip())
    if not match:
        return None
    return int(match.group("speed"))


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None
```

- [ ] **Step 5: Run parser tests**

Run: `pytest tests/test_ap_port_parser.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ap_port_audit/__init__.py ap_port_audit/models.py ap_port_audit/parser.py tests/test_ap_port_parser.py
git commit -m "Add AP port audit parser"
```

---

### Task 2: Scoring And Display

**Files:**
- Create: `ap_port_audit/scoring.py`
- Create: `ap_port_audit/display.py`
- Test: `tests/test_ap_port_scoring.py`
- Test: `tests/test_ap_port_display.py`

- [ ] **Step 1: Write scoring tests**

Create `tests/test_ap_port_scoring.py`:

```python
from ap_port_audit.models import APPortAuditConfig, APPortRow
from ap_port_audit.scoring import filter_rows, row_statuses, sort_rows, visible_rows


def row(ap_name, speed_mbps=1000, duplex="Full", interface="GigabitEthernet0"):
    return APPortRow(
        ap_name=ap_name,
        interface=interface,
        link_status="UP",
        speed_text="Unknown" if speed_mbps is None else f"{speed_mbps} Mbps",
        speed_mbps=speed_mbps,
        duplex=duplex,
    )


def test_row_statuses_flags_low_speed_and_half_duplex():
    statuses = row_statuses(row("AP-1", speed_mbps=100, duplex="Half"), APPortAuditConfig())

    assert statuses == ("LOW-SPEED", "HALF-DUPLEX")


def test_row_statuses_flags_unknown_values():
    assert row_statuses(row("AP-1", speed_mbps=None, duplex="Auto"), APPortAuditConfig()) == ("UNKNOWN",)


def test_row_statuses_ok_at_or_above_threshold_with_full_duplex():
    assert row_statuses(row("AP-1", speed_mbps=2500), APPortAuditConfig()) == ("OK",)


def test_filter_rows_applies_include_then_exclude():
    rows = [row("MATCH-1"), row("MATCH-TEST"), row("OTHER-1")]

    filtered = filter_rows(rows, APPortAuditConfig(include=("MATCH-*",), exclude=("*TEST",)))

    assert [item.ap_name for item in filtered] == ["MATCH-1"]


def test_visible_rows_default_shows_only_problem_rows():
    rows = [row("OK-AP", speed_mbps=5000), row("BAD-AP", speed_mbps=100)]

    visible = visible_rows(rows, APPortAuditConfig())

    assert [item.ap_name for item in visible] == ["BAD-AP"]


def test_visible_rows_show_all_includes_healthy_rows():
    rows = [row("OK-AP", speed_mbps=5000), row("BAD-AP", speed_mbps=100)]

    visible = visible_rows(rows, APPortAuditConfig(show_all=True))

    assert [item.ap_name for item in visible] == ["OK-AP", "BAD-AP"]


def test_sort_rows_puts_problems_before_ok_rows():
    rows = [row("OK-AP", speed_mbps=5000), row("BAD-AP", speed_mbps=100)]

    sorted_items = sort_rows(rows, APPortAuditConfig(show_all=True))

    assert [item.ap_name for item in sorted_items] == ["BAD-AP", "OK-AP"]
```

- [ ] **Step 2: Write display tests**

Create `tests/test_ap_port_display.py`:

```python
from rich.console import Console

from ap_port_audit.display import build_port_table
from ap_port_audit.models import APPortAuditConfig, APPortRow, APPortSnapshot


def row(ap_name, speed_mbps=100, duplex="Full"):
    return APPortRow(
        ap_name=ap_name,
        interface="GigabitEthernet0",
        link_status="UP",
        speed_text=f"{speed_mbps} Mbps",
        speed_mbps=speed_mbps,
        duplex=duplex,
    )


def test_build_port_table_renders_problem_rows():
    console = Console(record=True, width=140)

    console.print(build_port_table(APPortSnapshot(rows=[row("BAD-AP")]), APPortAuditConfig()))
    rendered = console.export_text()

    assert "BAD-AP" in rendered
    assert "LOW-SPEED" in rendered
    assert "GigabitEthernet0" in rendered


def test_build_port_table_renders_no_issues_panel_for_problem_only_empty_result():
    console = Console(record=True, width=120)

    console.print(build_port_table(APPortSnapshot(rows=[row("OK-AP", speed_mbps=5000)]), APPortAuditConfig()))
    rendered = console.export_text()

    assert "No AP Ethernet port issues found" in rendered


def test_build_port_table_includes_parser_warnings():
    console = Console(record=True, width=140)

    console.print(
        build_port_table(
            APPortSnapshot(rows=[row("BAD-AP")], parser_warnings=["line 3: skipped malformed row"]),
            APPortAuditConfig(),
        )
    )
    rendered = console.export_text()

    assert "line 3: skipped malformed row" in rendered
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_ap_port_scoring.py tests/test_ap_port_display.py -q`

Expected: FAIL because `ap_port_audit.scoring` and `ap_port_audit.display` do not exist.

- [ ] **Step 4: Implement scoring**

Create `ap_port_audit/scoring.py`:

```python
from __future__ import annotations

from fnmatch import fnmatchcase

from ap_port_audit.models import APPortAuditConfig, APPortRow


def row_statuses(row: APPortRow, config: APPortAuditConfig) -> tuple[str, ...]:
    statuses: list[str] = []
    if row.speed_mbps is None or not row.duplex:
        statuses.append("UNKNOWN")
    elif row.speed_mbps < config.speed_threshold:
        statuses.append("LOW-SPEED")
    if row.duplex.lower() == "half":
        statuses.append("HALF-DUPLEX")
    elif row.duplex.lower() not in {"full", "half"} and "UNKNOWN" not in statuses:
        statuses.append("UNKNOWN")
    return tuple(statuses or ["OK"])


def filter_rows(rows: list[APPortRow], config: APPortAuditConfig) -> list[APPortRow]:
    filtered = list(rows)
    if config.include:
        filtered = [row for row in filtered if any(fnmatchcase(row.ap_name, pattern) for pattern in config.include)]
    if config.exclude:
        filtered = [row for row in filtered if not any(fnmatchcase(row.ap_name, pattern) for pattern in config.exclude)]
    return filtered


def visible_rows(rows: list[APPortRow], config: APPortAuditConfig) -> list[APPortRow]:
    filtered = filter_rows(rows, config)
    if config.show_all:
        return filtered
    return [row for row in filtered if row_statuses(row, config) != ("OK",)]


def sort_rows(rows: list[APPortRow], config: APPortAuditConfig) -> list[APPortRow]:
    return sorted(rows, key=lambda row: (_problem_rank(row, config), row.ap_name, row.interface))


def _problem_rank(row: APPortRow, config: APPortAuditConfig) -> int:
    return 1 if row_statuses(row, config) == ("OK",) else 0
```

- [ ] **Step 5: Implement display**

Create `ap_port_audit/display.py`:

```python
from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ap_port_audit.models import APPortAuditConfig, APPortSnapshot
from ap_port_audit.scoring import row_statuses, sort_rows, visible_rows


STATUS_STYLES = {
    "LOW-SPEED": "red",
    "HALF-DUPLEX": "red",
    "UNKNOWN": "yellow",
    "OK": "green",
}


def build_port_table(snapshot: APPortSnapshot, config: APPortAuditConfig) -> Panel:
    rows = sort_rows(visible_rows(snapshot.rows, config), config)
    if not rows and not config.show_all and not snapshot.poll_error:
        return Panel("No AP Ethernet port issues found", title="AP Ethernet Port Audit", border_style="green")

    table = Table(expand=False)
    table.add_column("AP", no_wrap=True)
    table.add_column("Interface", no_wrap=True)
    table.add_column("Link Status", no_wrap=True)
    table.add_column("Speed", justify="right", no_wrap=True)
    table.add_column("Duplex", no_wrap=True)
    table.add_column("Port Status", no_wrap=True)
    table.add_column("Notes")

    for row in rows:
        statuses = row_statuses(row, config)
        style = _status_style(statuses)
        table.add_row(
            row.ap_name,
            row.interface,
            row.link_status,
            row.speed_text,
            row.duplex,
            ", ".join(statuses),
            ", ".join(row.notes),
            style=style,
        )

    if snapshot.poll_error or snapshot.parser_warnings:
        table.add_section()
    if snapshot.poll_error:
        table.add_row("Poll Error", "", "", "", "", "", snapshot.poll_error, style="red")
    for warning in snapshot.parser_warnings[:5]:
        table.add_row("Warning", "", "", "", "", "", warning, style="yellow")
    if len(snapshot.parser_warnings) > 5:
        table.add_row(
            "Warning",
            "",
            "",
            "",
            "",
            "",
            f"{len(snapshot.parser_warnings) - 5} additional parser warnings hidden",
            style="yellow",
        )

    title = f"{len(rows)} shown / {len(snapshot.rows)} ports | AP Ethernet Port Audit"
    return Panel(table, title=title, border_style="cyan", expand=False)


def _status_style(statuses: tuple[str, ...]) -> str:
    for status in statuses:
        if status in {"LOW-SPEED", "HALF-DUPLEX"}:
            return "red"
    if "UNKNOWN" in statuses:
        return "yellow"
    return "green"
```

- [ ] **Step 6: Run scoring and display tests**

Run: `pytest tests/test_ap_port_scoring.py tests/test_ap_port_display.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add ap_port_audit/scoring.py ap_port_audit/display.py tests/test_ap_port_scoring.py tests/test_ap_port_display.py
git commit -m "Add AP port audit scoring and display"
```

---

### Task 3: Config, WLC Session, And App Runner

**Files:**
- Create: `ap_port_audit/config.py`
- Create: `ap_port_audit/wlc.py`
- Create: `ap_port_audit/app.py`
- Test: `tests/test_ap_port_config.py`
- Test: `tests/test_ap_port_wlc.py`
- Test: `tests/test_ap_port_app.py`

- [ ] **Step 1: Write config, WLC, and app tests**

Create `tests/test_ap_port_config.py`:

```python
from ap_port_audit.config import load_config


def test_load_config_reads_wlc_and_ap_ports(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wlc:
  host: "192.0.2.10"
  username: "admin"
  password: "secret"
  read_timeout: 120
ap_ports:
  include: ["MBY-*"]
  exclude: ["*-TEST"]
  show_all: true
  speed_threshold: 2500
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.wlc.host == "192.0.2.10"
    assert config.wlc.username == "admin"
    assert config.wlc.password == "secret"
    assert config.wlc.read_timeout == 120
    assert config.ap_ports.include == ("MBY-*",)
    assert config.ap_ports.exclude == ("*-TEST",)
    assert config.ap_ports.show_all is True
    assert config.ap_ports.speed_threshold == 2500
```

Create `tests/test_ap_port_wlc.py`:

```python
from ap_radio_monitor.models import WLCConfig
from ap_port_audit.wlc import APPortAuditSession


def test_get_ethernet_statistics_runs_expected_command(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.commands = []

        def check_enable_mode(self):
            return True

        def send_command(self, command, **kwargs):
            self.commands.append((command, kwargs))
            return "output"

        def disconnect(self):
            pass

    fake = FakeConnection()
    monkeypatch.setattr("ap_port_audit.wlc.ConnectHandler", lambda **_kwargs: fake)
    session = APPortAuditSession(WLCConfig(host="192.0.2.10", username="u", password="p", read_timeout=120))

    session.connect()
    output = session.get_ethernet_statistics()

    assert output == "output"
    assert fake.commands == [
        ("terminal length 0", {"expect_string": r"#", "read_timeout": 30}),
        ("show ap ethernet statistics", {"expect_string": r"#", "read_timeout": 120}),
    ]
```

Create `tests/test_ap_port_app.py`:

```python
from rich.console import Console

from ap_port_audit.app import collect_once, run_once
from ap_port_audit.models import APPortAuditConfig
from ap_radio_monitor.models import WLCConfig


SAMPLE_OUTPUT = """
AP Name : BAD-AP
Interface Name      Status  Speed       Duplex  Rx Packets    Tx Packets    Discarded Packets
------------------------------------------------------------------------------------------------
GigabitEthernet0    UP       100 Mbps    Half    1             2             0
"""


class FakeSession:
    def __init__(self, _config=None):
        self.connected = False

    def connect(self):
        self.connected = True

    def get_ethernet_statistics(self):
        return SAMPLE_OUTPUT

    def disconnect(self):
        self.connected = False


def test_collect_once_parses_session_output():
    snapshot = collect_once(FakeSession(), APPortAuditConfig())

    assert snapshot.rows[0].ap_name == "BAD-AP"
    assert snapshot.rows[0].speed_mbps == 100


def test_run_once_renders_audit_table(monkeypatch):
    console = Console(record=True, width=140)
    monkeypatch.setattr("ap_port_audit.app.APPortAuditSession", FakeSession)

    run_once(WLCConfig(host="192.0.2.10", username="u", password="p"), APPortAuditConfig(), console)

    rendered = console.export_text()
    assert "BAD-AP" in rendered
    assert "LOW-SPEED" in rendered
    assert "HALF-DUPLEX" in rendered
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ap_port_config.py tests/test_ap_port_wlc.py tests/test_ap_port_app.py -q`

Expected: FAIL because modules do not exist.

- [ ] **Step 3: Implement config loader**

Create `ap_port_audit/config.py`:

```python
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from ap_port_audit.models import APPortAuditConfig, APPortConfig
from ap_radio_monitor.models import WLCConfig
from wifiops.credentials import CredentialConfigError, resolve_credentials


WLC_CREDENTIAL_ENV = {
    "username": "CLIENT_TRACKER_WLC_USERNAME",
    "password": "CLIENT_TRACKER_WLC_PASSWORD",
    "enable": "CLIENT_TRACKER_WLC_ENABLE",
}


def load_config(path: str | Path) -> APPortConfig:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise ValueError(f"Config file not found: {cfg_path}")
    with cfg_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("Config file must contain a YAML mapping")

    wlc_raw = _mapping(raw.get("wlc") or {}, "wlc")
    try:
        credentials = resolve_credentials(raw, "wlc", os.environ, WLC_CREDENTIAL_ENV)
    except CredentialConfigError as exc:
        raise ValueError(str(exc)) from exc

    host = os.environ.get("CLIENT_TRACKER_WLC_HOST", str(wlc_raw.get("host", "")))
    if not host.strip():
        raise ValueError("Missing required config value: wlc.host")
    if not credentials.username.strip():
        raise ValueError("Missing required config value: wlc.username")
    if not credentials.password.strip():
        raise ValueError("Missing required config value: wlc.password")

    ap_raw = _mapping(raw.get("ap_ports") or {}, "ap_ports")
    return APPortConfig(
        wlc=WLCConfig(
            host=host,
            username=credentials.username,
            password=credentials.password,
            enable=credentials.enable,
            read_timeout=int(wlc_raw.get("read_timeout", 90)),
        ),
        ap_ports=APPortAuditConfig(
            include=_str_tuple(ap_raw.get("include", ())),
            exclude=_str_tuple(ap_raw.get("exclude", ())),
            show_all=bool(ap_raw.get("show_all", False)),
            speed_threshold=int(ap_raw.get("speed_threshold", 1000)),
        ),
    )


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def _str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)
```

- [ ] **Step 4: Implement WLC session**

Create `ap_port_audit/wlc.py`:

```python
from __future__ import annotations

import threading
from typing import Optional

from netmiko import ConnectHandler

from ap_radio_monitor.models import WLCConfig


class APPortAuditSession:
    def __init__(self, config: WLCConfig):
        self.config = config
        self.connection: Optional[ConnectHandler] = None
        self._lock = threading.Lock()

    def connect(self) -> None:
        self.connection = ConnectHandler(
            device_type="cisco_ios",
            host=self.config.host,
            username=self.config.username,
            password=self.config.password,
            secret=self.config.enable,
        )
        if self.config.enable and not self.connection.check_enable_mode():
            self.connection.enable()
        self.connection.send_command("terminal length 0", expect_string=r"#", read_timeout=30)

    def get_ethernet_statistics(self) -> str:
        with self._lock:
            if self.connection is None:
                raise RuntimeError("WLC session not connected")
            return self.connection.send_command(
                "show ap ethernet statistics",
                expect_string=r"#",
                read_timeout=self.config.read_timeout,
            )

    def disconnect(self) -> None:
        with self._lock:
            if self.connection is not None:
                try:
                    self.connection.disconnect()
                finally:
                    self.connection = None
```

- [ ] **Step 5: Implement app runner**

Create `ap_port_audit/app.py`:

```python
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from ap_port_audit.display import build_port_table
from ap_port_audit.models import APPortAuditConfig, APPortSnapshot
from ap_port_audit.parser import parse_ethernet_statistics
from ap_port_audit.wlc import APPortAuditSession
from ap_radio_monitor.models import WLCConfig


def collect_once(session, config: APPortAuditConfig) -> APPortSnapshot:
    del config
    output = session.get_ethernet_statistics()
    snapshot = parse_ethernet_statistics(output)
    if not snapshot.rows:
        return APPortSnapshot(
            parser_warnings=snapshot.parser_warnings,
            poll_error="no AP Ethernet port rows parsed",
            error_excerpt=_output_excerpt(output),
        )
    return snapshot


def run_once(wlc_config: WLCConfig, audit_config: APPortAuditConfig, console: Console) -> None:
    session = APPortAuditSession(wlc_config)
    try:
        console.print(f"[cyan]Connecting to WLC {wlc_config.host}[/cyan]")
        session.connect()
        console.print("[cyan]Collecting AP Ethernet statistics[/cyan]")
        snapshot = _collect_with_error_handling(session, audit_config)
        console.print("[cyan]Rendering AP Ethernet audit[/cyan]")
        if snapshot.poll_error and not snapshot.rows:
            console.print(_error_panel(snapshot))
        else:
            console.print(build_port_table(snapshot, audit_config))
    finally:
        session.disconnect()


def _collect_with_error_handling(
    session,
    config: APPortAuditConfig,
    previous: APPortSnapshot | None = None,
) -> APPortSnapshot:
    try:
        return collect_once(session, config)
    except Exception as exc:
        return APPortSnapshot(
            rows=previous.rows if previous else [],
            parser_warnings=previous.parser_warnings if previous else [],
            poll_error=f"poll failed: {exc}",
        )


def _error_panel(snapshot: APPortSnapshot) -> Panel:
    message = snapshot.poll_error
    if snapshot.error_excerpt:
        message = f"{message}\n{snapshot.error_excerpt}"
    return Panel(message, title="AP Ethernet Port Audit", border_style="red")


def _output_excerpt(output: str, limit: int = 160) -> str:
    collapsed = " ".join(output.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit] + "..."
```

- [ ] **Step 6: Run config, WLC, and app tests**

Run: `pytest tests/test_ap_port_config.py tests/test_ap_port_wlc.py tests/test_ap_port_app.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add ap_port_audit/config.py ap_port_audit/wlc.py ap_port_audit/app.py tests/test_ap_port_config.py tests/test_ap_port_wlc.py tests/test_ap_port_app.py
git commit -m "Add AP port audit config and WLC runner"
```

---

### Task 4: CLI And WifiOps Wiring

**Files:**
- Create: `ap_port_audit/cli.py`
- Modify: `wifiops/cli.py`
- Modify: `pyproject.toml`
- Modify: `config.example.yaml`
- Test: `tests/test_ap_port_cli.py`
- Modify: `tests/test_wifiops_cli.py`

- [ ] **Step 1: Write CLI and delegation tests**

Create `tests/test_ap_port_cli.py`:

```python
from unittest.mock import Mock, patch

from ap_port_audit.cli import main, parse_args


def test_parse_args_supports_audit_options():
    args = parse_args(
        [
            "--config",
            "lab.yaml",
            "--include",
            "MBY-*",
            "--exclude",
            "*TEST*",
            "--all",
            "--speed-threshold",
            "2500",
        ]
    )

    assert args.config == "lab.yaml"
    assert args.include == ["MBY-*"]
    assert args.exclude == ["*TEST*"]
    assert args.all is True
    assert args.speed_threshold == 2500


def test_main_loads_config_applies_overrides_and_runs_once():
    loaded = Mock()
    loaded.wlc = Mock()
    loaded.ap_ports = Mock(include=(), exclude=(), show_all=False, speed_threshold=1000)
    run_once = Mock()

    with (
        patch("ap_port_audit.cli.load_config", return_value=loaded),
        patch("ap_port_audit.cli.run_once", run_once),
    ):
        exit_code = main(["--config", "config.yaml", "--include", "MBY-*", "--all", "--speed-threshold", "2500"])

    assert exit_code == 0
    passed_config = run_once.call_args.args[1]
    assert passed_config.include == ("MBY-*",)
    assert passed_config.show_all is True
    assert passed_config.speed_threshold == 2500
```

Add to `tests/test_wifiops_cli.py`:

```python
def test_c9800_ap_ports_delegates_to_ap_port_audit():
    port_main = Mock(return_value=0)

    with patch("ap_port_audit.cli.main", port_main):
        exit_code = main(["c9800", "ap-ports", "--config", "config.yaml", "--include", "MBY-*"])

    assert exit_code == 0
    port_main.assert_called_once_with(["--config", "config.yaml", "--include", "MBY-*"])
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run: `pytest tests/test_ap_port_cli.py tests/test_wifiops_cli.py::test_c9800_ap_ports_delegates_to_ap_port_audit -q`

Expected: FAIL because `ap_port_audit.cli` and the `wifiops` route are missing.

- [ ] **Step 3: Implement `ap_port_audit.cli`**

Create `ap_port_audit/cli.py`:

```python
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from rich.console import Console

from ap_port_audit.app import run_once
from ap_port_audit.config import load_config


DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Catalyst 9800 AP Ethernet port speed and duplex."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")
    parser.add_argument("--include", action="append", default=[], help="AP name wildcard to include")
    parser.add_argument("--exclude", action="append", default=[], help="AP name wildcard to exclude")
    parser.add_argument("--all", action="store_true", help="Show all AP ports, including healthy rows")
    parser.add_argument(
        "--speed-threshold",
        type=int,
        help="Minimum expected negotiated speed in Mbps. Defaults to config or 1000.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    console = Console()
    try:
        config = load_config(args.config)
        audit_config = config.ap_ports
        if args.include:
            audit_config = replace(audit_config, include=tuple(args.include))
        if args.exclude:
            audit_config = replace(audit_config, exclude=tuple(args.exclude))
        if args.all:
            audit_config = replace(audit_config, show_all=True)
        if args.speed_threshold is not None:
            audit_config = replace(audit_config, speed_threshold=args.speed_threshold)
        run_once(config.wlc, audit_config, console)
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Wire `wifiops c9800 ap-ports`**

In `wifiops/cli.py`, add the parser below the existing `radio` parser:

```python
    ap_ports = c9800_subcommands.add_parser(
        "ap-ports",
        help="Audit AP Ethernet port speed and duplex",
        description="Audit AP Ethernet port speed and duplex from a Catalyst 9800 WLC.",
    )
    ap_ports.add_argument("--config", help="Path to config.yaml")
    ap_ports.add_argument("--include", action="append", default=[], help="AP name wildcard to include")
    ap_ports.add_argument("--exclude", action="append", default=[], help="AP name wildcard to exclude")
    ap_ports.add_argument("--all", action="store_true", help="Show all AP ports, including healthy rows")
    ap_ports.add_argument("--speed-threshold", type=int, help="Minimum expected negotiated speed in Mbps")
```

In `wifiops/cli.py`, add the route after the radio route:

```python
    if args.command == "c9800" and args.c9800_command == "ap-ports":
        from ap_port_audit.cli import main as ap_ports_main

        return _exit_code(ap_ports_main(_delegated_args(argv, "ap-ports")))
```

- [ ] **Step 5: Update packaging and example config**

In `pyproject.toml`, make sure package discovery includes:

```toml
include = ["ap_radio_monitor*", "ap_port_audit*", "client_tracker*", "wifiops*"]
```

In `config.example.yaml`, add:

```yaml
ap_ports:
  include: []
  exclude: []
  show_all: false
  speed_threshold: 1000
```

- [ ] **Step 6: Run CLI tests**

Run: `pytest tests/test_ap_port_cli.py tests/test_wifiops_cli.py::test_c9800_ap_ports_delegates_to_ap_port_audit -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add ap_port_audit/cli.py wifiops/cli.py pyproject.toml config.example.yaml tests/test_ap_port_cli.py tests/test_wifiops_cli.py
git commit -m "Wire AP port audit CLI"
```

---

### Task 5: Full Verification And Documentation

**Files:**
- Modify: `README.md`
- Existing tests: all AP port tests and full suite.

- [ ] **Step 1: Add README usage**

Add a short section to `README.md` near the existing `wifiops c9800` usage:

```markdown
### AP Ethernet Port Audit

Audit AP uplink speed and duplex from a Catalyst 9800 WLC:

```bash
wifiops c9800 ap-ports --config config.yaml
wifiops c9800 ap-ports --include "MBY-*"
wifiops c9800 ap-ports --all
wifiops c9800 ap-ports --speed-threshold 2500
```

The command runs `show ap ethernet statistics`. By default it shows only AP ports with a low negotiated speed, half duplex, or unknown speed/duplex. The default low-speed threshold is below `1000 Mbps`.
```

- [ ] **Step 2: Run focused AP port tests**

Run:

```bash
pytest tests/test_ap_port_parser.py tests/test_ap_port_scoring.py tests/test_ap_port_display.py tests/test_ap_port_config.py tests/test_ap_port_wlc.py tests/test_ap_port_app.py tests/test_ap_port_cli.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full suite**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 4: Commit docs and final adjustments**

```bash
git add README.md
git commit -m "Document AP port audit command"
```

If Step 2 or Step 3 required code fixes, include those fixed files in this commit and mention them in the commit body.

---

## Self-Review

- Spec coverage: The plan implements `wifiops c9800 ap-ports`, `show ap ethernet statistics`, default problem-only output, `--all`, include/exclude filters, configurable speed threshold, low speed/half duplex/unknown statuses, Rich rendering, config loading, WLC command dispatch, and tests.
- Placeholder scan: No task contains placeholder instructions. Every code-producing step names exact files and expected behavior.
- Type consistency: `APPortAuditConfig`, `APPortConfig`, `APPortRow`, and `APPortSnapshot` are defined in Task 1 and used consistently by later tasks.
