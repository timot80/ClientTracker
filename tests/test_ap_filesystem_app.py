from rich.console import Console

from ap_filesystem_audit.app import collect_ap_filesystems, run_audit
from ap_filesystem_audit.models import APFilesystemAuditConfig, APCredentials, APTarget
from ap_radio_monitor.models import WLCConfig
from wifiops.wlc_targets import WlcTarget


FILESYSTEM_OUTPUT = """
Filesystem Size Used Available Use% Mounted on
none 95.4M 95.0M 376.0K 100% /tmp
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
