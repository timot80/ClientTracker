# Unified Client Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge local Wi-Fi client telemetry into ClientTracker with infra, local, and combined modes, a unified Rich UI, event timeline, CSV logging, safer config handling, and parser tests.

**Architecture:** Refactor the current single-file script into a small `client_tracker` package while keeping `client_tracker.py` as the executable shim. Keep hardware-dependent Netmiko and OS command execution behind poller/session classes, and make parsers, event generation, config loading, and CSV formatting independently testable.

**Tech Stack:** Python 3.10+, Netmiko, PyYAML, Rich, Colorama, pytest, stdlib `csv`, `dataclasses`, `argparse`, `subprocess`, and `threading`.

---

## File Structure

- Create `client_tracker/__init__.py`: package marker and version.
- Create `client_tracker/models.py`: shared dataclasses and mode/event constants.
- Create `client_tracker/infra.py`: WLC session, AP session pool, MAC helpers, infra parsers.
- Create `client_tracker/local.py`: macOS/Windows local telemetry commands, parsers, state-change detection, sound alert.
- Create `client_tracker/events.py`: event timeline and CSV logger.
- Create `client_tracker/config.py`: config loading, env overrides, mode-aware validation.
- Create `client_tracker/display.py`: Rich panels for WLC, AP, local stats, and events.
- Create `client_tracker/app.py`: orchestration loop for infra/local/combined.
- Create `client_tracker/cli.py`: argument parsing, `--mode`, `--log`, `--check`.
- Modify `client_tracker.py`: executable shim to call `client_tracker.cli.main`.
- Create `config.example.yaml`: tracked example config.
- Create `.gitignore`: ignore `config.yaml`, Python caches, pytest caches, and generated logs.
- Modify `requirements.txt`: add `colorama` and `pytest`.
- Modify `README.md`: document modes, config, logging, and checks.
- Create tests under `tests/`: parser, config, event, CSV, and CLI validation coverage.

---

## Task 1: Package Skeleton and MAC Helpers

**Files:**
- Create: `client_tracker/__init__.py`
- Create: `client_tracker/models.py`
- Create: `client_tracker/infra.py`
- Modify: `client_tracker.py`
- Create: `tests/test_infra_helpers.py`

- [ ] **Step 1: Write failing tests for MAC helpers**

Create `tests/test_infra_helpers.py`:

```python
from client_tracker.infra import is_valid_mac, mac_to_cisco, normalize_mac


def test_normalize_mac_strips_common_delimiters():
    assert normalize_mac("AA:BB-CC.DD:EE-FF") == "aabbccddeeff"


def test_mac_to_cisco_formats_normalized_mac():
    assert mac_to_cisco("aa:bb:cc:dd:ee:ff") == "aabb.ccdd.eeff"


def test_is_valid_mac_accepts_common_formats():
    assert is_valid_mac("aa:bb:cc:dd:ee:ff")
    assert is_valid_mac("aabb.ccdd.eeff")
    assert is_valid_mac("aabbccddeeff")


def test_is_valid_mac_rejects_bad_values():
    assert not is_valid_mac("not-a-mac")
    assert not is_valid_mac("aa:bb:cc:dd:ee")
    assert not is_valid_mac("gg:bb:cc:dd:ee:ff")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_infra_helpers.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'client_tracker'`.

- [ ] **Step 3: Implement package skeleton and MAC helpers**

Create `client_tracker/__init__.py`:

```python
"""Unified Cisco wireless client tracker."""

__version__ = "0.1.0"
```

