# Multi-WLC Command Aggregation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-controller execution for `wifiops c9800 ap-ports`, using `wlcs:` config entries by default and allowing `--wlc` selection.

**Architecture:** Add shared WLC target resolution under `wifiops` so single `wlc:` and multi `wlcs:` config produce a common named target list. Add a small bounded concurrency helper, then update `ap_port_audit` to run one snapshot per selected WLC, aggregate rows with source WLC metadata, render failures, and return non-zero on partial or total failure.

**Tech Stack:** Python 3.10+, dataclasses, PyYAML, keyring-backed credential resolver, `concurrent.futures`, Rich, argparse, pytest.

---

## Scope

Implement multi-WLC support for `wifiops c9800 ap-ports` only.

Do not change `wifiops c9800 radio` or `wifiops c9800 client` behavior in this implementation. The shared helper modules should be reusable later, but this task should not convert live radio or client tracking.

## File Structure

- Create `wifiops/wlc_targets.py`: parse `wlc:` and `wlcs:` into named targets with resolved `WLCConfig`.
- Create `wifiops/concurrency.py`: bounded worker-pool helper.
- Modify `ap_port_audit/models.py`: add source WLC fields and aggregate failure model.
- Modify `ap_port_audit/config.py`: return selected WLC targets, AP port config, and concurrency.
- Modify `ap_port_audit/app.py`: collect per WLC and aggregate.
- Modify `ap_port_audit/display.py`: add `WLC` column and failure footer.
- Modify `ap_port_audit/cli.py`: add `--wlc` and `--wlc-concurrency`.
- Modify `wifiops/cli.py`: preserve delegated args for new options.
- Modify `config.example.yaml`: add example `wlcs:` and `wifiops.wlc_concurrency`.
- Modify `README.md`: document multi-WLC `ap-ports`.
- Add tests for target resolution, concurrency, config/CLI overrides, app aggregation, display, and delegation.

---

### Task 1: Shared WLC Target Resolution

**Files:**
- Create: `wifiops/wlc_targets.py`
- Test: `tests/test_wlc_targets.py`

- [ ] **Step 1: Write failing target resolution tests**

Create `tests/test_wlc_targets.py`:

```python
import pytest

from wifiops.wlc_targets import WlcTargetConfigError, resolve_wlc_targets, select_wlc_targets


def test_single_wlc_resolves_to_default_target():
    raw = {
        "wlc": {
            "host": "192.0.2.10",
            "username": "admin",
            "password": "secret",
            "read_timeout": 120,
        }
    }

    targets = resolve_wlc_targets(raw, env={})

    assert len(targets) == 1
    assert targets[0].name == "default"
    assert targets[0].config.host == "192.0.2.10"
    assert targets[0].config.username == "admin"
    assert targets[0].config.password == "secret"
    assert targets[0].config.read_timeout == 120


def test_single_wlc_uses_explicit_name():
    raw = {"wlc": {"name": "mby-1", "host": "192.0.2.10", "username": "admin", "password": "secret"}}

    assert resolve_wlc_targets(raw, env={})[0].name == "mby-1"


def test_wlcs_resolves_all_targets_and_wins_over_wlc():
    raw = {
        "wlc": {"host": "192.0.2.99", "username": "old", "password": "old"},
        "wlcs": [
            {"name": "mby-1", "host": "192.0.2.10", "username": "admin", "password": "secret"},
            {"name": "mby-2", "host": "192.0.2.11", "username": "admin", "password": "secret"},
        ],
    }

    targets = resolve_wlc_targets(raw, env={})

    assert [target.name for target in targets] == ["mby-1", "mby-2"]
    assert [target.config.host for target in targets] == ["192.0.2.10", "192.0.2.11"]


def test_wlcs_rejects_missing_name_and_duplicate_name():
    with pytest.raises(WlcTargetConfigError, match="wlcs\\[0\\].name"):
        resolve_wlc_targets(
            {"wlcs": [{"host": "192.0.2.10", "username": "admin", "password": "secret"}]},
            env={},
        )

    with pytest.raises(WlcTargetConfigError, match="Duplicate WLC name"):
        resolve_wlc_targets(
            {
                "wlcs": [
                    {"name": "mby-1", "host": "192.0.2.10", "username": "admin", "password": "secret"},
                    {"name": "mby-1", "host": "192.0.2.11", "username": "admin", "password": "secret"},
                ]
            },
            env={},
        )


def test_select_wlc_targets_preserves_requested_order_and_rejects_unknown():
    targets = resolve_wlc_targets(
        {
            "wlcs": [
                {"name": "mby-1", "host": "192.0.2.10", "username": "admin", "password": "secret"},
                {"name": "mby-2", "host": "192.0.2.11", "username": "admin", "password": "secret"},
            ]
        },
        env={},
    )

    selected = select_wlc_targets(targets, ("mby-2", "mby-1"))

    assert [target.name for target in selected] == ["mby-2", "mby-1"]
    with pytest.raises(WlcTargetConfigError, match="Unknown WLC"):
        select_wlc_targets(targets, ("missing",))
```

