from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from ap_port_audit.display import build_port_table
from ap_port_audit.models import APPortAuditConfig, APPortSnapshot
from ap_port_audit.parser import parse_ethernet_statistics
from ap_port_audit.wlc import APPortAuditSession
from ap_radio_monitor.models import WLCConfig
from wifiops.wlc_targets import WlcTarget


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


def run_once(wlc_config: WLCConfig, audit_config: APPortAuditConfig, console: Console) -> int:
    session = APPortAuditSession(wlc_config)
    try:
        console.print(f"[cyan]Connecting to WLC {wlc_config.host}[/cyan]")
        session.connect()
        console.print("[cyan]Collecting AP Ethernet statistics[/cyan]")
        snapshot = _collect_with_error_handling(session, audit_config)
        console.print("[cyan]Rendering AP Ethernet audit[/cyan]")
        if snapshot.poll_error and not snapshot.rows:
            console.print(_error_panel(snapshot))
            return 1
        else:
            console.print(build_port_table(snapshot, audit_config))
            return 0
    finally:
        session.disconnect()


def run_multi(
    targets: list[WlcTarget],
    audit_config: APPortAuditConfig,
    concurrency: int,
    console: Console,
) -> int:
    del concurrency
    return run_once(targets[0].config, audit_config, console)


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
