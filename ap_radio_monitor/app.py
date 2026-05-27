from __future__ import annotations

from time import sleep

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from ap_radio_monitor.display import build_monitor_table
from ap_radio_monitor.models import APBalanceConfig, APLoad, LoadInfoSnapshot, RadioSlotLoad, WLCConfig
from ap_radio_monitor.parser import LoadInfoParseError, parse_load_info
from ap_radio_monitor.scoring import filter_aps
from ap_radio_monitor.wlc import WLCLoadInfoSession


class StartupReporter:
    def __init__(self, console: Console):
        self.console = console

    def step(self, message: str) -> None:
        self.console.print(f"[cyan]{message}[/cyan]")


def collect_once(session, config: APBalanceConfig) -> LoadInfoSnapshot:
    """Collect and parse one load-info snapshot from an existing WLC-like session."""
    output = session.get_load_info()
    try:
        snapshot = parse_load_info(output)
    except LoadInfoParseError as exc:
        excerpt = _output_excerpt(output)
        raise LoadInfoParseError(f"{exc}\nExcerpt: {excerpt}") from exc
    if config.auto_exclude_admin_down_slots:
        return _auto_exclude_admin_down_slots(session, snapshot, config)
    return snapshot


def run_once(
    wlc_config: WLCConfig,
    balance_config: APBalanceConfig,
    console: Console,
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
        snapshot = _collect_with_error_handling(session, balance_config)
        reporter.step("Rendering monitor")
        console.print(_render_snapshot(snapshot, balance_config))
    finally:
        session.disconnect()


def run_live(
    wlc_config: WLCConfig,
    balance_config: APBalanceConfig,
    console: Console,
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
        last_snapshot = _collect_with_error_handling(session, balance_config)
        reporter.step("Rendering monitor")
        with Live(console=console, refresh_per_second=2, screen=False) as live:
            while True:
                live.update(_render_snapshot(last_snapshot, balance_config))
                sleep(balance_config.refresh_seconds)
                last_snapshot = _collect_with_error_handling(
                    session, balance_config, previous=last_snapshot
                )
    except KeyboardInterrupt:
        console.print("\nShutting down...")
    finally:
        session.disconnect()


def _collect_with_error_handling(
    session, config: APBalanceConfig, previous: LoadInfoSnapshot | None = None
) -> LoadInfoSnapshot:
    try:
        return collect_once(session, config)
    except LoadInfoParseError as exc:
        return LoadInfoSnapshot(
            ap_loads=previous.ap_loads if previous else [],
            parser_warnings=previous.parser_warnings if previous else [],
            poll_error=str(exc),
            error_excerpt=_extract_error_excerpt(str(exc)),
        )
    except Exception as exc:
        return LoadInfoSnapshot(
            ap_loads=previous.ap_loads if previous else [],
            parser_warnings=previous.parser_warnings if previous else [],
            poll_error=f"poll failed: {exc}",
        )


def _render_snapshot(snapshot: LoadInfoSnapshot, config: APBalanceConfig):
    if snapshot.poll_error and not snapshot.ap_loads:
        table = Table.grid()
        table.add_column()
        table.add_row(f"[red]{snapshot.poll_error}[/red]")
        if snapshot.error_excerpt:
            table.add_row(f"[dim]{snapshot.error_excerpt}[/dim]")
        return Panel(table, title="AP Radio Distribution Monitor")
    return build_monitor_table(snapshot, config)


def _output_excerpt(output: str, limit: int = 160) -> str:
    compact = " ".join(line.strip() for line in output.splitlines() if line.strip())
    return compact[:limit]


def _extract_error_excerpt(message: str) -> str:
    marker = "\nExcerpt: "
    if marker not in message:
        return ""
    return message.split(marker, 1)[1]


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
        error_excerpt=snapshot.error_excerpt,
        raw_command=snapshot.raw_command,
    )


def _copy_with_unavailable_slots(ap: APLoad, unavailable_slots: set[int]) -> APLoad:
    slot_loads = [
        RadioSlotLoad(slot=slot.slot, clients=None, utilization=None)
        if slot.slot in unavailable_slots
        else slot
        for slot in ap.slot_loads
    ]
    warning = "auto-excluded admin-down slots: " + ", ".join(
        f"S{slot}" for slot in sorted(unavailable_slots)
    )
    return APLoad(
        name=ap.name,
        radio_mac=ap.radio_mac,
        identity_label=ap.identity_label,
        slots=ap.slots,
        total_clients=ap.total_clients,
        slot_loads=slot_loads,
        timestamp=ap.timestamp,
        warnings=[*ap.warnings, warning],
    )
