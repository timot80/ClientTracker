from rich.console import Console

from ap_filesystem_audit.app import collect_ap_filesystems, run_audit
from ap_filesystem_audit.models import APFilesystemAuditConfig, APCredentials, APTarget
from ap_radio_monitor.models import WLCConfig
from wifiops.wlc_targets import WlcTarget


FILESYSTEM_OUTPUT = """
Filesystem Size Used Available Use% Mounted on
none 95.4M 95.0M 376.0K 100% /tmp
"""

FULL_PART_OUTPUT = """
Filesystem Size Used Available Use% Mounted on
none 95.4M 1.0M 94.4M 1% /tmp
/dev/loop1 18.2M 18.2M 0 100% /part2/app
"""


def test_collect_ap_filesystems_runs_sh_filesystems(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.commands = []

        def check_enable_mode(self):
            return True

        def send_command(self, command, **kwargs):
            self.commands.append((command, kwargs))
            if command == "terminal length 0":
                return ""
            return FILESYSTEM_OUTPUT

        def disconnect(self):
            pass

    fake = FakeConnection()
    monkeypatch.setattr("ap_filesystem_audit.app.ConnectHandler", lambda **_kwargs: fake)
    target = APTarget("wlc-1", "192.0.2.10", "AP-1", "10.1.2.3")

    snapshot = collect_ap_filesystems(target, APCredentials("u", "p"), APFilesystemAuditConfig())

    assert snapshot.rows[0].ap_name == "AP-1"
    assert snapshot.rows[0].mount == "/tmp"
    assert fake.commands[-1][0] == "sh filesystems"


def test_collect_ap_filesystems_reports_empty_parse_as_failure(monkeypatch):
    class FakeConnection:
        def send_command(self, command, **_kwargs):
            if command == "terminal length 0":
                return ""
            return "unexpected output\nbad row\n"

        def disconnect(self):
            pass

    monkeypatch.setattr("ap_filesystem_audit.app.ConnectHandler", lambda **_kwargs: FakeConnection())
    target = APTarget("wlc-1", "192.0.2.10", "AP-1", "10.1.2.3")

    snapshot = collect_ap_filesystems(target, APCredentials("u", "p"), APFilesystemAuditConfig())

    assert snapshot.rows == []
    assert snapshot.failures
    assert snapshot.failures[0].ap_name == "AP-1"
    assert "no filesystem rows parsed" in snapshot.failures[0].message


def test_collect_ap_filesystems_reloads_when_tmp_is_full(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.calls = []

        def send_command(self, command, **_kwargs):
            self.calls.append(("send_command", command))
            if command == "terminal length 0":
                return ""
            return FILESYSTEM_OUTPUT

        def send_command_timing(self, command, **_kwargs):
            self.calls.append(("send_command_timing", command))
            if command == "reload":
                return "Proceed with reload? [confirm]"
            return ""

        def write_channel(self, value):
            self.calls.append(("write_channel", value))

        def read_channel(self):
            self.calls.append(("read_channel", ""))
            return "cli: AP Rebooting: CLI triggered reboot(reload command)"

        def disconnect(self):
            pass

    fake = FakeConnection()
    monkeypatch.setattr("ap_filesystem_audit.app.ConnectHandler", lambda **_kwargs: fake)
    target = APTarget("wlc-1", "192.0.2.10", "AP-1", "10.1.2.3")

    snapshot = collect_ap_filesystems(
        target,
        APCredentials("u", "p"),
        APFilesystemAuditConfig(reload_full_tmp=True, confirm_reload_full_tmp=True),
    )

    assert snapshot.failures == []
    assert len(snapshot.reload_results) == 1
    assert snapshot.reload_results[0].action == "triggered"
    assert ("send_command_timing", "reload") in fake.calls
    assert ("write_channel", "\r\n") in fake.calls


def test_collect_ap_filesystems_does_not_reload_when_only_non_tmp_mount_is_full(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.calls = []

        def send_command(self, command, **_kwargs):
            self.calls.append(("send_command", command))
            if command == "terminal length 0":
                return ""
            return FULL_PART_OUTPUT

        def send_command_timing(self, command, **_kwargs):
            self.calls.append(("send_command_timing", command))
            return ""

        def disconnect(self):
            pass

    fake = FakeConnection()
    monkeypatch.setattr("ap_filesystem_audit.app.ConnectHandler", lambda **_kwargs: fake)
    target = APTarget("wlc-1", "192.0.2.10", "AP-1", "10.1.2.3")

    snapshot = collect_ap_filesystems(
        target,
        APCredentials("u", "p"),
        APFilesystemAuditConfig(reload_full_tmp=True, confirm_reload_full_tmp=True),
    )

    assert snapshot.failures == []
    assert snapshot.reload_results == []
    assert ("send_command_timing", "reload") not in fake.calls


def test_collect_ap_filesystems_records_reload_failure_when_confirmation_missing(monkeypatch):
    class FakeConnection:
        def send_command(self, command, **_kwargs):
            if command == "terminal length 0":
                return ""
            return FILESYSTEM_OUTPUT

        def send_command_timing(self, command, **_kwargs):
            assert command == "reload"
            return "reload rejected"

        def disconnect(self):
            pass

    monkeypatch.setattr("ap_filesystem_audit.app.ConnectHandler", lambda **_kwargs: FakeConnection())
    target = APTarget("wlc-1", "192.0.2.10", "AP-1", "10.1.2.3")

    snapshot = collect_ap_filesystems(
        target,
        APCredentials("u", "p"),
        APFilesystemAuditConfig(reload_full_tmp=True, confirm_reload_full_tmp=True),
    )

    assert len(snapshot.reload_results) == 1
    assert snapshot.reload_results[0].action == "failed"
    assert snapshot.failures
    assert "confirmation prompt not received" in snapshot.failures[0].message


def test_collect_ap_filesystems_records_reload_failure_without_reboot_evidence(monkeypatch):
    class FakeConnection:
        def send_command(self, command, **_kwargs):
            if command == "terminal length 0":
                return ""
            return FILESYSTEM_OUTPUT

        def send_command_timing(self, command, **_kwargs):
            assert command == "reload"
            return "Proceed with reload? [confirm]"

        def write_channel(self, _value):
            pass

        def read_channel(self):
            return ""

        def disconnect(self):
            pass

    monkeypatch.setattr("ap_filesystem_audit.app.ConnectHandler", lambda **_kwargs: FakeConnection())
    monkeypatch.setattr("ap_filesystem_audit.app.time.sleep", lambda _seconds: None)
    target = APTarget("wlc-1", "192.0.2.10", "AP-1", "10.1.2.3")

    snapshot = collect_ap_filesystems(
        target,
        APCredentials("u", "p"),
        APFilesystemAuditConfig(reload_full_tmp=True, confirm_reload_full_tmp=True),
    )

    assert len(snapshot.reload_results) == 1
    assert snapshot.reload_results[0].action == "failed"
    assert snapshot.failures
    assert "no reboot evidence" in snapshot.failures[0].message


def test_run_audit_renders_failures_and_returns_nonzero(monkeypatch):
    def fake_discover(_target):
        return [APTarget("wlc-1", "192.0.2.10", "AP-1", "10.1.2.3")]

    def fake_collect(_ap, _creds, _config):
        raise RuntimeError("ssh failed")

    monkeypatch.setattr("ap_filesystem_audit.app.discover_aps_from_wlc", fake_discover)
    monkeypatch.setattr("ap_filesystem_audit.app.collect_ap_filesystems", fake_collect)
    console = Console(record=True, width=160)

    exit_code = run_audit(
        [WlcTarget("wlc-1", WLCConfig(host="192.0.2.10", username="u", password="p"))],
        APCredentials("ap-u", "ap-p"),
        APFilesystemAuditConfig(),
        wlc_concurrency=1,
        console=console,
    )

    rendered = console.export_text()
    assert exit_code == 1
    assert "AP-1" in rendered
    assert "ssh failed" in rendered