- [ ] **Step 2: Run target tests to verify they fail**

Run:

```bash
pytest tests/test_wlc_targets.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `wifiops.wlc_targets`.

- [ ] **Step 3: Implement target resolver**

Create `wifiops/wlc_targets.py`:

```python
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ap_radio_monitor.models import WLCConfig
from wifiops.credentials import CredentialConfigError, resolve_credentials


WLC_CREDENTIAL_ENV = {
    "username": "CLIENT_TRACKER_WLC_USERNAME",
    "password": "CLIENT_TRACKER_WLC_PASSWORD",
    "enable": "CLIENT_TRACKER_WLC_ENABLE",
}


class WlcTargetConfigError(ValueError):
    pass


@dataclass(frozen=True)
class WlcTarget:
    name: str
    config: WLCConfig


def resolve_wlc_targets(
    raw: dict[str, Any],
    env: Mapping[str, str] | None = None,
) -> list[WlcTarget]:
    env = os.environ if env is None else env
    if "wlcs" in raw and raw.get("wlcs") is not None:
        wlcs = raw["wlcs"]
        if not isinstance(wlcs, list):
            raise WlcTargetConfigError("wlcs must be a list")
        targets = [_target_from_section(raw, f"wlcs[{index}]", item, env) for index, item in enumerate(wlcs)]
        _validate_unique_names(targets)
        return targets

    wlc = raw.get("wlc") or {}
    if not isinstance(wlc, dict):
        raise WlcTargetConfigError("wlc must be a mapping")
    return [_target_from_section(raw, "wlc", wlc, env, default_name="default")]


def select_wlc_targets(targets: list[WlcTarget], names: tuple[str, ...]) -> list[WlcTarget]:
    if not names:
        return targets
    by_name = {target.name: target for target in targets}
    selected = []
    for name in names:
        target = by_name.get(name)
        if target is None:
            available = ", ".join(sorted(by_name))
            raise WlcTargetConfigError(f"Unknown WLC '{name}'. Available WLCs: {available}")
        selected.append(target)
    return selected


def _target_from_section(
    raw: dict[str, Any],
    section: str,
    section_data: Any,
    env: Mapping[str, str],
    default_name: str | None = None,
) -> WlcTarget:
    if not isinstance(section_data, dict):
        raise WlcTargetConfigError(f"{section} must be a mapping")
    name = str(section_data.get("name") or default_name or "").strip()
    if not name:
        raise WlcTargetConfigError(f"Missing required config value: {section}.name")
    try:
        credentials = resolve_credentials({**raw, section: section_data}, section, env, WLC_CREDENTIAL_ENV)
    except CredentialConfigError as exc:
        raise WlcTargetConfigError(str(exc)) from exc
    host = env.get("CLIENT_TRACKER_WLC_HOST", str(section_data.get("host", ""))).strip()
    if not host:
        raise WlcTargetConfigError(f"Missing required config value: {section}.host")
    if not credentials.username.strip():
        raise WlcTargetConfigError(f"Missing required config value: {section}.username")
    if not credentials.password.strip():
        raise WlcTargetConfigError(f"Missing required config value: {section}.password")
    return WlcTarget(
        name=name,
        config=WLCConfig(
            host=host,
            username=credentials.username,
            password=credentials.password,
            enable=credentials.enable,
            read_timeout=int(section_data.get("read_timeout", 90)),
        ),
    )


def _validate_unique_names(targets: list[WlcTarget]) -> None:
    seen: set[str] = set()
    for target in targets:
        if target.name in seen:
            raise WlcTargetConfigError(f"Duplicate WLC name '{target.name}'")
        seen.add(target.name)
