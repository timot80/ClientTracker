from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from ap_filesystem_audit.models import APFilesystemAuditConfig, APFilesystemSnapshot
from ap_filesystem_audit.scoring import row_status, visible_rows


def build_filesystem_table(snapshot: APFilesystemSnapshot, config: APFilesystemAuditConfig):
    rows = visible_rows(snapshot.rows, config)
    renderables = []
    if rows:
        table = Table(title=f"{len(rows)} shown / {len(snapshot.rows)} filesystems | AP Filesystem Audit")
        for column in ("WLC", "AP", "AP IP", "Filesystem", "Mount", "Size", "Used", "Available", "Use%", "Status", "Notes"):
            table.add_column(column)
        for row in rows:
            table.add_row(
                row.wlc_name,
                row.ap_name,
                row.ap_host,
                row.filesystem,
                row.mount,
                row.size,
                row.used,
                row.available,
                "" if row.used_percent is None else f"{row.used_percent}%",
                row_status(row, config),
                "; ".join(row.notes),
            )
        renderables.append(table)
    else:
        renderables.append(Panel("No AP filesystem issues found", title="AP Filesystem Audit"))

    if snapshot.failures:
        failures = Table(title="Failures")
        for column in ("WLC", "AP", "AP IP", "Error"):
            failures.add_column(column)
        for failure in snapshot.failures:
            failures.add_row(failure.wlc_name, failure.ap_name, failure.ap_host, failure.message)
        renderables.append(failures)

    if snapshot.parser_warnings:
        warnings = Table(title="Parser Warnings")
        for column in ("Status", "Warning"):
            warnings.add_column(column)
        for warning in snapshot.parser_warnings:
            warnings.add_row("UNKNOWN", warning)
        renderables.append(warnings)

    return Group(*renderables)