Create `client_tracker/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


Mode = Literal["infra", "local", "combined"]
EventSource = Literal["infra", "ap", "local", "system"]
EventType = Literal[
    "roam",
    "bssid-change",
    "disassociated",
    "associated",
    "poll-error",
    "poll-recovered",
    "startup",
    "shutdown",
]


@dataclass
class WLCClientState:
    mac: str = ""
    ap_name: str = ""
    ap_ip: str = ""
    ssid: str = ""
    protocol: str = ""
    state: str = ""
    rssi: str = ""
    snr: str = ""
    timestamp: datetime | None = None


@dataclass
class APClientState:
    mac: str = ""
    ap_name: str = ""
    rssi: str = ""
    channel: str = ""
    ssid: str = ""
    mcs_rate: str = ""
    timestamp: datetime | None = None


@dataclass
class LocalClientState:
    ssid: str = ""
    bssid: str = ""
    channel: str = ""
    tx_rate: str = ""
    rx_rate: str = ""
    signal: str = ""
    noise: str = ""
    ping_status: str = ""
    platform: str = ""
    timestamp: datetime | None = None


@dataclass
class TrackerEvent:
    timestamp: datetime
    source: EventSource
    type: EventType
    message: str
    previous_ap: str = ""
    current_ap: str = ""
    previous_bssid: str = ""
    current_bssid: str = ""
    rssi: str = ""
    channel: str = ""
    error: str = ""
```

Create the helper section in `client_tracker/infra.py`:

```python
from __future__ import annotations

import re

_VALID_MAC_RE = re.compile(r"^[0-9a-f]{12}$")


def normalize_mac(mac: str) -> str:
    """Strip common MAC delimiters and return lowercase hex."""
    return re.sub(r"[:\\-.]", "", mac).lower()


def mac_to_cisco(mac: str) -> str:
    """Convert any supported MAC format to Cisco dot notation."""
    raw = normalize_mac(mac)
    return f"{raw[0:4]}.{raw[4:8]}.{raw[8:12]}"


def mac_to_colon(mac: str) -> str:
    """Convert any supported MAC format to colon notation."""
    raw = normalize_mac(mac)
    return ":".join(raw[i:i + 2] for i in range(0, 12, 2))


def is_valid_mac(mac: str) -> bool:
    """Return True when the input is exactly 12 hex digits after normalization."""
    return bool(_VALID_MAC_RE.match(normalize_mac(mac)))
```

Replace `client_tracker.py` with:

```python
#!/usr/bin/env python3
"""Executable shim for the unified client tracker."""

from client_tracker.cli import main


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_infra_helpers.py -v`

Expected: 4 passed.

- [ ] **Step 5: Commit**

Run:

```bash
git add client_tracker.py client_tracker tests/test_infra_helpers.py
git commit -m "refactor: add client tracker package skeleton"
```

---

## Task 2: Infrastructure Parsers and Sessions

**Files:**
- Modify: `client_tracker/infra.py`
- Test: `tests/test_infra_parsers.py`

- [ ] **Step 1: Write failing parser tests**

Create `tests/test_infra_parsers.py`:

```python
from client_tracker.infra import WLCSession, APSessionPool


def test_parse_client_detail_preserves_multi_word_ssid():
    output = """
Client MAC Address : aabb.ccdd.eeff
AP Name : AP-9166-1
Wireless LAN Network Name (SSID) : Corp Guest WiFi
Protocol : 802.11ax - 5 GHz
Policy Manager State : Run
Radio Signal Strength Indicator : -42 dBm
Signal to Noise Ratio : 38 dB
"""
    state = WLCSession.parse_client_detail(output, "aa:bb:cc:dd:ee:ff")

    assert state.ap_name == "AP-9166-1"
    assert state.ssid == "Corp Guest WiFi"
    assert state.protocol == "802.11ax - 5 GHz"
    assert state.state == "Run"
    assert state.rssi == "-42"
    assert state.snr == "38"


def test_parse_dot11_clients_preserves_multi_word_ssid():
    output = """
MAC Address     SlotID WLANID AID  WLAN Name       RSSI  Maxrate is_wgb_wired is_mld_sta
aabb.ccdd.eeff  1      17     36   Corp Guest WiFi -51   MCS92SS false        false
"""
    state = APSessionPool.parse_dot11_clients(
        output, "aa:bb:cc:dd:ee:ff", "AP-9166-1"
    )

    assert state.ap_name == "AP-9166-1"
    assert state.channel == "36"
    assert state.ssid == "Corp Guest WiFi"
    assert state.rssi == "-51"
    assert state.mcs_rate == "MCS92SS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_infra_parsers.py -v`

Expected: FAIL because `WLCSession` and `APSessionPool` are not implemented.

