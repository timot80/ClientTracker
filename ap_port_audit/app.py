from __future__ import annotations

from dataclasses import replace

from rich.console import Console
from rich.panel import Panel

from ap_port_audit.display import build_port_table
from ap_port_audit.models import APPortAuditConfig, APPortFailure, APPortSnapshot
from ap_port_audit.parser import parse_ethernet_statistics
from ap_port_audit.wlc import APPortAuditSession
from ap_radio_monitor.models import WLCConfig
from wifiops.concurrency import run_bounded
from wifiops.wlc_targets import WlcTarget


def collect_once(session, config: APPortAuditConfig) -> APPortSnapshot:
    del config
    output = session.get_ethernet_statistics()
    snapshot = parse_ethernet_statistics(output)
    if not snapshot.rows:
        if _is_empty_ap_inventory_output(output):
            return snapshot
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
            return APPortFailure(wlc_name=target.name, message=_failure_message(snapshot))
        return APPortSnapshot(
            rows=[replace(row, wlc_name=target.name) for row in snapshot.rows],
            parser_warnings=[f"{target.name}: {warning}" for warning in snapshot.parser_warnings],
        )
    except Exception as exc:
        return APPortFailure(wlc_name=target.name, message=f"poll failed: {exc}")
    finally:
        try:
            session.disconnect()
        except Exception:
            pass


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
    return Panel(_failure_message(snapshot), title="AP Ethernet Port Audit", border_style="red")


def _failure_message(snapshot: APPortSnapshot) -> str:
    message = snapshot.poll_error
    if snapshot.error_excerpt:
        message = f"{message}\n{snapshot.error_excerpt}"
    return message


def _output_excerpt(output: str, limit: int = 160) -> str:
    collapsed = " ".join(output.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit] + "..."


def _is_empty_ap_inventory_output(output: str) -> bool:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return False
    return all(
        line.startswith(("Load for ", "Time source is "))
        for line in lines
    )
