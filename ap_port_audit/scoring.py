from __future__ import annotations

from fnmatch import fnmatchcase

from ap_port_audit.models import APPortAuditConfig, APPortRow


def row_statuses(row: APPortRow, config: APPortAuditConfig) -> tuple[str, ...]:
    statuses: list[str] = []
    duplex = row.duplex.lower()
    if row.speed_mbps is None or not row.duplex:
        statuses.append("UNKNOWN")
    elif row.speed_mbps < config.speed_threshold:
        statuses.append("LOW-SPEED")
    if duplex == "half":
        statuses.append("HALF-DUPLEX")
    elif duplex not in {"full", "half"} and "UNKNOWN" not in statuses:
        statuses.append("UNKNOWN")
    return tuple(statuses or ["OK"])


def filter_rows(rows: list[APPortRow], config: APPortAuditConfig) -> list[APPortRow]:
    filtered = list(rows)
    if config.include:
        filtered = [
            row
            for row in filtered
            if any(fnmatchcase(row.ap_name, pattern) for pattern in config.include)
        ]
    if config.exclude:
        filtered = [
            row
            for row in filtered
            if not any(fnmatchcase(row.ap_name, pattern) for pattern in config.exclude)
        ]
    return filtered


def visible_rows(rows: list[APPortRow], config: APPortAuditConfig) -> list[APPortRow]:
    filtered = filter_rows(rows, config)
    if config.show_all:
        return filtered
    return [row for row in filtered if row_statuses(row, config) != ("OK",)]


def sort_rows(rows: list[APPortRow], config: APPortAuditConfig) -> list[APPortRow]:
    return sorted(rows, key=lambda row: (_problem_rank(row, config), row.ap_name, row.interface))


def _problem_rank(row: APPortRow, config: APPortAuditConfig) -> int:
    return 1 if row_statuses(row, config) == ("OK",) else 0
