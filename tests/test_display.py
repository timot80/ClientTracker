import re
from datetime import datetime

from rich.console import Console

from ap_radio_monitor.display import build_monitor_table, render_slot_cell, render_slot_distribution
from ap_radio_monitor.models import APBalanceConfig, APLoad, LoadInfoSnapshot, RadioSlotLoad


def make_ap(name, clients, utilizations=None):
    utilizations = utilizations or [10 for _ in clients]
    return APLoad(
        name=name,
        radio_mac="0c75.bdb5.6380",
        identity_label="Radio Mac",
        slots=len(clients),
        total_clients=sum(value for value in clients if value is not None),
        slot_loads=[
            RadioSlotLoad(slot=index, clients=value, utilization=utilizations[index])
            for index, value in enumerate(clients)
        ],
    )


def make_ap_with_wlc_total(name, wlc_total, clients, utilizations=None):
    utilizations = utilizations or [10 for _ in clients]
    return APLoad(
        name=name,
        radio_mac="0c75.bdb5.6380",
        identity_label="Radio Mac",
        slots=len(clients),
        total_clients=wlc_total,
        slot_loads=[
            RadioSlotLoad(slot=index, clients=value, utilization=utilizations[index])
            for index, value in enumerate(clients)
        ],
    )


def rendered_row_for(rendered: str, ap_name: str) -> str:
    return next(line for line in rendered.splitlines() if ap_name in line)


def test_build_monitor_table_labels_wlc_total_explicitly():
    snapshot = LoadInfoSnapshot(ap_loads=[make_ap("NOC-AP-1", [2, 2, 1, None])])
    console = Console(record=True, width=140)

    console.print(build_monitor_table(snapshot, APBalanceConfig()))
    rendered = console.export_text()

    assert "WLC Tot" in rendered
    assert "Cli" not in rendered


def test_build_monitor_table_shows_wlc_total_and_slot_total_when_counts_disagree():
    ap = make_ap_with_wlc_total("MISMATCH-AP", 0, [1, 0, 0])
    snapshot = LoadInfoSnapshot(ap_loads=[ap])
    console = Console(record=True, width=160)

    console.print(build_monitor_table(snapshot, APBalanceConfig()))
    rendered = console.export_text()

    assert "WLC Tot" in rendered
    assert "Slot Tot" in rendered
    assert "MISMATCH-AP" in rendered
    row = rendered_row_for(rendered, "MISMATCH-AP")
    assert re.search(r"MISMATCH-AP.*\b0\b.*\b1\b.*1c", row)


def test_two_column_metadata_rows_align_with_slot_total_column():
    snapshot = LoadInfoSnapshot(
        ap_loads=[
            make_ap_with_wlc_total("VISIBLE-AP", 1, [1, 0]),
            make_ap_with_wlc_total("HIDDEN-AP", 0, [0, 0]),
        ],
        parser_warnings=["line 99: skipped malformed row"],
    )
    console = Console(record=True, width=220)

    console.print(
        build_monitor_table(
            snapshot,
            APBalanceConfig(display_columns=2, hide_idle=True),
        )
    )
    rendered = console.export_text()

    assert "Slot Tot" in rendered
    assert "Warning" in rendered
    assert "line 99: skipped malformed row" in rendered
    assert "Hidden by filter" in rendered


def test_slot_total_uses_visible_slots_only():
    ap = make_ap_with_wlc_total("HIDDEN-SLOT-AP", 6, [5, 1, 0])
    snapshot = LoadInfoSnapshot(ap_loads=[ap])
    console = Console(record=True, width=160)

    console.print(build_monitor_table(snapshot, APBalanceConfig(included_slots=(1, 2))))
    rendered = console.export_text()

    assert "HIDDEN-SLOT-AP" in rendered
    assert "S0" not in rendered
    assert "S1" in rendered
    assert "S2" in rendered
    row = rendered_row_for(rendered, "HIDDEN-SLOT-AP")
    assert re.search(r"HIDDEN-SLOT-AP.*\b6\b.*\b1\b.*1c", row)


def test_slot_total_ignores_auto_excluded_none_slots():
    ap = make_ap_with_wlc_total("AUTO-EXCLUDED-AP", 6, [None, 1, 0])
    snapshot = LoadInfoSnapshot(ap_loads=[ap])
    console = Console(record=True, width=160)

    console.print(build_monitor_table(snapshot, APBalanceConfig(included_slots=(0, 1, 2))))
    rendered = console.export_text()

    row = rendered_row_for(rendered, "AUTO-EXCLUDED-AP")
    assert "--" in row
    assert re.search(r"AUTO-EXCLUDED-AP.*\b6\b.*\b1\b.*--.*1c", row)


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


def test_build_monitor_table_hides_excluded_slot_columns():
    snapshot = LoadInfoSnapshot(ap_loads=[make_ap("NOC-AP-1", [2, 2, 1, None])])
    console = Console(record=True, width=140)

    console.print(build_monitor_table(snapshot, APBalanceConfig(excluded_slots=(0,))))
    rendered = console.export_text()

    assert "S0" not in rendered
    assert "S1" in rendered
    assert "S2" in rendered
    assert "S3" in rendered


