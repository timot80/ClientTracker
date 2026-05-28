from __future__ import annotations

import csv
from pathlib import Path

from ap_filesystem_audit.models import APFilesystemAuditConfig, APFilesystemSnapshot
from ap_filesystem_audit.scoring import row_status, visible_rows


CSV_FIELDS = [
    "record_type",
    "wlc_name",
    "wlc_host",
    "ap_name",
    "ap_host",
    "filesystem",
    "mount",
    "size",
    "used",
    "available",
    "used_percent",
    "status",
    "notes",
    "reload_action",
    "reload_output",
    "error",
]


def write_csv(path: str | Path, snapshot: APFilesystemSnapshot, config: APFilesystemAuditConfig) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        reloads_by_ap = {
            (result.wlc_name, result.wlc_host, result.ap_name, result.ap_host): result
            for result in snapshot.reload_results
        }
        for row in visible_rows(snapshot.rows, config):
            reload_result = reloads_by_ap.get((row.wlc_name, row.wlc_host, row.ap_name, row.ap_host))
            writer.writerow(
                {
                    "record_type": "filesystem",
                    "wlc_name": row.wlc_name,
                    "wlc_host": row.wlc_host,
                    "ap_name": row.ap_name,
                    "ap_host": row.ap_host,
                    "filesystem": row.filesystem,
                    "mount": row.mount,
                    "size": row.size,
                    "used": row.used,
                    "available": row.available,
                    "used_percent": "" if row.used_percent is None else row.used_percent,
                    "status": row_status(row, config),
                    "notes": "; ".join(row.notes),
                    "reload_action": "" if reload_result is None else reload_result.action,
                    "reload_output": "" if reload_result is None else reload_result.output,
                    "error": "",
                }
            )
        for failure in snapshot.failures:
            writer.writerow(
                {
                    "record_type": "failure",
                    "wlc_name": failure.wlc_name,
                    "wlc_host": failure.wlc_host,
                    "ap_name": failure.ap_name,
                    "ap_host": failure.ap_host,
                    "filesystem": "",
                    "mount": "",
                    "size": "",
                    "used": "",
                    "available": "",
                    "used_percent": "",
                    "status": "",
                    "notes": "",
                    "reload_action": "",
                    "reload_output": "",
                    "error": failure.message,
                }
            )
        for warning in snapshot.parser_warnings:
            writer.writerow(
                {
                    "record_type": "failure",
                    "wlc_name": "",
                    "wlc_host": "",
                    "ap_name": "",
                    "ap_host": "",
                    "filesystem": "",
                    "mount": "",
                    "size": "",
                    "used": "",
                    "available": "",
                    "used_percent": "",
                    "status": "UNKNOWN",
                    "notes": "",
                    "reload_action": "",
                    "reload_output": "",
                    "error": warning,
                }
            )