```

- [ ] **Step 4: Run target tests**

Run:

```bash
pytest tests/test_wlc_targets.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wifiops/wlc_targets.py tests/test_wlc_targets.py
git commit -m "Add WLC target resolver"
```

---

### Task 2: Bounded Concurrency Helper

**Files:**
- Create: `wifiops/concurrency.py`
- Test: `tests/test_concurrency.py`

- [ ] **Step 1: Write concurrency tests**

Create `tests/test_concurrency.py`:

```python
from wifiops.concurrency import run_bounded


def test_run_bounded_returns_results_in_input_order():
    results = run_bounded([3, 1, 2], lambda value: value * 10, concurrency=2)

    assert results == [30, 10, 20]


def test_run_bounded_captures_exceptions_in_input_order():
    def worker(value):
        if value == 2:
            raise RuntimeError("failed")
        return value

    results = run_bounded([1, 2, 3], worker, concurrency=2)

    assert results[0] == 1
    assert isinstance(results[1], RuntimeError)
    assert str(results[1]) == "failed"
    assert results[2] == 3


def test_run_bounded_uses_at_least_one_worker():
    assert run_bounded([1], lambda value: value, concurrency=0) == [1]
```

- [ ] **Step 2: Run concurrency tests to verify they fail**

Run:

```bash
pytest tests/test_concurrency.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `wifiops.concurrency`.

- [ ] **Step 3: Implement concurrency helper**

Create `wifiops/concurrency.py`:

```python
from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar


T = TypeVar("T")
R = TypeVar("R")


def run_bounded(
    items: Sequence[T],
    worker: Callable[[T], R],
    concurrency: int,
) -> list[R | Exception]:
    max_workers = max(1, min(max(1, concurrency), len(items) or 1))
    results: list[R | Exception | None] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker, item): index for index, item in enumerate(items)}
        for future in as_completed(futures):
            index = futures[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                results[index] = exc
    return [result for result in results if result is not None]
```

- [ ] **Step 4: Run concurrency tests**

Run:

```bash
pytest tests/test_concurrency.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wifiops/concurrency.py tests/test_concurrency.py
git commit -m "Add bounded concurrency helper"
```

---

### Task 3: Multi-WLC AP Port Config And CLI

**Files:**
- Modify: `ap_port_audit/models.py`
- Modify: `ap_port_audit/config.py`
- Modify: `ap_port_audit/cli.py`
- Modify: `wifiops/cli.py`
- Test: `tests/test_ap_port_config.py`
- Test: `tests/test_ap_port_cli.py`
- Test: `tests/test_wifiops_cli.py`

- [ ] **Step 1: Add config and CLI tests**

Append to `tests/test_ap_port_config.py`:

```python
def test_load_config_reads_multi_wlc_targets_and_concurrency(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wifiops:
  wlc_concurrency: 5
wlcs:
  - name: "mby-1"
    host: "192.0.2.10"
    username: "admin"
    password: "secret"
  - name: "mby-2"
    host: "192.0.2.11"
    username: "admin"
    password: "secret"
ap_ports:
  speed_threshold: 2500
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert [target.name for target in config.wlc_targets] == ["mby-1", "mby-2"]
    assert [target.config.host for target in config.wlc_targets] == ["192.0.2.10", "192.0.2.11"]
    assert config.wlc_concurrency == 5
    assert config.ap_ports.speed_threshold == 2500
```

Update existing single-WLC assertions in `tests/test_ap_port_config.py` to use `config.wlc_targets[0].config` while preserving `config.wlc` if the implementation keeps a compatibility property.

Append to `tests/test_ap_port_cli.py`:

```python
def test_parse_args_supports_wlc_selection_and_concurrency():
    args = parse_args(["--wlc", "mby-1", "--wlc", "mby-2", "--wlc-concurrency", "5"])

    assert args.wlc == ["mby-1", "mby-2"]
    assert args.wlc_concurrency == 5


def test_main_selects_wlcs_and_overrides_concurrency():
    loaded = Mock()
    loaded.wlc_targets = [
        Mock(name="mby-1", config=Mock()),
        Mock(name="mby-2", config=Mock()),
    ]
    loaded.ap_ports = APPortAuditConfig()
    loaded.wlc_concurrency = 3
    run_multi = Mock(return_value=0)

    with (
        patch("ap_port_audit.cli.load_config", return_value=loaded),
        patch("ap_port_audit.cli.run_multi", run_multi),
    ):
        exit_code = main(["--config", "config.yaml", "--wlc", "mby-2", "--wlc-concurrency", "5"])

    assert exit_code == 0
    assert [target.name for target in run_multi.call_args.args[0]] == ["mby-2"]
    assert run_multi.call_args.args[2] == 5
```

