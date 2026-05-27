from __future__ import annotations

from time import sleep

from rich.console import Console
from rich.live import Live
from rich.panel import Panel

from ap_radio_monitor.display import build_monitor_table
from ap_radio_monitor.models import APBalanceConfig, LoadInfoSnapshot, WLCConfig
from ap_radio_monitor.parser import LoadInfoParseError, parse_load_info
from ap_radio_monitor.wlc import WLCLoadInfoSession


def collect_once(session, config: APBalanceConfig) -> LoadInfoSnapshot:
    """Collect and parse one load-info snapshot from an existing WLC-like session."""
    del config
    output = session.get_load_info()
    return parse_load_info(output)


def run_once(wlc_config: WLCConfig, balance_config: APBalanceConfig, console: Console) -> None:
    session = WLCLoadInfoSession(wlc_config)
    try:
        session.connect()
        snapshot = _collect_with_error_handling(session, balance_config)
        console.print(_render_snapshot(snapshot, balance_config))
    finally:
        session.disconnect()


def run_live(wlc_config: WLCConfig, balance_config: APBalanceConfig, console: Console) -> None:
    session = WLCLoadInfoSession(wlc_config)
    last_snapshot = LoadInfoSnapshot()
    try:
        session.connect()
        with Live(console=console, refresh_per_second=2, screen=False) as live:
            while True:
                last_snapshot = _collect_with_error_handling(
                    session, balance_config, previous=last_snapshot
                )
                live.update(_render_snapshot(last_snapshot, balance_config))
                sleep(balance_config.refresh_seconds)
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
        )
    except Exception as exc:
        return LoadInfoSnapshot(
            ap_loads=previous.ap_loads if previous else [],
            parser_warnings=previous.parser_warnings if previous else [],
            poll_error=f"poll failed: {exc}",
        )


def _render_snapshot(snapshot: LoadInfoSnapshot, config: APBalanceConfig):
    if snapshot.poll_error and not snapshot.ap_loads:
        return Panel(f"[red]{snapshot.poll_error}[/red]", title="AP Radio Distribution Monitor")
    return build_monitor_table(snapshot, config)
