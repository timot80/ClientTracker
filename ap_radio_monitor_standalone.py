#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import getpass
import os
import re
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Any, Optional

try:
    from netmiko import ConnectHandler
except ImportError:  # pragma: no cover - operator guidance path
    ConnectHandler = None

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:  # pragma: no cover - operator guidance path
    Console = None
    Live = None
    Panel = None
    Table = None
    Text = None

try:
    import yaml
except ImportError:  # pragma: no cover - operator guidance path
    yaml = None


@dataclass(frozen=True)
class WLCConfig:
    host: str
    username: str
    password: str
    enable: str = ""
    read_timeout: int = 90


@dataclass(frozen=True)
class APBalanceConfig:
    refresh_seconds: int = 30
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    included_slots: tuple[int, ...] = ()
    excluded_slots: tuple[int, ...] = ()
    only_imbalanced: bool = False
    only_problem: bool = False
    hide_idle: bool = False
    limit: int = 75
    display_columns: int = 1
    auto_exclude_admin_down_slots: bool = False
    min_total_clients: int = 1
    busy_idle_utilization: int = 20
    ratio_threshold: float = 10.0
    min_difference: int = 20
    include_zero_client_slots: bool = True


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


@dataclass(frozen=True)
class LoadInfoSnapshot:
    ap_loads: list[APLoad] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    parser_warnings: list[str] = field(default_factory=list)
    poll_error: str = ""


@dataclass(frozen=True)
class BalanceScore:
    status: str
    max_clients: int = 0
    min_clients: int = 0
    spread: int = 0
    ratio: Optional[float] = None
    reason: str = ""


class LoadInfoParseError(ValueError):
    pass


class WLCLoadInfoSession:
    def __init__(self, config: WLCConfig):
        self.config = config
        self.connection = None
        self._lock = threading.Lock()
        self._admin_down_slots_by_ap: dict[str, set[int]] = {}
        self._checked_slots_by_ap: dict[str, set[int]] = {}
        self._radio_summary_loaded = False

    def connect(self) -> None:
        if ConnectHandler is None:
            raise RuntimeError("Missing dependency: pip install netmiko rich")
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

    def get_load_info(self) -> str:
        with self._lock:
            if self.connection is None:
                raise RuntimeError("WLC session not connected")
            return self.connection.send_command(
                "show ap summary load-info",
                expect_string=r"#",
                read_timeout=self.config.read_timeout,
            )

    def get_admin_down_slots(self, ap_name: str, slot_numbers: tuple[int, ...]) -> set[int]:
        checked = self._checked_slots_by_ap.get(ap_name, set())
        missing_slots = tuple(slot for slot in slot_numbers if slot not in checked)
        if not missing_slots:
            return set(self._admin_down_slots_by_ap.get(ap_name, set())).intersection(slot_numbers)

        with self._lock:
            if self.connection is None:
                raise RuntimeError("WLC session not connected")
            if not self._radio_summary_loaded:
                self._load_radio_summary_slot_states()
                self._radio_summary_loaded = True
                checked = self._checked_slots_by_ap.get(ap_name, set())
                missing_slots = tuple(slot for slot in slot_numbers if slot not in checked)
                if not missing_slots:
                    return set(self._admin_down_slots_by_ap.get(ap_name, set())).intersection(slot_numbers)
            known = self._admin_down_slots_by_ap.setdefault(ap_name, set())
            checked = self._checked_slots_by_ap.setdefault(ap_name, set())
            for slot in missing_slots:
                output = self.connection.send_command(
                    f"show ap name {ap_name} config slot {slot}",
                    expect_string=r"#",
                    read_timeout=self.config.read_timeout,
                )
                checked.add(slot)
                if _is_admin_down_slot_config(output):
                    known.add(slot)
        return set(self._admin_down_slots_by_ap.get(ap_name, set())).intersection(slot_numbers)

    def _load_radio_summary_slot_states(self) -> None:
        for command in (
            "show ap dot11 24ghz summary",
            "show ap dot11 5ghz summary",
            "show ap dot11 6ghz summary",
        ):
            try:
                output = _send_command_timing(
                    self.connection,
                    command,
                    read_timeout=self.config.read_timeout,
                )
            except Exception:
                continue
            _merge_radio_summary(output, self._admin_down_slots_by_ap, self._checked_slots_by_ap)

    def disconnect(self) -> None:
        with self._lock:
            if self.connection is not None:
                try:
                    self.connection.disconnect()
                finally:
                    self.connection = None


