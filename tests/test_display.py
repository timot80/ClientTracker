from rich.console import Console

from ap_radio_monitor.display import build_monitor_table, render_slot_cell, render_slot_distribution
from ap_radio_monitor.models import APBalanceConfig, APLoad, LoadInfoSnapshot, RadioSlotLoad


def make_ap(name, clients):
    return APLoad(
        name=name,
        radio_mac="0c75.bdb5.6380",
        identity_label="Radio Mac",
        slots=len(clients),
        total_clients=sum(value for value in clients if value is not None),
        slot_loads=[
            RadioSlotLoad(slot=index, clients=value, utilization=10)
            for index, value in enumerate(clients)
        ],
    )


def test_render_slot_distribution_uses_relative_bars_and_na_marker():
    ap = make_ap("NOC-AP-1", [1, 50, None])

    rendered = render_slot_distribution(ap, width=12)

    assert "S0  1 cl  10% util" in rendered
    assert "S1 50 cl  10% util" in rendered
    assert "S2 --" in rendered
    assert "████" in rendered


def test_render_slot_distribution_uses_one_line_per_slot():
    ap = make_ap("NOC-AP-1", [2, 2, 1, None])

    rendered = render_slot_distribution(ap, width=12)

    assert rendered.count("\n") == 3
    assert "S0  2 cl  10% util" in rendered
    assert "S3 --" in rendered


def test_render_slot_cell_is_compact_for_one_line_table():
    ap = make_ap("NOC-AP-1", [2, 2, 1, None])

    assert render_slot_cell(ap, 0, width=4) == "2c 10%"
    assert render_slot_cell(ap, 2, width=4) == "1c 10%"
    assert render_slot_cell(ap, 3, width=4) == "--"


def test_build_monitor_table_uses_slot_columns_for_one_line_rows():
    snapshot = LoadInfoSnapshot(ap_loads=[make_ap("NOC-AP-1", [2, 2, 1, None])])
    console = Console(record=True, width=140)

    console.print(build_monitor_table(snapshot, APBalanceConfig()))
    rendered = console.export_text()

    assert "S0" in rendered
    assert "S1" in rendered
    assert "S2" in rendered
    assert "S3" in rendered
    assert "Radio Slots" not in rendered
    assert "2c 10%" in rendered


def test_build_monitor_table_renders_parser_warning_and_poll_error():
    snapshot = LoadInfoSnapshot(
        ap_loads=[make_ap("NOC-AP-1", [1, 50])],
        parser_warnings=["line 12: skipped malformed row"],
        poll_error="poll failed: timeout",
    )
    console = Console(record=True, width=140)

    console.print(build_monitor_table(snapshot, APBalanceConfig()))
    rendered = console.export_text()

    assert "poll failed: timeout" in rendered
    assert "line 12: skipped malformed row" in rendered