Append to `tests/test_wifiops_cli.py`:

```python
def test_c9800_ap_ports_preserves_multi_wlc_options():
    port_main = Mock(return_value=0)

    with patch("ap_port_audit.cli.main", port_main):
        exit_code = main(
            [
                "c9800",
                "ap-ports",
                "--wlc",
                "mby-1",
                "--wlc",
                "mby-2",
                "--wlc-concurrency",
                "5",
            ]
        )

    assert exit_code == 0
    port_main.assert_called_once_with(["--wlc", "mby-1", "--wlc", "mby-2", "--wlc-concurrency", "5"])
```

- [ ] **Step 2: Run config and CLI tests to verify they fail**

Run:

```bash
pytest tests/test_ap_port_config.py tests/test_ap_port_cli.py tests/test_wifiops_cli.py -q
```

Expected: FAIL because models/config/CLI do not expose multi-WLC fields yet.

- [ ] **Step 3: Update models**

Modify `ap_port_audit/models.py` so `APPortConfig` contains targets and concurrency:

```python
from wifiops.wlc_targets import WlcTarget


@dataclass(frozen=True)
class APPortConfig:
    wlc_targets: list[WlcTarget]
    ap_ports: APPortAuditConfig = field(default_factory=APPortAuditConfig)
    wlc_concurrency: int = 3

    @property
    def wlc(self) -> WLCConfig:
        return self.wlc_targets[0].config
```

Keep the `wlc` property for older tests and single-WLC callers.

- [ ] **Step 4: Update AP port config loader**

Modify `ap_port_audit/config.py` to:

```python
from wifiops.wlc_targets import WlcTargetConfigError, resolve_wlc_targets
```

Replace the direct single `wlc` credential resolution with:

```python
    try:
        wlc_targets = resolve_wlc_targets(raw, os.environ)
    except WlcTargetConfigError as exc:
        raise ValueError(str(exc)) from exc
```

Parse concurrency:

```python
    wifiops_raw = _mapping(raw.get("wifiops") or {}, "wifiops")
    wlc_concurrency = int(wifiops_raw.get("wlc_concurrency", 3))
```

Return:

```python
    return APPortConfig(
        wlc_targets=wlc_targets,
        ap_ports=APPortAuditConfig(...),
        wlc_concurrency=wlc_concurrency,
    )
```

- [ ] **Step 5: Update AP port CLI parser and main**

In `ap_port_audit/cli.py`, add parser flags:

```python
    parser.add_argument("--wlc", action="append", default=[], help="Named WLC to include; repeatable")
    parser.add_argument("--wlc-concurrency", type=int, help="Maximum WLCs to query concurrently")
```

Import:

```python
from wifiops.wlc_targets import select_wlc_targets
```

Update `main` so it selects targets and calls `run_multi`:

```python
        targets = select_wlc_targets(config.wlc_targets, tuple(args.wlc))
        concurrency = args.wlc_concurrency if args.wlc_concurrency is not None else config.wlc_concurrency
        return run_multi(targets, audit_config, concurrency, console)
```

Retain `run_once` only as a lower-level single target helper in `ap_port_audit.app`.

- [ ] **Step 6: Update wifiops parser**

In `wifiops/cli.py`, add to the `ap-ports` subparser:

```python
    ap_ports.add_argument("--wlc", action="append", default=[], help="Named WLC to include; repeatable")
    ap_ports.add_argument("--wlc-concurrency", type=int, help="Maximum WLCs to query concurrently")
```

The existing `_delegated_args(argv, "ap-ports")` should preserve these arguments.

- [ ] **Step 7: Run config and CLI tests**

Run:

```bash
pytest tests/test_ap_port_config.py tests/test_ap_port_cli.py tests/test_wifiops_cli.py -q
```

Expected: PASS after `run_multi` is introduced in Task 4. If this task fails only because `run_multi` does not exist, create a temporary importable stub in `ap_port_audit.app`:

```python
def run_multi(targets, audit_config, concurrency, console):
    return run_once(targets[0].config, audit_config, console)
```

- [ ] **Step 8: Commit**