def _is_admin_down_slot_config(output: str) -> bool:
    admin_state = _config_value(output, "Administrative State")
    operation_state = _config_value(output, "Operation State")
    if admin_state and admin_state.lower() != "enabled":
        return True
    if operation_state and operation_state.lower() != "up":
        return True
    return False


def _config_value(output: str, label: str) -> str:
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith(label) or ":" not in stripped:
            continue
        return stripped.split(":", 1)[1].strip()
    return ""


def _send_command_timing(connection, command: str, read_timeout: int) -> str:
    if hasattr(connection, "send_command_timing"):
        return connection.send_command_timing(command, read_timeout=read_timeout, last_read=3)
    return connection.send_command(command, expect_string=r"#", read_timeout=read_timeout)


def _merge_radio_summary(
    output: str,
    admin_down_slots_by_ap: dict[str, set[int]],
    checked_slots_by_ap: dict[str, set[int]],
) -> None:
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 6 or not parts[2].isdigit():
            continue
        ap_name = parts[0]
        slot = int(parts[2])
        admin_state = parts[3].lower()
        oper_state = parts[4].lower()
        checked_slots_by_ap.setdefault(ap_name, set()).add(slot)
        if admin_state != "enabled" or oper_state != "up":
            admin_down_slots_by_ap.setdefault(ap_name, set()).add(slot)


_MAC_RE = re.compile(r"^[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}$")
_SLOT_RE = re.compile(r"\bSlot(\d+)\b", re.IGNORECASE)
_SEVERITY_ORDER = {
    "IMBALANCED": 0,
    "BUSY-IDLE": 1,
    "WARNING": 2,
    "INSUFFICIENT_DATA": 3,
    "OK": 4,
    "IDLE": 5,
}
_STATUS_STYLES = {
    "IMBALANCED": "red",
    "BUSY-IDLE": "yellow",
    "WARNING": "yellow",
    "OK": "green",
    "IDLE": "dim",
    "INSUFFICIENT_DATA": "dim",
}


