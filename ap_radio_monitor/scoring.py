from __future__ import annotations

import fnmatch

from ap_radio_monitor.models import APBalanceConfig, APLoad, BalanceScore


SEVERITY_ORDER = {
    "IMBALANCED": 0,
    "WARNING": 1,
    "OK": 2,
    "IDLE": 3,
    "INSUFFICIENT_DATA": 4,
}


def filter_aps(aps: list[APLoad], config: APBalanceConfig) -> list[APLoad]:
    """Apply AP name include/exclude wildcard filters."""
    filtered = []
    for ap in aps:
        included = not config.include or any(fnmatch.fnmatch(ap.name, pattern) for pattern in config.include)
        excluded = any(fnmatch.fnmatch(ap.name, pattern) for pattern in config.exclude)
        if included and not excluded:
            filtered.append(ap)
    return filtered


def score_ap(ap: APLoad, config: APBalanceConfig) -> BalanceScore:
    """Score radio client distribution for one AP."""
    comparable = _comparable_clients(ap, config)
    if ap.total_clients < config.min_total_clients:
        if comparable and all(value == 0 for value in comparable):
            return BalanceScore(status="IDLE", reason="zero clients")
        return BalanceScore(status="INSUFFICIENT_DATA", reason="below minimum clients")
    if len(comparable) < 2:
        return BalanceScore(status="INSUFFICIENT_DATA", reason="fewer than two comparable slots")
    if not any(value > 0 for value in comparable):
        return BalanceScore(status="IDLE", reason="zero clients")

    max_clients = max(comparable)
    min_clients = min(comparable)
    spread = max_clients - min_clients
    nonzero = [value for value in comparable if value > 0]
    ratio = None
    if len(nonzero) >= 2:
        ratio = max_clients / min(nonzero)

    if (ratio is not None and ratio >= config.ratio_threshold) or spread >= config.min_difference:
        return BalanceScore(
            status="IMBALANCED",
            max_clients=max_clients,
            min_clients=min_clients,
            spread=spread,
            ratio=ratio,
            reason="threshold exceeded",
        )

    warning_ratio = config.ratio_threshold / 2
    warning_difference = config.min_difference / 2
    if (ratio is not None and ratio >= warning_ratio) or spread >= warning_difference:
        return BalanceScore(
            status="WARNING",
            max_clients=max_clients,
            min_clients=min_clients,
            spread=spread,
            ratio=ratio,
            reason="approaching threshold",
        )

    return BalanceScore(
        status="OK",
        max_clients=max_clients,
        min_clients=min_clients,
        spread=spread,
        ratio=ratio,
        reason="within threshold",
    )


def sort_rows(rows: list[tuple[APLoad, BalanceScore]]) -> list[tuple[APLoad, BalanceScore]]:
    """Sort AP rows by severity, then worst spread and ratio."""
    return sorted(
        rows,
        key=lambda row: (
            SEVERITY_ORDER.get(row[1].status, 99),
            -row[1].spread,
            -(row[1].ratio or 0),
            row[0].name,
        ),
    )


def _comparable_clients(ap: APLoad, config: APBalanceConfig) -> list[int]:
    included_slots = set(config.included_slots)
    excluded_slots = set(config.excluded_slots)
    values = []
    for slot in ap.slot_loads:
        if slot.clients is None:
            continue
        if included_slots and slot.slot not in included_slots:
            continue
        if slot.slot in excluded_slots:
            continue
        if slot.clients == 0 and not config.include_zero_client_slots:
            continue
        values.append(slot.clients)
    return values
