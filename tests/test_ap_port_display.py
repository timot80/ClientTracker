from rich.console import Console

from ap_port_audit.display import build_port_table
from ap_port_audit.models import APPortAuditConfig, APPortRow, APPortSnapshot


def row(ap_name, speed_mbps=100, duplex="Full"):
    return APPortRow(
        ap_name=ap_name,
        interface="GigabitEthernet0",
        link_status="UP",
        speed_text=f"{speed_mbps} Mbps",
        speed_mbps=speed_mbps,
        duplex=duplex,
    )


def test_build_port_table_renders_problem_rows():
    console = Console(record=True, width=140)

    console.print(build_port_table(APPortSnapshot(rows=[row("BAD-AP")]), APPortAuditConfig()))
    rendered = console.export_text()

    assert "BAD-AP" in rendered
    assert "LOW-SPEED" in rendered
    assert "GigabitEthernet0" in rendered


def test_build_port_table_renders_no_issues_panel_for_problem_only_empty_result():
    console = Console(record=True, width=120)

    console.print(build_port_table(APPortSnapshot(rows=[row("OK-AP", speed_mbps=5000)]), APPortAuditConfig()))
    rendered = console.export_text()

    assert "No AP Ethernet port issues found" in rendered


def test_build_port_table_includes_parser_warnings():
    console = Console(record=True, width=140)

    console.print(
        build_port_table(
            APPortSnapshot(rows=[row("BAD-AP")], parser_warnings=["line 3: skipped malformed row"]),
            APPortAuditConfig(),
        )
    )
    rendered = console.export_text()

    assert "line 3: skipped malformed row" in rendered
