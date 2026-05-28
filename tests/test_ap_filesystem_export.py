import csv

from ap_filesystem_audit.export import write_csv
from ap_filesystem_audit.models import (
    APFilesystemAuditConfig,
    APFilesystemFailure,
    APFilesystemRow,
    APFilesystemSnapshot,
    APReloadResult,
)


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


def test_write_csv_exports_visible_problem_rows_and_failures(tmp_path):
    path = tmp_path / "out" / "filesystems.csv"
    snapshot = APFilesystemSnapshot(
        rows=[row("OK", 10), row("FULL", 100)],
        failures=[APFilesystemFailure(wlc_name="wlc-1", ap_name="AP-FAIL", ap_host="10.1.2.4", message="ssh failed")],
    )

    write_csv(path, snapshot, APFilesystemAuditConfig())

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [item["record_type"] for item in rows] == ["filesystem", "failure"]
    assert rows[0]["ap_name"] == "FULL"
    assert rows[1]["error"] == "ssh failed"


def test_write_csv_all_includes_ok_rows(tmp_path):
    path = tmp_path / "filesystems.csv"

    write_csv(path, APFilesystemSnapshot(rows=[row("OK", 10)]), APFilesystemAuditConfig(show_all=True))

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["ap_name"] == "OK"
    assert rows[0]["status"] == "OK"


def test_write_csv_exports_parser_warnings_as_unknown_failures(tmp_path):
    path = tmp_path / "filesystems.csv"
    snapshot = APFilesystemSnapshot(parser_warnings=["AP-1: line 2: skipped malformed row"])

    write_csv(path, snapshot, APFilesystemAuditConfig())

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["record_type"] == "failure"
    assert rows[0]["status"] == "UNKNOWN"
    assert rows[0]["error"] == "AP-1: line 2: skipped malformed row"


def test_write_csv_exports_reload_fields_for_filesystem_rows(tmp_path):
    path = tmp_path / "filesystems.csv"
    snapshot = APFilesystemSnapshot(
        rows=[row()],
        reload_results=[
            APReloadResult(
                wlc_name="wlc-1",
                wlc_host="192.0.2.10",
                ap_name="AP-1",
                ap_host="10.1.2.3",
                action="triggered",
                output="cli: AP Rebooting",
            )
        ],
    )

    write_csv(path, snapshot, APFilesystemAuditConfig())

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["reload_action"] == "triggered"
    assert rows[0]["reload_output"] == "cli: AP Rebooting"
