from __future__ import annotations

from rich.panel import Panel
from rich.table import Table

from ap_port_audit.models import APPortAuditConfig, APPortSnapshot
from ap_port_audit.scoring import row_statuses, sort_rows, visible_rows


def build_port_table(snapshot: APPortSnapshot, config: APPortAuditConfig) -> Panel:
    rows = sort_rows(visible_rows(snapshot.rows, config), config)
    if not rows and not config.show_all and not snapshot.poll_error and not snapshot.failures:
        return Panel("No AP Ethernet port issues found", title="AP Ethernet Port Audit", border_style="green")

    table = Table(expand=False)
    table.add_column("WLC", no_wrap=True)
    table.add_column("AP", no_wrap=True)
    table.add_column("Interface", no_wrap=True)
    table.add_column("Link Status", no_wrap=True)
    table.add_column("Speed", justify="right", no_wrap=True)
    table.add_column("Duplex", no_wrap=True)
    table.add_column("Port Status", no_wrap=True)
    table.add_column("Notes")

    if not rows and snapshot.rows and snapshot.failures and not config.show_all:
        table.add_row("", "No AP Ethernet port issues found", "", "", "", "", "", "", style="green")

    for row in rows:
        statuses = row_statuses(row, config)
        table.add_row(
            row.wlc_name,
            row.ap_name,
            row.interface,
            row.link_status,
            row.speed_text,
            row.duplex,
            ", ".join(statuses),
            ", ".join(row.notes),
            style=_status_style(statuses),
        )

    if snapshot.poll_error or snapshot.parser_warnings or snapshot.failures:
        table.add_section()
    if snapshot.poll_error:
        table.add_row("", "Poll Error", "", "", "", "", "", snapshot.poll_error, style="red")
    for warning in snapshot.parser_warnings[:5]:
        table.add_row("", "Warning", "", "", "", "", "", warning, style="yellow")
    if len(snapshot.parser_warnings) > 5:
        table.add_row(
            "",
            "Warning",
            "",
            "",
            "",
            "",
            "",
            f"{len(snapshot.parser_warnings) - 5} additional parser warnings hidden",
            style="yellow",
        )
    for failure in snapshot.failures:
        table.add_row(failure.wlc_name, "WLC Failure", "", "", "", "", "", failure.message, style="red")

    title = f"{len(rows)} shown / {len(snapshot.rows)} ports | AP Ethernet Port Audit"
    return Panel(table, title=title, border_style="cyan", expand=False)


def _status_style(statuses: tuple[str, ...]) -> str:
    for status in statuses:
        if status in {"LOW-SPEED", "HALF-DUPLEX"}:
            return "red"
    if "UNKNOWN" in statuses:
        return "yellow"
    return "green"