- [ ] **Step 3: Move infrastructure code into `client_tracker/infra.py`**

Add imports, session classes, and parser methods from existing `client_tracker.py`, using the shared dataclasses from `models.py`. Expose static parser names `parse_client_detail` and `parse_dot11_clients` so tests can call them directly. Keep Netmiko imports in this module.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_infra_helpers.py tests/test_infra_parsers.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add client_tracker/infra.py tests/test_infra_parsers.py
git commit -m "refactor: extract infrastructure tracking logic"
```

---

## Task 3: Local Telemetry Parsers

**Files:**
- Create: `client_tracker/local.py`
- Test: `tests/test_local_parsers.py`

- [ ] **Step 1: Write failing local parser tests**

Create `tests/test_local_parsers.py`:

```python
from client_tracker.local import parse_airport_output, parse_netsh_output


def test_parse_airport_output_preserves_multi_word_ssid():
    output = """
     agrCtlRSSI: -55
     agrCtlNoise: -92
           state: running
         lastTxRate: 286
             SSID: Corp Guest WiFi
            BSSID: aa:bb:cc:dd:ee:ff
          channel: 36,80
"""
    state = parse_airport_output(output)

    assert state.ssid == "Corp Guest WiFi"
    assert state.bssid == "aa:bb:cc:dd:ee:ff"
    assert state.channel == "36,80"
    assert state.tx_rate == "286"
    assert state.signal == "-55"
    assert state.noise == "-92"
    assert state.platform == "darwin"


def test_parse_netsh_output_preserves_multi_word_ssid_and_signal():
    output = """
    SSID                   : Corp Guest WiFi
    BSSID                  : aa:bb:cc:dd:ee:ff
    Signal                 : 82%
    Channel                : 36
    Receive rate (Mbps)    : 1201
    Transmit rate (Mbps)   : 960
"""
    state = parse_netsh_output(output)

    assert state.ssid == "Corp Guest WiFi"
    assert state.bssid == "aa:bb:cc:dd:ee:ff"
    assert state.channel == "36"
    assert state.rx_rate == "1201"
    assert state.tx_rate == "960"
    assert state.signal == "-59.0 approx dBm"
    assert state.platform == "win32"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_local_parsers.py -v`

Expected: FAIL because `client_tracker.local` does not exist.

- [ ] **Step 3: Implement local parsers and command poller shell**

Create `client_tracker/local.py` with parser functions, `LocalTelemetryPoller`, non-shell subprocess calls, optional ping host support, and sound alert helper. Use colon-based parsing, not `.split()[-1]`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_local_parsers.py -v`

Expected: 2 passed.

- [ ] **Step 5: Commit**

Run:

```bash
git add client_tracker/local.py tests/test_local_parsers.py
git commit -m "feat: add local wireless telemetry parsers"
```

---

## Task 4: Event Timeline and CSV Logger

**Files:**
- Create: `client_tracker/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: Write failing event and CSV tests**

Create `tests/test_events.py`:

```python
import csv
from datetime import datetime

from client_tracker.events import CSVLogger, EventTimeline
from client_tracker.models import TrackerEvent


def test_event_timeline_keeps_max_events():
    timeline = EventTimeline(max_events=2)
    timeline.append(TrackerEvent(datetime(2026, 5, 26, 1), "system", "startup", "one"))
    timeline.append(TrackerEvent(datetime(2026, 5, 26, 2), "local", "bssid-change", "two"))
    timeline.append(TrackerEvent(datetime(2026, 5, 26, 3), "infra", "roam", "three"))

    assert [event.message for event in timeline.items()] == ["two", "three"]


def test_csv_logger_writes_header_sample_and_event(tmp_path):
    path = tmp_path / "roam.csv"
    logger = CSVLogger(path)
    logger.write_sample(
        mode="combined",
        infra_ap_name="AP-1",
        local_bssid="aa:bb:cc:dd:ee:ff",
    )
    logger.write_event(
        mode="combined",
        event=TrackerEvent(
            datetime(2026, 5, 26, 12, 0, 0),
            "infra",
            "roam",
            "AP changed",
            previous_ap="AP-1",
            current_ap="AP-2",
        ),
    )

    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert rows[0]["row_type"] == "sample"
    assert rows[0]["mode"] == "combined"
    assert rows[0]["infra_ap_name"] == "AP-1"
    assert rows[0]["local_bssid"] == "aa:bb:cc:dd:ee:ff"
    assert rows[1]["row_type"] == "event"
    assert rows[1]["event_source"] == "infra"
    assert rows[1]["event_type"] == "roam"
    assert rows[1]["event_message"] == "AP changed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_events.py -v`