```bash
git add ap_port_audit/models.py ap_port_audit/config.py ap_port_audit/cli.py wifiops/cli.py tests/test_ap_port_config.py tests/test_ap_port_cli.py tests/test_wifiops_cli.py
git commit -m "Wire AP port audit multi-WLC config and CLI"
```

---

### Task 4: AP Port Multi-WLC Aggregation

**Files:**
- Modify: `ap_port_audit/models.py`
- Modify: `ap_port_audit/app.py`
- Modify: `ap_port_audit/display.py`
- Test: `tests/test_ap_port_app.py`
- Test: `tests/test_ap_port_display.py`

- [ ] **Step 1: Add aggregation tests**

Append to `tests/test_ap_port_app.py`:

```python
from wifiops.wlc_targets import WlcTarget


def test_run_multi_aggregates_rows_and_returns_nonzero_for_partial_failure(monkeypatch):
    from ap_port_audit.app import run_multi

    class MultiSession:
        def __init__(self, config):
            self.config = config

        def connect(self):
            pass

        def get_ethernet_statistics(self):
            if self.config.host == "192.0.2.11":
                raise RuntimeError("connection lost")
            return SAMPLE_OUTPUT

        def disconnect(self):
            pass

    targets = [
        WlcTarget("mby-1", WLCConfig(host="192.0.2.10", username="u", password="p")),
        WlcTarget("mby-2", WLCConfig(host="192.0.2.11", username="u", password="p")),
    ]
    console = Console(record=True, width=160)
    monkeypatch.setattr("ap_port_audit.app.APPortAuditSession", MultiSession)

    exit_code = run_multi(targets, APPortAuditConfig(), 2, console)

    rendered = console.export_text()
    assert exit_code == 1
    assert "mby-1" in rendered
    assert "BAD-AP" in rendered
    assert "mby-2" in rendered
    assert "connection lost" in rendered
```

Append to `tests/test_ap_port_display.py`:

```python
from ap_port_audit.models import APPortFailure


def test_build_port_table_renders_wlc_column_and_failures():
    console = Console(record=True, width=180)
    snapshot = APPortSnapshot(
        rows=[row("BAD-AP")],
        failures=[APPortFailure(wlc_name="mby-2", message="poll failed: timeout")],
    )
    snapshot.rows[0].wlc_name = "mby-1"

    console.print(build_port_table(snapshot, APPortAuditConfig()))
    rendered = console.export_text()

    assert "WLC" in rendered
    assert "mby-1" in rendered
    assert "mby-2" in rendered
    assert "poll failed: timeout" in rendered
```

If the row dataclass is frozen, create the row with `wlc_name="mby-1"` instead of assigning after creation.

- [ ] **Step 2: Run aggregation tests to verify they fail**

Run:

```bash
pytest tests/test_ap_port_app.py tests/test_ap_port_display.py -q
```

Expected: FAIL because failure models, WLC rendering, and `run_multi` are incomplete.

- [ ] **Step 3: Update models for source WLC and failures**

Modify `ap_port_audit/models.py`:

```python
@dataclass(frozen=True)
class APPortFailure:
    wlc_name: str
    message: str


@dataclass(frozen=True)
class APPortRow:
    ...
    wlc_name: str = ""
```

Add to `APPortSnapshot`:

```python
    failures: list[APPortFailure] = field(default_factory=list)
```

- [ ] **Step 4: Implement aggregation in app**

Modify `ap_port_audit/app.py`:

```python
from dataclasses import replace

from ap_port_audit.models import APPortFailure
from wifiops.concurrency import run_bounded
from wifiops.wlc_targets import WlcTarget
```

Add:

```python
def run_multi(
    targets: list[WlcTarget],
    audit_config: APPortAuditConfig,
    concurrency: int,
    console: Console,
) -> int:
    console.print(f"[cyan]Collecting AP Ethernet statistics from {len(targets)} WLC(s)[/cyan]")
    results = run_bounded(targets, lambda target: _collect_target(target, audit_config), concurrency)
    rows = []
    warnings = []
    failures = []
    for result in results:
        if isinstance(result, APPortFailure):
            failures.append(result)
            continue
        if isinstance(result, Exception):
            failures.append(APPortFailure(wlc_name="unknown", message=f"poll failed: {result}"))
            continue
        rows.extend(result.rows)
        warnings.extend(result.parser_warnings)
        failures.extend(result.failures)
    snapshot = APPortSnapshot(rows=rows, parser_warnings=warnings, failures=failures)
    console.print("[cyan]Rendering AP Ethernet audit[/cyan]")
    console.print(build_port_table(snapshot, audit_config))
    return 1 if failures else 0


def _collect_target(target: WlcTarget, audit_config: APPortAuditConfig) -> APPortSnapshot | APPortFailure:
    session = APPortAuditSession(target.config)
    try:
        session.connect()
        snapshot = _collect_with_error_handling(session, audit_config)
        if snapshot.poll_error and not snapshot.rows:
            return APPortFailure(wlc_name=target.name, message=snapshot.poll_error)
        return APPortSnapshot(
            rows=[replace(row, wlc_name=target.name) for row in snapshot.rows],
            parser_warnings=[f"{target.name}: {warning}" for warning in snapshot.parser_warnings],
        )
    finally:
        session.disconnect()
```