def test_build_monitor_table_only_shows_included_slot_columns():
    snapshot = LoadInfoSnapshot(ap_loads=[make_ap("NOC-AP-1", [2, 2, 1, None])])
    console = Console(record=True, width=140)

    console.print(build_monitor_table(snapshot, APBalanceConfig(included_slots=(1, 2))))
    rendered = console.export_text()

    assert "S0" not in rendered
    assert "S1" in rendered
    assert "S2" in rendered
    assert "S3" not in rendered


def test_build_monitor_table_shows_last_polled_time_in_title():
    snapshot = LoadInfoSnapshot(
        ap_loads=[make_ap("NOC-AP-1", [2, 2, 1, None])],
        timestamp=datetime(2026, 5, 27, 14, 3, 9),
    )
    console = Console(record=True, width=140)

    console.print(build_monitor_table(snapshot, APBalanceConfig()))
    rendered = console.export_text()

    assert "Last 14:03:09" in rendered


def test_build_monitor_table_keeps_last_poll_visible_in_narrow_title():
    snapshot = LoadInfoSnapshot(
        ap_loads=[make_ap("NOC-AP-MBY-1", [2, 2, 1, None])],
        timestamp=datetime(2026, 5, 27, 14, 3, 9),
    )
    console = Console(record=True, width=50)

    console.print(build_monitor_table(snapshot, APBalanceConfig()))
    first_line = console.export_text().splitlines()[0]

    assert "Last 14:03:09" in first_line


def test_build_monitor_table_stays_compact_on_wide_terminal():
    snapshot = LoadInfoSnapshot(
        ap_loads=[make_ap("NOC-AP-MBY-1", [2, 2, 1, None])],
        timestamp=datetime(2026, 5, 27, 14, 3, 9),
    )
    console = Console(record=True, width=220)

    console.print(build_monitor_table(snapshot, APBalanceConfig()))
    header_line = next(line for line in console.export_text().splitlines() if "┃ AP" in line)

    assert len(header_line) < 180


def test_build_monitor_table_uses_two_side_by_side_row_groups():
    snapshot = LoadInfoSnapshot(
        ap_loads=[
            make_ap("AP-0", [1, 1]),
            make_ap("AP-1", [2, 2]),
            make_ap("AP-2", [3, 3]),
            make_ap("AP-3", [4, 4]),
        ]
    )
    console = Console(record=True, width=220)

    console.print(build_monitor_table(snapshot, APBalanceConfig(display_columns=2)))
    rendered = console.export_text()
    header_line = next(line for line in rendered.splitlines() if "┃ AP" in line)

    assert header_line.count("AP") == 2
    assert any("AP-0" in line and "AP-2" in line for line in rendered.splitlines())
    assert any("AP-1" in line and "AP-3" in line for line in rendered.splitlines())


def test_build_monitor_table_renders_idle_for_zero_client_ap():
    snapshot = LoadInfoSnapshot(ap_loads=[make_ap("IDLE-AP", [0, 0, 0, None])])
    console = Console(record=True, width=120)

    console.print(build_monitor_table(snapshot, APBalanceConfig()))
    rendered = console.export_text()

    assert "IDLE" in rendered
    assert "NO DATA" not in rendered


def test_build_monitor_table_does_not_render_no_data_for_dual_radio_single_reporting_slot():
    snapshot = LoadInfoSnapshot(ap_loads=[make_ap("MBY-EVNT-CNTR_HLWY-22", [15, None])])
    console = Console(record=True, width=120)

    console.print(build_monitor_table(snapshot, APBalanceConfig()))
    rendered = console.export_text()

    assert "MBY-EVNT-CNTR_HLWY-22" in rendered
    assert "OK" in rendered
    assert "NO DATA" not in rendered


def test_build_monitor_table_limits_rows_and_reports_hidden_counts():
    aps = [make_ap(f"AP-{index}", [1, 1]) for index in range(4)]
    snapshot = LoadInfoSnapshot(ap_loads=aps)
    console = Console(record=True, width=120)

    console.print(build_monitor_table(snapshot, APBalanceConfig(limit=2)))
    rendered = console.export_text()

    assert "Showing 2/4" in rendered
    assert "Hidden by limit: 2 OK" in rendered
    assert "AP-0" in rendered
    assert "AP-1" in rendered
    assert "AP-2" not in rendered


def test_build_monitor_table_only_problem_keeps_busy_idle_and_hides_idle():
    snapshot = LoadInfoSnapshot(
        ap_loads=[
            make_ap("BUSY-IDLE", [0, 0], utilizations=[25, 0]),
            make_ap("IDLE-AP", [0, 0], utilizations=[0, 0]),
            make_ap("OK-AP", [2, 2]),
        ]
    )
    console = Console(record=True, width=120)

    console.print(build_monitor_table(snapshot, APBalanceConfig(only_problem=True)))
    rendered = console.export_text()

    assert "BUSY-IDLE" in rendered
    assert "IDLE-AP" not in rendered
    assert "OK-AP" not in rendered
    assert "Hidden by filter:" in rendered


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
