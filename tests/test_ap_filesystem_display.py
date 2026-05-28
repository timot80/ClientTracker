from rich.console import Console

from ap_filesystem_audit.display import build_filesystem_table
from ap_filesystem_audit.models import APFilesystemAuditConfig, APFilesystemFailure, APFilesystemRow, APFilesystemSnapshot


def row(ap_name="AP-1", used_percent=100):
    return APFilesystemRow(
        wlc_name="wlc-1",
        wlc_host="192.0.2.10",
        ap_name=ap_name,
        ap_host="10.1.2.3",
        filesystem="none",
        mount="/tmp",
        size="95.4M",
        used="95.0M",
        available="376.0K",
        used_percent=used_percent,
    )


def test_build_filesystem_table_renders_problem_rows():
    console = Console(record=True, width=180)

    console.print(build_filesystem_table(APFilesystemSnapshot(rows=[row()]), APFilesystemAuditConfig()))

    rendered = console.export_text()
    assert "AP-1" in rendered
    assert "/tmp" in rendered
    assert "FULL" in rendered


def test_build_filesystem_table_renders_no_issue_panel():
    console = Console(record=True, width=140)

    console.print(build_filesystem_table(APFilesystemSnapshot(rows=[row(used_percent=10)]), APFilesystemAuditConfig()))

    assert "No AP filesystem issues found" in console.export_text()


def test_build_filesystem_table_renders_failures():
    console = Console(record=True, width=180)
    snapshot = APFilesystemSnapshot(
        failures=[
            APFilesystemFailure(
                wlc_name="wlc-1",
                wlc_host="192.0.2.10",
                ap_name="AP-1",
                ap_host="10.1.2.3",
                message="ssh failed",
            )
        ]
    )

    console.print(build_filesystem_table(snapshot, APFilesystemAuditConfig()))

    rendered = console.export_text()
    assert "AP-1" in rendered
    assert "ssh failed" in rendered


def test_build_filesystem_table_renders_parser_warnings():
    console = Console(record=True, width=180)
    snapshot = APFilesystemSnapshot(parser_warnings=["AP-1: line 2: skipped malformed row"])

    console.print(build_filesystem_table(snapshot, APFilesystemAuditConfig()))

    rendered = console.export_text()
    assert "Parser Warnings" in rendered
    assert "UNKNOWN" in rendered
    assert "AP-1: line 2: skipped malformed row" in rendered
