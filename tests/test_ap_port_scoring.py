from ap_port_audit.models import APPortAuditConfig, APPortRow
from ap_port_audit.scoring import filter_rows, row_statuses, sort_rows, visible_rows


def row(ap_name, speed_mbps=1000, duplex="Full", interface="GigabitEthernet0"):
    return APPortRow(
        ap_name=ap_name,
        interface=interface,
        link_status="UP",
        speed_text="Unknown" if speed_mbps is None else f"{speed_mbps} Mbps",
        speed_mbps=speed_mbps,
        duplex=duplex,
    )


def test_row_statuses_flags_low_speed_and_half_duplex():
    statuses = row_statuses(row("AP-1", speed_mbps=100, duplex="Half"), APPortAuditConfig())

    assert statuses == ("LOW-SPEED", "HALF-DUPLEX")


def test_row_statuses_flags_unknown_values():
    assert row_statuses(row("AP-1", speed_mbps=None, duplex="Auto"), APPortAuditConfig()) == ("UNKNOWN",)


def test_row_statuses_ok_at_or_above_threshold_with_full_duplex():
    assert row_statuses(row("AP-1", speed_mbps=2500), APPortAuditConfig()) == ("OK",)


def test_filter_rows_applies_include_then_exclude():
    rows = [row("MATCH-1"), row("MATCH-TEST"), row("OTHER-1")]

    filtered = filter_rows(rows, APPortAuditConfig(include=("MATCH-*",), exclude=("*TEST",)))

    assert [item.ap_name for item in filtered] == ["MATCH-1"]


def test_visible_rows_default_shows_only_problem_rows():
    rows = [row("OK-AP", speed_mbps=5000), row("BAD-AP", speed_mbps=100)]

    visible = visible_rows(rows, APPortAuditConfig())

    assert [item.ap_name for item in visible] == ["BAD-AP"]


def test_visible_rows_show_all_includes_healthy_rows():
    rows = [row("OK-AP", speed_mbps=5000), row("BAD-AP", speed_mbps=100)]

    visible = visible_rows(rows, APPortAuditConfig(show_all=True))

    assert [item.ap_name for item in visible] == ["OK-AP", "BAD-AP"]


def test_sort_rows_puts_problems_before_ok_rows():
    rows = [row("OK-AP", speed_mbps=5000), row("BAD-AP", speed_mbps=100)]

    sorted_items = sort_rows(rows, APPortAuditConfig(show_all=True))

    assert [item.ap_name for item in sorted_items] == ["BAD-AP", "OK-AP"]
