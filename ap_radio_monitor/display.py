from __future__ import annotations

from rich.panel import Panel
from rich.table import Table

from ap_radio_monitor.models import APBalanceConfig, APLoad, BalanceScore, LoadInfoSnapshot
from ap_radio_monitor.scoring import filter_aps, score_ap, sort_rows


STATUS_STYLES = {
    "IMBALANCED": "red",
    "WARNING": "yellow",
    "OK": "green",
    "INSUFFICIENT_DATA": "dim",
}


def render_slot_distribution(ap: APLoad, width: int = 16) -> str:
    """Render per-slot client counts as compact relative text bars."""
    numeric_clients = [slot.clients for slot in ap.slot_loads if slot.clients is not None]
    max_clients = max(numeric_clients, default=0)
    parts = []
    for slot in ap.slot_loads:
        if slot.clients is None:
            parts.append(f"S{slot.slot} --")
            continue
        util = "--" if slot.utilization is None else f"{slot.utilization}%"
        bar = _bar(slot.clients, max_clients, width)
        parts.append(f"S{slot.slot} {slot.clients} cl / {util} util {bar}")
    return " | ".join(parts)


def build_monitor_table(snapshot: LoadInfoSnapshot, config: APBalanceConfig) -> Panel:
    """Build the Rich renderable for one monitor snapshot."""
    table = Table(expand=True)
    table.add_column("AP Name", overflow="fold")
    table.add_column("Clients", justify="right")
    table.add_column("Radio Client Distribution", overflow="fold")
    table.add_column("Balance", justify="right")

    aps = filter_aps(snapshot.ap_loads, config)
    rows = [(ap, score_ap(ap, config)) for ap in aps]
    if config.only_imbalanced:
        rows = [(ap, score) for ap, score in rows if score.status == "IMBALANCED"]

    for ap, score in sort_rows(rows):
        style = STATUS_STYLES.get(score.status, "")
        table.add_row(
            ap.name,
            str(ap.total_clients),
            render_slot_distribution(ap),
            _balance_text(score),
            style=style,
        )

    if snapshot.poll_error or snapshot.parser_warnings:
        table.add_section()
    if snapshot.poll_error:
        table.add_row("Poll Error", "", snapshot.poll_error, "", style="red")
    for warning in snapshot.parser_warnings[:3]:
        table.add_row("Warning", "", warning, "", style="yellow")
    if len(snapshot.parser_warnings) > 3:
        table.add_row(
            "Warning",
            "",
            f"{len(snapshot.parser_warnings) - 3} additional parser warnings hidden",
            "",
            style="yellow",
        )

    title = f"AP Radio Distribution Monitor | {len(aps)} APs"
    return Panel(table, title=title, border_style="cyan")


def _bar(clients: int, max_clients: int, width: int) -> str:
    if clients == 0:
        return "."
    if max_clients <= 0:
        return ""
    length = max(1, round((clients / max_clients) * width))
    return "█" * length


def _balance_text(score: BalanceScore) -> str:
    if score.ratio is None:
        ratio = "N/A"
    else:
        ratio = f"{score.ratio:.1f}:1".replace(".0:1", ":1")
    if score.status == "INSUFFICIENT_DATA":
        return score.status
    return f"{score.status} {ratio} spread {score.spread}"