Expected: FAIL because `client_tracker.events` does not exist.

- [ ] **Step 3: Implement timeline and CSV logger**

Create `client_tracker/events.py` with `CSV_COLUMNS`, `EventTimeline`, and `CSVLogger`. The logger creates parent directories, writes a header for new files, appends rows, and flushes after each row.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_events.py -v`

Expected: 2 passed.

- [ ] **Step 5: Commit**

Run:

```bash
git add client_tracker/events.py tests/test_events.py
git commit -m "feat: add tracker event timeline and csv logging"
```

---

## Task 5: Config Loading and Secret Hygiene

**Files:**
- Create: `client_tracker/config.py`
- Create: `config.example.yaml`
- Create/Modify: `.gitignore`
- Modify: `requirements.txt`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/test_config.py`:

```python
from client_tracker.config import load_config


def test_load_config_uses_yaml_and_env_overrides(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
wlc:
  host: "192.0.2.10"
  username: "admin"
  password: "file-password"
  enable: "file-enable"
ap:
  username: "ap-admin"
  password: "ap-file-password"
  enable: "ap-file-enable"
local:
  ping_host: "1.1.1.1"
  sound_alerts: false
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLIENT_TRACKER_WLC_PASSWORD", "env-password")

    cfg = load_config(cfg_path, require_infra=True)

    assert cfg.wlc.host == "192.0.2.10"
    assert cfg.wlc.password == "env-password"
    assert cfg.ap.username == "ap-admin"
    assert cfg.local.ping_host == "1.1.1.1"
    assert cfg.local.sound_alerts is False


def test_load_config_does_not_require_file_for_local_mode(tmp_path):
    cfg = load_config(tmp_path / "missing.yaml", require_infra=False)

    assert cfg.wlc.host == ""
    assert cfg.local.sound_alerts is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`

Expected: FAIL because `client_tracker.config` does not exist.

- [ ] **Step 3: Implement config loader and hygiene files**

Create `client_tracker/config.py` with `WLCConfig`, `APConfig`, `LocalConfig`, `AppConfig`, and `load_config(path, require_infra)`. Add env var overrides listed in the spec.

Create `config.example.yaml` with placeholder values and local defaults. Create `.gitignore` with:

```gitignore
config.yaml
__pycache__/
.pytest_cache/
*.pyc
*.csv
*.log
```

Append to `requirements.txt` if missing:

```text
colorama>=0.4.6
pytest>=8.0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`

Expected: 2 passed.

- [ ] **Step 5: Commit**

Run:

```bash
git add client_tracker/config.py tests/test_config.py config.example.yaml .gitignore requirements.txt
git commit -m "feat: add mode-aware config loading"
```

---

## Task 6: Display and CLI

**Files:**
- Create: `client_tracker/display.py`
- Create: `client_tracker/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI validation tests**

Create `tests/test_cli.py`:

```python
import pytest

from client_tracker.cli import parse_args


def test_default_mode_is_infra_when_mac_supplied():
    args = parse_args(["aa:bb:cc:dd:ee:ff"])

    assert args.mode == "infra"
    assert args.mac == "aa:bb:cc:dd:ee:ff"


def test_local_mode_does_not_require_mac():
    args = parse_args(["--mode", "local"])

    assert args.mode == "local"
    assert args.mac is None


def test_combined_mode_requires_mac():
    with pytest.raises(SystemExit):
        parse_args(["--mode", "combined"])