Keep `run_once` working by wrapping one target or leaving it as-is for tests.

- [ ] **Step 5: Update display**

Modify `ap_port_audit/display.py`:

Add WLC column before AP:

```python
    table.add_column("WLC", no_wrap=True)
```

Rows:

```python
            row.wlc_name,
            row.ap_name,
```

Metadata rows need one extra leading cell. Failure footer:

```python
    for failure in snapshot.failures:
        table.add_row(failure.wlc_name, "WLC Failure", "", "", "", "", "", failure.message, style="red")
```

For the no-issues panel, if failures exist, render the table instead of the green no-issues panel so failures remain visible.

- [ ] **Step 6: Run aggregation tests**

Run:

```bash
pytest tests/test_ap_port_app.py tests/test_ap_port_display.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add ap_port_audit/models.py ap_port_audit/app.py ap_port_audit/display.py tests/test_ap_port_app.py tests/test_ap_port_display.py
git commit -m "Aggregate AP port audit across WLCs"
```

---

### Task 5: Documentation, Examples, And Full Verification

**Files:**
- Modify: `config.example.yaml`
- Modify: `README.md`
- Existing tests: all AP port, WLC target, concurrency, and wifiops CLI tests.

- [ ] **Step 1: Update config example**

In `config.example.yaml`, add a commented or active example that shows `wlcs:` and `wifiops.wlc_concurrency`.

Use this shape:

```yaml
wifiops:
  wlc_concurrency: 3

wlcs:
  - name: "mby-1"
    host: "192.0.2.10"
    credential_profile: "c9800-admin"
  - name: "mby-2"
    host: "192.0.2.11"
    credential_profile: "c9800-admin"
```

Keep the existing single `wlc:` example valid. If both are shown active, add a comment that `wlcs:` wins for multi-WLC-aware commands.

- [ ] **Step 2: Update README usage**

In `README.md`, update the AP Ethernet Port Audit section with:

````markdown
Multi-WLC config can use `wlcs:`:

```yaml
wlcs:
  - name: mby-1
    host: 10.0.0.10
    credential_profile: c9800-admin
  - name: mby-2
    host: 10.0.0.11
    credential_profile: c9800-admin
```

With `wlcs:` configured, `wifiops c9800 ap-ports --config config.yaml` runs all WLCs by default. Use `--wlc NAME` to target one or more controllers:

```bash
wifiops c9800 ap-ports --config config.yaml --wlc mby-1
wifiops c9800 ap-ports --config config.yaml --wlc mby-1 --wlc mby-2
wifiops c9800 ap-ports --config config.yaml --wlc-concurrency 5
```
````

- [ ] **Step 3: Run focused tests**

Run:

```bash
pytest tests/test_wlc_targets.py tests/test_concurrency.py tests/test_ap_port_*.py tests/test_wifiops_cli.py -q
```

Expected: PASS.

- [ ] **Step 4: Run full suite**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config.example.yaml README.md
git commit -m "Document multi-WLC AP port audit"
```

If verification required small code or test fixes, include those files in this commit and mention them in the commit body.

---

## Self-Review

- Spec coverage: The plan covers `wlcs:`, backward-compatible `wlc:`, name selection, bounded concurrency, partial failure behavior, `ap-ports` aggregation, WLC output identity, and tests.
- Scope control: `radio` and `client` are not converted in this implementation.
- Type consistency: `WlcTarget`, `APPortFailure`, `APPortSnapshot.failures`, and `APPortRow.wlc_name` are introduced before use.
- Display table metadata row cell counts are covered by Task 4 display tests after adding the WLC column.
