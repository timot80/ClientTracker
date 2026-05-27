from __future__ import annotations

from rich.panel import Panel
from rich.table import Table

from ap_radio_monitor.models import APBalanceConfig, APLoad, BalanceScore, LoadInfoSnapshot
from ap_radio_monitor.scoring import filter_aps, score_ap, sort_rows


STATUS_STYLES = {
    "IMBALANCED": "red",
    "BUSY-IDLE": "yellow",
    "WARNING": "yellow",
    "OK": "green",
    "IDLE": "dim",
    "INSUFFICIENT_DATA": "dim",
}


def render_slot_distribution(ap: APLoad, width: int = 8) -> str:
    """Render per-slot client counts as readable multi-line relative bars."""
    numeric_clients = [slot.clients for slot in ap.slot_loads if slot.clients is not None]
    max_clients = max(numeric_clients, default=0)
    parts = []
    for slot in ap.slot_loads:
        if slot.clients is None:
            parts.append(f"S{slot.slot} --")
            continue
        util = "--" if slot.utilization is None else f"{slot.utilization}%"
        bar = _bar(slot.clients, max_clients, width)
        parts.append(f"S{slot.slot} {slot.clients:>2} cl  {util:>3} util  {bar}")
    return "\n".join(parts)


def render_slot_cell(ap: APLoad, slot_number: int, width: int = 4) -> str:
    """Render one AP slot as a compact one-line table cell."""
    slot_by_number = {slot.slot: slot for slot in ap.slot_loads}
    slot = slot_by_number.get(slot_number)
    if slot is None or slot.clients is None:
        return "--"
    util = "--" if slot.utilization is None else f"{slot.utilization}%"
    return f"{slot.clients}c {util}"


def build_monitor_table(snapshot: LoadInfoSnapshot, config: APBalanceConfig) -> Panel:
    """Build the Rich renderable for one monitor snapshot."""
    table = Table(expand=False)
    table.add_column("AP", no_wrap=True)
    table.add_column("Cli", justify="right", no_wrap=True)
    table.add_column("S0", no_wrap=True)
    table.add_column("S1", no_wrap=True)
    table.add_column("S2", no_wrap=True)
    table.add_column("S3", no_wrap=True)
    table.add_column("Balance", justify="right", no_wrap=True)

    aps = filter_aps(snapshot.ap_loads, config)
    rows = [(ap, score_ap(ap, config)) for ap in aps]
    visible_rows, hidden_by_visibility = _apply_visibility(rows, config)
    sorted_rows = sort_rows(visible_rows)
    displayed_rows = sorted_rows[: config.limit]
    hidden_by_limit = sorted_rows[config.limit :]

    for ap, score in displayed_rows:
        style = STATUS_STYLES.get(score.status, "")
        table.add_row(
            ap.name,
            str(ap.total_clients),
            render_slot_cell(ap, 0),
            render_slot_cell(ap, 1),
            render_slot_cell(ap, 2),
            render_slot_cell(ap, 3),
            _balance_text(score),
            style=style,
        )

    hidden_lines = _hidden_summary_lines(hidden_by_visibility, hidden_by_limit)
    if snapshot.poll_error or snapshot.parser_warnings or hidden_lines:
        table.add_section()
    for line in hidden_lines:
        table.add_row("Summary", "", line, "", "", "", "", style="dim")
    if snapshot.poll_error:
        table.add_row("Poll Error", "", snapshot.poll_error, "", "", "", "", style="red")
    for warning in snapshot.parser_warnings[:3]:
        table.add_row("Warning", "", warning, "", "", "", "", style="yellow")
    if len(snapshot.parser_warnings) > 3:
        table.add_row(
            "Warning",
            "",
            f"{len(snapshot.parser_warnings) - 3} additional parser warnings hidden",
            "",
            "",
            "",
            "",
            style="yellow",
        )

    last_poll = snapshot.timestamp.strftime("%H:%M:%S")
    title = f"Last {last_poll} | {len(aps)} APs | Showing {len(displayed_rows)}/{len(aps)} | AP Radio"
    return Panel(table, title=title, border_style="cyan", expand=False)


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
        return "NO DATA"
    if score.status == "IDLE":
        return "IDLE"
    if score.status == "BUSY-IDLE":
        return "BUSY-IDLE"
    return f"{score.status} {ratio} Δ{score.spread}"


def _apply_visibility(
    rows: list[tuple[APLoad, BalanceScore]], config: APBalanceConfig
) -> tuple[list[tuple[APLoad, BalanceScore]], list[tuple[APLoad, BalanceScore]]]:
    if config.only_imbalanced:
        visible = [(ap, score) for ap, score in rows if score.status == "IMBALANCED"]
    elif config.only_problem:
        problem_statuses = {"IMBALANCED", "BUSY-IDLE", "WARNING", "INSUFFICIENT_DATA"}
        visible = [(ap, score) for ap, score in rows if score.status in problem_statuses]
    elif config.hide_idle and not config.show_idle:
        visible = [(ap, score) for ap, score in rows if score.status != "IDLE"]
    else:
        visible = list(rows)
    visible_ids = {id(ap) for ap, _score in visible}
    hidden = [(ap, score) for ap, score in rows if id(ap) not in visible_ids]
    return visible, hidden


def _hidden_summary_lines(
    hidden_by_visibility: list[tuple[APLoad, BalanceScore]],
    hidden_by_limit: list[tuple[APLoad, BalanceScore]],
) -> list[str]:
    lines = []
    if hidden_by_visibility:
        lines.append(f"Hidden by filter: {_format_status_counts(hidden_by_visibility)}")
    if hidden_by_limit:
        lines.append(f"Hidden by limit: {_format_status_counts(hidden_by_limit)}")
    return lines


def _format_status_counts(rows: list[tuple[APLoad, BalanceScore]]) -> str:
    counts: dict[str, int] = {}
    for _ap, score in rows:
        label = "NO DATA" if score.status == "INSUFFICIENT_DATA" else score.status
        counts[label] = counts.get(label, 0) + 1
    order = ["IMBALANCED", "BUSY-IDLE", "WARNING", "NO DATA", "OK", "IDLE"]
    return ", ".join(f"{counts[status]} {status}" for status in order if status in counts)
