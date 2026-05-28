import csv

import ap_filesystem_audit_standalone as standalone


def test_standalone_loads_yaml_config(tmp_path):
    path = tmp_path / "filesystems.yaml"
    path.write_text(
        """
wifiops:
  wlc_concurrency: 2
wlcs:
  - name: wlc-1
    host: 192.0.2.10
    username: wlc-user
    password: wlc-pass
    enable: wlc-enable
ap:
  username: ap-user
  password: ap-pass
  enable: ap-enable
ap_filesystems:
  include: ["MBY-*"]
  exclude: ["*-TEST"]
  min_used_percent: 90
  show_all: true
  ap_concurrency: 7
""",
        encoding="utf-8",
    )

    config = standalone.load_config(path)

    assert config.wlc_targets[0].name == "wlc-1"
    assert config.wlc_targets[0].config.host == "192.0.2.10"
    assert config.wlc_targets[0].config.username == "wlc-user"
    assert config.ap_credentials.username == "ap-user"
    assert config.ap_credentials.enable == "ap-enable"
    assert config.audit.include == ("MBY-*",)
    assert config.audit.exclude == ("*-TEST",)
    assert config.audit.min_used_percent == 90
    assert config.audit.show_all is True
    assert config.audit.ap_concurrency == 7
    assert config.wlc_concurrency == 2


def test_standalone_parse_filesystems_reads_tmp_full_row():
    snapshot = standalone.parse_filesystems(
        """
AP#sh filesystems
Filesystem Size Used Available Use% Mounted on
none 95.4M 95.0M 376.0K 100% /tmp
AP#
"""
    )

    assert len(snapshot.rows) == 1
    assert snapshot.rows[0].mount == "/tmp"
    assert snapshot.rows[0].used_percent == 100
    assert snapshot.parser_warnings == []


def test_standalone_collect_reloads_only_when_tmp_is_full(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.calls = []

        def send_command(self, command, **_kwargs):
            self.calls.append(("send_command", command))
            if command == "terminal length 0":
                return ""
            return """
Filesystem Size Used Available Use% Mounted on
none 95.4M 95.0M 376.0K 100% /tmp
"""

        def send_command_timing(self, command, **_kwargs):
            self.calls.append(("send_command_timing", command))
            if command == "reload":
                return "Proceed with reload? [confirm]"
            return "cli: AP Rebooting"

        def disconnect(self):
            pass

    fake = FakeConnection()
    monkeypatch.setattr(standalone, "ConnectHandler", lambda **_kwargs: fake)

    snapshot = standalone.collect_ap_filesystems(
        standalone.APTarget("wlc-1", "192.0.2.10", "AP-1", "10.1.2.3"),
        standalone.APCredentials("u", "p"),
        standalone.APFilesystemAuditConfig(reload_full_tmp=True, confirm_reload_full_tmp=True),
    )

    assert snapshot.failures == []
    assert snapshot.reload_results[0].action == "triggered"
    assert ("send_command_timing", "reload") in fake.calls
    assert ("send_command_timing", "\r") in fake.calls


def test_standalone_collect_does_not_reload_when_non_tmp_mount_is_full(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.calls = []

        def send_command(self, command, **_kwargs):
            self.calls.append(("send_command", command))
            if command == "terminal length 0":
                return ""
            return """
Filesystem Size Used Available Use% Mounted on
none 95.4M 1.0M 94.4M 1% /tmp
/dev/loop1 18.2M 18.2M 0 100% /part2/app
"""

        def send_command_timing(self, command, **_kwargs):
            self.calls.append(("send_command_timing", command))
            return ""

        def disconnect(self):
            pass

    fake = FakeConnection()
    monkeypatch.setattr(standalone, "ConnectHandler", lambda **_kwargs: fake)

    snapshot = standalone.collect_ap_filesystems(
        standalone.APTarget("wlc-1", "192.0.2.10", "AP-1", "10.1.2.3"),
        standalone.APCredentials("u", "p"),
        standalone.APFilesystemAuditConfig(reload_full_tmp=True, confirm_reload_full_tmp=True),
    )

    assert snapshot.failures == []
    assert snapshot.reload_results == []
    assert ("send_command_timing", "reload") not in fake.calls


def test_standalone_write_csv_includes_reload_fields(tmp_path):
    path = tmp_path / "filesystems.csv"
    snapshot = standalone.APFilesystemSnapshot(
        rows=[
            standalone.APFilesystemRow(
                wlc_name="wlc-1",
                wlc_host="192.0.2.10",
                ap_name="AP-1",
                ap_host="10.1.2.3",
                filesystem="none",
                mount="/tmp",
                size="95.4M",
                used="95.0M",
                available="376.0K",
                used_percent=100,
            )
        ],
        reload_results=[
            standalone.APReloadResult(
                wlc_name="wlc-1",
                wlc_host="192.0.2.10",
                ap_name="AP-1",
                ap_host="10.1.2.3",
                action="triggered",
                output="cli: AP Rebooting",
            )
        ],
    )

    standalone.write_csv(path, snapshot, standalone.APFilesystemAuditConfig())

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["reload_action"] == "triggered"
    assert rows[0]["reload_output"] == "cli: AP Rebooting"


def test_standalone_main_requires_reload_confirmation(capsys):
    assert standalone.main(["--config", "missing.yaml", "--reload-full-tmp"]) == 1

    captured = capsys.readouterr()
    assert "--reload-full-tmp requires --confirm-reload-full-tmp" in captured.err