def test_invalid_mac_exits():
    with pytest.raises(SystemExit):
        parse_args(["not-a-mac"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`

Expected: FAIL because `client_tracker.cli` does not exist.

- [ ] **Step 3: Implement display renderer and CLI parsing**

Create `display.py` by adapting the current `LiveDisplay`, adding Local Client Stats and Event Timeline panels. Create `cli.py` with `parse_args(argv=None)`, `main(argv=None)`, `--mode`, `--log`, and `--check`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`

Expected: 4 passed.

- [ ] **Step 5: Commit**

Run:

```bash
git add client_tracker/display.py client_tracker/cli.py tests/test_cli.py
git commit -m "feat: add unified cli and display shell"
```

---

## Task 7: Application Orchestration

**Files:**
- Create: `client_tracker/app.py`
- Modify: `client_tracker/cli.py`
- Modify: `client_tracker.py`
- Test: `tests/test_app_events.py`

- [ ] **Step 1: Write failing state-change tests**

Create `tests/test_app_events.py`:

```python
from datetime import datetime

from client_tracker.app import detect_infra_roam, detect_local_change
from client_tracker.models import APClientState, LocalClientState, WLCClientState


def test_detect_infra_roam_uses_last_ap_stats():
    event = detect_infra_roam(
        previous_ap="AP-1",
        current=WLCClientState(ap_name="AP-2"),
        last_ap_state=APClientState(rssi="-51", mcs_rate="MCS92SS", channel="36"),
        now=datetime(2026, 5, 26, 12, 0, 0),
    )

    assert event is not None
    assert event.type == "roam"
    assert event.previous_ap == "AP-1"
    assert event.current_ap == "AP-2"
    assert event.rssi == "-51"
    assert event.channel == "36"


def test_detect_local_change_reports_bssid_change():
    event = detect_local_change(
        previous=LocalClientState(bssid="aa:bb:cc:dd:ee:ff"),
        current=LocalClientState(bssid="11:22:33:44:55:66", signal="-60", channel="40"),
        now=datetime(2026, 5, 26, 12, 0, 0),
    )

    assert event is not None
    assert event.type == "bssid-change"
    assert event.previous_bssid == "aa:bb:cc:dd:ee:ff"
    assert event.current_bssid == "11:22:33:44:55:66"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_app_events.py -v`

Expected: FAIL because `client_tracker.app` does not exist.

- [ ] **Step 3: Implement app orchestration and event detection**

Create `ClientTrackerApp`, `detect_infra_roam`, and `detect_local_change`. The loop runs mode-specific pollers, updates display, writes CSV samples/events, and handles Ctrl+C cleanup. Update `cli.main` to load config, run `--check`, construct the app, and call `run()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_app_events.py -v`

Expected: 2 passed.

- [ ] **Step 5: Commit**

Run:

```bash
git add client_tracker/app.py client_tracker/cli.py client_tracker.py tests/test_app_events.py
git commit -m "feat: orchestrate infra local and combined tracking"
```

---

## Task 8: README and Full Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-05-26-unified-client-tracker-implementation.md` if checklist status is updated during execution.

- [ ] **Step 1: Update README**

Document:

- `--mode infra`, `--mode local`, `--mode combined`
- `--log roam-test.csv`
- `--check`
- config.example.yaml to config.yaml workflow
- env var secret overrides
- platform support
- examples for endpoint and infrastructure workflows

- [ ] **Step 2: Run full automated verification**

Run:

```bash
pytest -v
python -m py_compile client_tracker.py client_tracker/*.py
git diff --check
```

Expected: pytest passes, py_compile exits 0, diff check exits 0.

- [ ] **Step 3: Commit docs and any final fixes**

Run:

```bash
git add README.md docs/superpowers/plans/2026-05-26-unified-client-tracker-implementation.md
git commit -m "docs: document unified client tracker usage"
```

---

## Spec Coverage Self-Review

- Modes are covered by Tasks 6 and 7.
- Package/module split is covered by Tasks 1 through 7.
- Local telemetry parser behavior is covered by Task 3.
- Event timeline and CSV logging are covered by Task 4 and integrated in Task 7.
- Config hygiene and env var overrides are covered by Task 5.
- Rich UI panels are covered by Task 6.
- Error handling and cleanup are covered by Tasks 6 and 7.
- Tests and verification are covered by every task and Task 8.
