from __future__ import annotations

from fnmatch import fnmatchcase

from ap_filesystem_audit.models import APFilesystemAuditConfig, APFilesystemRow, APTarget


def row_status(row: APFilesystemRow, config: APFilesystemAuditConfig) -> str:
    if row.used_percent is None:
        return "UNKNOWN"
    if row.used_percent == 100:
        return "FULL"
    if row.used_percent >= config.min_used_percent:
        return "HIGH"
    return "OK"


def filter_ap_targets(targets: list[APTarget], config: APFilesystemAuditConfig) -> list[APTarget]:
    filtered = list(targets)
    if config.ap_names or config.ap_hosts:
        allowed_names = set(config.ap_names)
        allowed_hosts = set(config.ap_hosts)
        filtered = [
            target
            for target in filtered
            if target.name in allowed_names or target.host in allowed_hosts
        ]
    if config.include:
        filtered = [
            target
            for target in filtered
            if any(fnmatchcase(target.name, pattern) for pattern in config.include)
        ]
    if config.exclude:
        filtered = [
            target
            for target in filtered
            if not any(fnmatchcase(target.name, pattern) for pattern in config.exclude)
        ]
    return filtered


def visible_rows(rows: list[APFilesystemRow], config: APFilesystemAuditConfig) -> list[APFilesystemRow]:
    if config.show_all:
        return list(rows)
    return [row for row in rows if row_status(row, config) != "OK"]


def sort_rows(rows: list[APFilesystemRow], config: APFilesystemAuditConfig) -> list[APFilesystemRow]:
    status_order = {"FULL": 0, "HIGH": 1, "UNKNOWN": 2, "OK": 3}
    return sorted(
        rows,
        key=lambda row: (
            row.wlc_name,
            row.ap_name,
            status_order.get(row_status(row, config), 99),
            row.mount,
            row.filesystem,
        ),
    )
