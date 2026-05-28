from ap_filesystem_audit.models import APFilesystemAuditConfig, APFilesystemRow, APTarget
from ap_filesystem_audit.scoring import filter_ap_targets, row_status, visible_rows


def fs_row(ap_name="AP-1", used_percent=95):
    return APFilesystemRow(
        wlc_name="wlc-1",
        wlc_host="192.0.2.10",
        ap_name=ap_name,
        ap_host="10.0.0.1",
        filesystem="none",
        mount="/tmp",
        size="95.4M",
        used="95.0M",
        available="376.0K",
        used_percent=used_percent,
    )


def test_row_status_flags_full_high_and_ok():
    assert row_status(fs_row(used_percent=100), APFilesystemAuditConfig()) == "FULL"
    assert row_status(fs_row(used_percent=95), APFilesystemAuditConfig()) == "HIGH"
    assert row_status(fs_row(used_percent=94), APFilesystemAuditConfig()) == "OK"


def test_visible_rows_default_shows_only_problem_rows():
    rows = [fs_row("OK", 10), fs_row("FULL", 100)]

    assert [row.ap_name for row in visible_rows(rows, APFilesystemAuditConfig())] == ["FULL"]


def test_visible_rows_all_includes_ok_rows():
    rows = [fs_row("OK", 10), fs_row("FULL", 100)]

    assert [row.ap_name for row in visible_rows(rows, APFilesystemAuditConfig(show_all=True))] == [
        "OK",
        "FULL",
    ]


def test_filter_ap_targets_applies_exact_then_wildcard_filters():
    targets = [
        APTarget(wlc_name="wlc-1", wlc_host="192.0.2.10", name="MBY-1", host="10.0.0.1"),
        APTarget(wlc_name="wlc-1", wlc_host="192.0.2.10", name="MBY-TEST", host="10.0.0.2"),
        APTarget(wlc_name="wlc-1", wlc_host="192.0.2.10", name="OTHER-1", host="10.0.0.3"),
    ]

    config = APFilesystemAuditConfig(include=("MBY-*",), exclude=("*TEST",))

    assert [target.name for target in filter_ap_targets(targets, config)] == ["MBY-1"]
    assert [target.name for target in filter_ap_targets(targets, APFilesystemAuditConfig(ap_names=("OTHER-1",)))] == [
        "OTHER-1"
    ]
    assert [target.host for target in filter_ap_targets(targets, APFilesystemAuditConfig(ap_hosts=("10.0.0.2",)))] == [
        "10.0.0.2"
    ]


def test_filter_ap_targets_combines_exact_names_and_hosts_as_union():
    targets = [
        APTarget(wlc_name="wlc-1", wlc_host="192.0.2.10", name="AP-BY-NAME", host="10.0.0.1"),
        APTarget(wlc_name="wlc-1", wlc_host="192.0.2.10", name="AP-BY-HOST", host="10.0.0.2"),
        APTarget(wlc_name="wlc-1", wlc_host="192.0.2.10", name="AP-SKIP", host="10.0.0.3"),
    ]

    filtered = filter_ap_targets(
        targets,
        APFilesystemAuditConfig(ap_names=("AP-BY-NAME",), ap_hosts=("10.0.0.2",)),
    )

    assert [target.name for target in filtered] == ["AP-BY-NAME", "AP-BY-HOST"]