def parse_load_info(output: str) -> LoadInfoSnapshot:
    header = _detect_header(output)
    if header is None:
        if _is_empty_load_info_output(output):
            return LoadInfoSnapshot()
        raise LoadInfoParseError("Could not find supported load-info header")

    mode, slot_numbers = header
    ap_loads: list[APLoad] = []
    parser_warnings: list[str] = []
    after_header = False

    for line_number, line in enumerate(output.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if _is_header_line(stripped):
            after_header = True
            continue
        if not after_header or _is_ignored_line(stripped):
            continue
        try:
            ap_loads.append(_parse_row(stripped, mode, slot_numbers))
        except ValueError:
            parser_warnings.append(f"line {line_number}: skipped malformed row")

    if not ap_loads:
        raise LoadInfoParseError("Could not parse any AP rows from load-info output")
    return LoadInfoSnapshot(ap_loads=ap_loads, parser_warnings=parser_warnings)


def _detect_header(output: str) -> tuple[str, list[int]] | None:
    for line in output.splitlines():
        slot_numbers = [int(match) for match in _SLOT_RE.findall(line)]
        if not slot_numbers:
            continue
        normalized = " ".join(line.lower().split())
        if "ap name" in normalized and "radio mac" in normalized:
            return "observed", slot_numbers
        if "wtp-mac" in normalized and "ap-name" in normalized:
            return "documented", slot_numbers
    return None


def _is_empty_load_info_output(output: str) -> bool:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return bool(lines) and all(_is_ignored_line(line) for line in lines)


def _is_header_line(line: str) -> bool:
    normalized = " ".join(line.lower().split())
    return (
        ("slot0" in normalized and ("ap name" in normalized or "ap-name" in normalized))
        or "clients utilisation" in normalized
        or "clients utilization" in normalized
    )


def _is_ignored_line(line: str) -> bool:
    lowered = line.lower()
    return (
        set(line) <= {"-"}
        or lowered.startswith("load for ")
        or lowered.startswith("time source ")
        or lowered.endswith("#sh ap summary load-info")
    )


def _parse_row(line: str, mode: str, slot_numbers: list[int]) -> APLoad:
    tokens = line.split()
    pair_count = len(slot_numbers)
    if len(tokens) < (pair_count * 2) + 3:
        raise ValueError("not enough fields")

    pair_tokens = tokens[-pair_count * 2 :]
    prefix = tokens[: -pair_count * 2]
    if len(prefix) < 3:
        raise ValueError("not enough identity fields")

    if len(prefix) >= 4:
        slots = _to_int(prefix[-2])
        total_clients = _to_int(prefix[-1])
        identity_tokens = prefix[:-2]
    else:
        slots = _to_int(prefix[-1])
        total_clients = _sum_slot_clients(pair_tokens)
        identity_tokens = prefix[:-1]

    if mode == "observed":
        if not identity_tokens or not _MAC_RE.match(identity_tokens[-1]):
            raise ValueError("missing radio mac")
        radio_mac = identity_tokens[-1].lower()
        name = " ".join(identity_tokens[:-1]).strip()
        identity_label = "Radio Mac"
    else:
        if not identity_tokens or not _MAC_RE.match(identity_tokens[0]):
            raise ValueError("missing wtp mac")
        radio_mac = identity_tokens[0].lower()
        name = " ".join(identity_tokens[1:]).strip()
        identity_label = "WTP-Mac"

    if not name:
        raise ValueError("missing ap name")

    slot_loads = [
        RadioSlotLoad(
            slot=slot,
            clients=_to_optional_int(pair_tokens[index * 2]),
            utilization=_to_optional_int(pair_tokens[index * 2 + 1]),
        )
        for index, slot in enumerate(slot_numbers)
    ]
    return APLoad(
        name=name,
        radio_mac=radio_mac,
        identity_label=identity_label,
        slots=slots,
        total_clients=total_clients,
        slot_loads=slot_loads,
    )


def _to_int(value: str) -> int:
    if not value.isdigit():
        raise ValueError(f"expected integer, got {value!r}")
    return int(value)


def _to_optional_int(value: str) -> int | None:
    if value.upper() == "NA":
        return None
    return _to_int(value)


def _sum_slot_clients(pair_tokens: list[str]) -> int:
    total = 0
    for index in range(0, len(pair_tokens), 2):
        clients = _to_optional_int(pair_tokens[index])
        if clients is not None:
            total += clients
    return total


def filter_aps(aps: list[APLoad], config: APBalanceConfig) -> list[APLoad]:
    filtered = []
    for ap in aps:
        included = not config.include or any(fnmatch.fnmatch(ap.name, pattern) for pattern in config.include)
        excluded = any(fnmatch.fnmatch(ap.name, pattern) for pattern in config.exclude)
        if included and not excluded:
            filtered.append(ap)
    return filtered


def score_ap(ap: APLoad, config: APBalanceConfig) -> BalanceScore:
    comparable = _comparable_clients(ap, config)
    comparable_total = sum(comparable)

    if comparable_total < config.min_total_clients:
        if comparable and all(value == 0 for value in comparable):
            return _zero_client_score(ap, config)
        return BalanceScore(status="INSUFFICIENT_DATA", reason="below minimum clients")
    if len(comparable) < 2:
        if ap.slots <= 2 and comparable and any(value > 0 for value in comparable):
            only_value = comparable[0]
            return BalanceScore(
                status="OK",
                max_clients=only_value,
                min_clients=only_value,
                spread=0,
                reason="single comparable slot",
            )
        return BalanceScore(status="INSUFFICIENT_DATA", reason="fewer than two comparable slots")
    if not any(value > 0 for value in comparable):
        return _zero_client_score(ap, config)

    max_clients = max(comparable)
    min_clients = min(comparable)
    spread = max_clients - min_clients
    nonzero = [value for value in comparable if value > 0]
    ratio = max_clients / min(nonzero) if len(nonzero) >= 2 else None

    if (ratio is not None and ratio >= config.ratio_threshold) or spread >= config.min_difference:
        return BalanceScore("IMBALANCED", max_clients, min_clients, spread, ratio, "threshold exceeded")

    if (
        (ratio is not None and ratio >= config.ratio_threshold / 2)
        or spread >= config.min_difference / 2
    ):
        return BalanceScore("WARNING", max_clients, min_clients, spread, ratio, "approaching threshold")

    return BalanceScore("OK", max_clients, min_clients, spread, ratio, "within threshold")


def _zero_client_score(ap: APLoad, config: APBalanceConfig) -> BalanceScore:
    utilizations = [
        slot.utilization
        for slot in ap.slot_loads
        if _is_comparable_slot(slot, config)
        and slot.clients == 0
        and slot.utilization is not None
    ]
    if any(utilization >= config.busy_idle_utilization for utilization in utilizations):
        return BalanceScore(status="BUSY-IDLE", reason="zero clients with busy channel")
    return BalanceScore(status="IDLE", reason="zero clients")


def _comparable_clients(ap: APLoad, config: APBalanceConfig) -> list[int]:
    values = []
    for slot in ap.slot_loads:
        if slot.clients is None:
            continue
        if not _is_comparable_slot(slot, config):
            continue
        if slot.clients == 0 and not config.include_zero_client_slots:
            continue
        values.append(slot.clients)
    return values


def _is_comparable_slot(slot, config: APBalanceConfig) -> bool:
    included_slots = set(config.included_slots)
    excluded_slots = set(config.excluded_slots)
    if included_slots and slot.slot not in included_slots:
        return False
    if slot.slot in excluded_slots:
        return False
    return True


def sort_rows(rows: list[tuple[APLoad, BalanceScore]]) -> list[tuple[APLoad, BalanceScore]]:
    return sorted(
        rows,
        key=lambda row: (
            _SEVERITY_ORDER.get(row[1].status, 99),
            -max((slot.utilization for slot in row[0].slot_loads if slot.utilization is not None), default=0),
            -row[1].spread,
            -(row[1].ratio or 0),
            row[0].name,
        ),
    )


def build_monitor_table(snapshot: LoadInfoSnapshot, config: APBalanceConfig):
    table = Table(expand=False)
    visible_slots = _visible_slot_numbers(config)
    display_columns = max(1, min(config.display_columns, 2))
    _add_ap_columns(table, visible_slots)
    if display_columns == 2:
        table.add_column("", no_wrap=True)
        _add_ap_columns(table, visible_slots)

    aps = filter_aps(snapshot.ap_loads, config)
    rows = [(ap, score_ap(ap, config)) for ap in aps]
    visible_rows, hidden_by_filter = _apply_visibility(rows, config)
    sorted_rows = sort_rows(visible_rows)
    displayed_rows = sorted_rows[: config.limit]
    hidden_by_limit = sorted_rows[config.limit :]

    if display_columns == 2:
        left_rows, right_rows = _split_display_rows(displayed_rows)
        empty_cells = [""] * _ap_column_count(visible_slots)
        for index, left in enumerate(left_rows):
            right = right_rows[index] if index < len(right_rows) else None
            left_cells = _ap_row_cells(left[0], left[1], visible_slots)
            right_cells = _ap_row_cells(right[0], right[1], visible_slots) if right else empty_cells
            table.add_row(*left_cells, "", *right_cells)
    else:
        for ap, score in displayed_rows:
            table.add_row(*_ap_row_cells(ap, score, visible_slots))

    hidden_lines = _hidden_summary_lines(hidden_by_filter, hidden_by_limit)
    if snapshot.poll_error or snapshot.parser_warnings or hidden_lines:
        table.add_section()
    for line in hidden_lines:
        table.add_row(*_metadata_cells("Summary", line, visible_slots, display_columns), style="dim")
    if snapshot.poll_error:
        table.add_row(
            *_metadata_cells("Poll Error", snapshot.poll_error, visible_slots, display_columns),
            style="red",
        )
    for warning in snapshot.parser_warnings[:3]:
        table.add_row(
            *_metadata_cells("Warning", warning, visible_slots, display_columns),
            style="yellow",
        )
    if len(snapshot.parser_warnings) > 3:
        table.add_row(
            *_metadata_cells(
                "Warning",
                f"{len(snapshot.parser_warnings) - 3} additional parser warnings hidden",
                visible_slots,
                display_columns,
            ),
            style="yellow",
        )

    last_poll = snapshot.timestamp.strftime("%H:%M:%S")
    title = f"Last {last_poll} | {len(aps)} APs | Showing {len(displayed_rows)}/{len(aps)} | AP Radio"
    return Panel(table, title=title, border_style="cyan", expand=False)


def _add_ap_columns(table, visible_slots: list[int]) -> None:
    table.add_column("AP", no_wrap=True)
    table.add_column("Cli", justify="right", no_wrap=True)
    for slot_number in visible_slots:
        table.add_column(f"S{slot_number}", no_wrap=True)
    table.add_column("Balance", justify="right", no_wrap=True)


def _split_display_rows(
    rows: list[tuple[APLoad, BalanceScore]],
) -> tuple[list[tuple[APLoad, BalanceScore]], list[tuple[APLoad, BalanceScore]]]:
    midpoint = (len(rows) + 1) // 2
    return rows[:midpoint], rows[midpoint:]


def _ap_column_count(visible_slots: list[int]) -> int:
    return len(visible_slots) + 3


def _ap_row_cells(ap: APLoad, score: BalanceScore, visible_slots: list[int]):
    style = _STATUS_STYLES.get(score.status, "")
    values = [
        ap.name,
        str(ap.total_clients),
        *(_render_slot_cell(ap, slot_number) for slot_number in visible_slots),
        _balance_text(score),
    ]
    if Text is None:
        return values
    return [Text(value, style=style) for value in values]


def _visible_slot_numbers(config: APBalanceConfig) -> list[int]:
    if config.included_slots:
        slot_numbers = sorted(set(config.included_slots))
    else:
        slot_numbers = [0, 1, 2, 3]
    excluded_slots = set(config.excluded_slots)
    return [slot_number for slot_number in slot_numbers if slot_number not in excluded_slots]


def _metadata_row(label: str, message: str, visible_slots: list[int]) -> list[str]:
    if not visible_slots:
        return [label, "", message]
    return [label, "", message, *([""] * (len(visible_slots) - 1)), ""]


def _wide_metadata_row(label: str, message: str, visible_slots: list[int]) -> list[str]:
    left = _metadata_row(label, message, visible_slots)
    right = [""] * _ap_column_count(visible_slots)
    return [*left, "", *right]


def _metadata_cells(
    label: str,
    message: str,
    visible_slots: list[int],
    display_columns: int,
) -> list[str]:
    if display_columns == 2:
        return _wide_metadata_row(label, message, visible_slots)
    return _metadata_row(label, message, visible_slots)


def _render_slot_cell(ap: APLoad, slot_number: int) -> str:
    slot_by_number = {slot.slot: slot for slot in ap.slot_loads}
    slot = slot_by_number.get(slot_number)
    if slot is None or slot.clients is None:
        return "--"
    util = "--" if slot.utilization is None else f"{slot.utilization}%"
    return f"{slot.clients}c {util}"


def _balance_text(score: BalanceScore) -> str:
    if score.status == "INSUFFICIENT_DATA":
        return "NO DATA"
    if score.status in {"IDLE", "BUSY-IDLE"}:
        return score.status
    ratio = "N/A" if score.ratio is None else f"{score.ratio:.1f}:1".replace(".0:1", ":1")
    return f"{score.status} {ratio} d{score.spread}"


def _apply_visibility(
    rows: list[tuple[APLoad, BalanceScore]], config: APBalanceConfig
) -> tuple[list[tuple[APLoad, BalanceScore]], list[tuple[APLoad, BalanceScore]]]:
    if config.only_imbalanced:
        visible = [(ap, score) for ap, score in rows if score.status == "IMBALANCED"]
    elif config.only_problem:
        problem_statuses = {"IMBALANCED", "BUSY-IDLE", "WARNING", "INSUFFICIENT_DATA"}
        visible = [(ap, score) for ap, score in rows if score.status in problem_statuses]
    elif config.hide_idle:
        visible = [(ap, score) for ap, score in rows if score.status != "IDLE"]
    else:
        visible = list(rows)
    visible_ids = {id(ap) for ap, _score in visible}
    hidden = [(ap, score) for ap, score in rows if id(ap) not in visible_ids]
    return visible, hidden


def _hidden_summary_lines(
    hidden_by_filter: list[tuple[APLoad, BalanceScore]],
    hidden_by_limit: list[tuple[APLoad, BalanceScore]],
) -> list[str]:
    lines = []
    if hidden_by_filter:
        lines.append(f"Hidden by filter: {_format_status_counts(hidden_by_filter)}")
    if hidden_by_limit:
        lines.append(f"Hidden by limit: {_format_status_counts(hidden_by_limit)}")
    return lines


def _format_status_counts(rows: list[tuple[APLoad, BalanceScore]]) -> str:
    counts: dict[str, int] = {}
    for _ap, score in rows:
        label = "NO DATA" if score.status == "INSUFFICIENT_DATA" else score.status
        counts[label] = counts.get(label, 0) + 1
    order = ["IMBALANCED", "BUSY-IDLE", "WARNING", "NO DATA", "OK", "IDLE"]
    return ", ".join(f"{counts[status]} {status}" for status in order if status in counts)


def collect_once(session: WLCLoadInfoSession, config: APBalanceConfig) -> LoadInfoSnapshot:
    snapshot = parse_load_info(session.get_load_info())
    if config.auto_exclude_admin_down_slots:
        return _auto_exclude_admin_down_slots(session, snapshot, config)
    return snapshot


def collect_with_error_handling(
    session: WLCLoadInfoSession,
    config: APBalanceConfig,
    previous: LoadInfoSnapshot | None = None,
) -> LoadInfoSnapshot:
    try:
        return collect_once(session, config)
    except Exception as exc:
        return LoadInfoSnapshot(
            ap_loads=previous.ap_loads if previous else [],
            parser_warnings=previous.parser_warnings if previous else [],
            poll_error=f"poll failed: {exc}",
        )


class StartupReporter:
    def __init__(self, console):
        self.console = console

    def step(self, message: str) -> None:
        self.console.print(f"[cyan]{message}[/cyan]")


def run_once(
    wlc_config: WLCConfig,
    balance_config: APBalanceConfig,
    console,
    reporter: StartupReporter | None = None,
) -> None:
    session = WLCLoadInfoSession(wlc_config)
    reporter = reporter or StartupReporter(console)
    try:
        reporter.step(f"Connecting to WLC {wlc_config.host}")
        session.connect()
        reporter.step("Collecting AP radio load-info")
        if balance_config.auto_exclude_admin_down_slots:
            reporter.step("Loading radio admin/oper state")
        snapshot = collect_with_error_handling(session, balance_config)
        reporter.step("Rendering monitor")
        console.print(build_monitor_table(snapshot, balance_config))
    finally:
        session.disconnect()


def run_live(
    wlc_config: WLCConfig,
    balance_config: APBalanceConfig,
    console,
    reporter: StartupReporter | None = None,
) -> None:
    session = WLCLoadInfoSession(wlc_config)
    reporter = reporter or StartupReporter(console)
    last_snapshot = LoadInfoSnapshot()
    try:
        reporter.step(f"Connecting to WLC {wlc_config.host}")
        session.connect()
        reporter.step("Collecting AP radio load-info")
        if balance_config.auto_exclude_admin_down_slots:
            reporter.step("Loading radio admin/oper state")
        last_snapshot = collect_with_error_handling(session, balance_config)
        reporter.step("Rendering monitor")
        with Live(console=console, refresh_per_second=2, screen=False) as live:
            while True:
                live.update(build_monitor_table(last_snapshot, balance_config))
                sleep(balance_config.refresh_seconds)
                last_snapshot = collect_with_error_handling(
                    session,
                    balance_config,
                    previous=last_snapshot,
                )
    except KeyboardInterrupt:
        console.print("\nShutting down...")
    finally:
        session.disconnect()


def _auto_exclude_admin_down_slots(
    session,
    snapshot: LoadInfoSnapshot,
    config: APBalanceConfig,
) -> LoadInfoSnapshot:
    ap_loads = []
    inspectable_ids = {id(ap) for ap in filter_aps(snapshot.ap_loads, config)}
    for ap in snapshot.ap_loads:
        if id(ap) not in inspectable_ids:
            ap_loads.append(ap)
            continue
        candidate_slots = tuple(
            slot.slot
            for slot in ap.slot_loads
            if slot.clients == 0 and slot.utilization == 0
        )
        if not candidate_slots:
            ap_loads.append(ap)
            continue
        admin_down_slots = session.get_admin_down_slots(ap.name, candidate_slots)
        if not admin_down_slots:
            ap_loads.append(ap)
            continue
        ap_loads.append(_copy_with_unavailable_slots(ap, admin_down_slots))
    return LoadInfoSnapshot(
        ap_loads=ap_loads,
        timestamp=snapshot.timestamp,
        parser_warnings=snapshot.parser_warnings,
        poll_error=snapshot.poll_error,
    )


def _copy_with_unavailable_slots(ap: APLoad, unavailable_slots: set[int]) -> APLoad:
    slot_loads = [
        RadioSlotLoad(slot=slot.slot, clients=None, utilization=None)
        if slot.slot in unavailable_slots
        else slot
        for slot in ap.slot_loads
    ]
    return APLoad(
        name=ap.name,
        radio_mac=ap.radio_mac,
        identity_label=ap.identity_label,
        slots=ap.slots,
        total_clients=ap.total_clients,
        slot_loads=slot_loads,
        timestamp=ap.timestamp,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standalone Catalyst 9800 AP radio client balance monitor."
    )
    parser.add_argument("--config", help="Optional YAML config file")
    parser.add_argument("--host", help="WLC hostname/IP")
    parser.add_argument("--username", help="WLC username")
    parser.add_argument("--password", help="WLC password")
    parser.add_argument("--enable", help="Enable secret")
    parser.add_argument("--read-timeout", type=int, help="WLC command read timeout")
    parser.add_argument("--refresh", type=int, help="Live refresh interval in seconds")
    parser.add_argument("--once", action="store_true", help="Print one snapshot and exit")
    parser.add_argument("--limit", type=int, help="Maximum AP rows to display")
    parser.add_argument("--columns", type=int, choices=(1, 2), help="AP row groups to display")
    parser.add_argument(
        "--auto-exclude-admin-down-slots",
        action="store_true",
        help="Query AP slot config and ignore admin-disabled/down 0-client slots",
    )
    parser.add_argument("--include", action="append", default=[], help="AP name wildcard to include")
    parser.add_argument("--exclude", action="append", default=[], help="AP name wildcard to exclude")
    parser.add_argument("--include-slot", type=int, action="append", default=[], help="Radio slot to show/score")
    parser.add_argument("--exclude-slot", type=int, action="append", default=[], help="Radio slot to hide/ignore")
    parser.add_argument("--only-imbalanced", action="store_true", help="Only show imbalanced APs")
    parser.add_argument("--only-problem", action="store_true", help="Show only problem APs")
    parser.add_argument("--hide-idle", action="store_true", help="Hide clean zero-client APs")
    parser.add_argument("--ratio-threshold", type=float, help="Imbalance ratio threshold")
    parser.add_argument("--min-difference", type=int, help="Imbalance client spread threshold")
    parser.add_argument(
        "--busy-idle-util",
        type=int,
        help="Utilization threshold for zero-client BUSY-IDLE APs",
    )
    return parser.parse_args(argv)


def build_configs(args: argparse.Namespace) -> tuple[WLCConfig, APBalanceConfig]:
    raw = _load_yaml_config(args.config)
    wlc_raw = _mapping(raw.get("wlc", {}), "wlc")
    ap_raw = _mapping(raw.get("ap_balance", {}), "ap_balance")
    imbalance_raw = _mapping(ap_raw.get("imbalance", {}), "ap_balance.imbalance")

    host = _first_present(args.host, os.environ.get("WLC_HOST"), wlc_raw.get("host"), "")
    username = _first_present(
        args.username, os.environ.get("WLC_USERNAME"), wlc_raw.get("username"), ""
    )
    password = _first_present(
        args.password, os.environ.get("WLC_PASSWORD"), wlc_raw.get("password"), ""
    )
    enable = _first_present(args.enable, os.environ.get("WLC_ENABLE"), wlc_raw.get("enable"), "")
    read_timeout = _first_present(args.read_timeout, wlc_raw.get("read_timeout"), 90)

    wlc_config = WLCConfig(
        host=str(host),
        username=str(username),
        password=str(password),
        enable=str(enable or ""),
        read_timeout=int(read_timeout),
    )
    balance_config = APBalanceConfig(
        refresh_seconds=int(_first_present(args.refresh, ap_raw.get("refresh_seconds"), 30)),
        include=tuple(args.include or _str_list(ap_raw.get("include", []))),
        exclude=tuple(args.exclude or _str_list(ap_raw.get("exclude", []))),
        included_slots=tuple(args.include_slot or _int_list(ap_raw.get("included_slots", []))),
        excluded_slots=tuple(args.exclude_slot or _int_list(ap_raw.get("excluded_slots", []))),
        only_imbalanced=bool(
            args.only_imbalanced or bool(ap_raw.get("only_imbalanced", False))
        ),
        only_problem=bool(args.only_problem or bool(ap_raw.get("only_problem", False))),
        hide_idle=bool(args.hide_idle or bool(ap_raw.get("hide_idle", False))),
        limit=int(_first_present(args.limit, ap_raw.get("limit"), 75)),
        display_columns=int(_first_present(args.columns, ap_raw.get("display_columns"), 1)),
        auto_exclude_admin_down_slots=bool(
            args.auto_exclude_admin_down_slots
            or bool(ap_raw.get("auto_exclude_admin_down_slots", False))
        ),
        min_total_clients=int(ap_raw.get("min_total_clients", 1)),
        busy_idle_utilization=int(
            _first_present(args.busy_idle_util, ap_raw.get("busy_idle_utilization"), 20)
        ),
        ratio_threshold=float(
            _first_present(args.ratio_threshold, imbalance_raw.get("ratio_threshold"), 10.0)
        ),
        min_difference=int(
            _first_present(args.min_difference, imbalance_raw.get("min_difference"), 20)
        ),
        include_zero_client_slots=bool(imbalance_raw.get("include_zero_client_slots", True)),
    )
    return wlc_config, balance_config


def _load_yaml_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    if yaml is None:
        raise RuntimeError("Missing dependency for YAML config: pip install pyyaml")
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise RuntimeError(f"Config file not found: {cfg_path}")
    with cfg_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return _mapping(raw, "config")


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{name} must be a YAML mapping")
    return value


def _first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _int_list(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    return [int(item) for item in value]


def main(argv: list[str] | None = None) -> int:
    if Console is None or Live is None or Panel is None or Table is None:
        print("Missing dependency: pip install rich netmiko", file=sys.stderr)
        return 1
    args = parse_args(argv)
    try:
        wlc_config, balance_config = build_configs(args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not wlc_config.host:
        print("Missing --host or WLC_HOST", file=sys.stderr)
        return 1
    if not wlc_config.username:
        print("Missing --username or WLC_USERNAME", file=sys.stderr)
        return 1
    if not wlc_config.password:
        wlc_config = WLCConfig(
            host=wlc_config.host,
            username=wlc_config.username,
            password=getpass.getpass("WLC password: "),
            enable=wlc_config.enable,
            read_timeout=wlc_config.read_timeout,
        )
    console = Console()
    if args.once:
        run_once(wlc_config, balance_config, console)
    else:
        run_live(wlc_config, balance_config, console)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
