from unittest.mock import Mock, patch
from types import SimpleNamespace

from ap_port_audit.cli import main, parse_args
from ap_port_audit.models import APPortAuditConfig, APPortConfig
from ap_radio_monitor.models import WLCConfig
from wifiops.wlc_targets import WlcTarget


def test_parse_args_supports_audit_options():
    args = parse_args(
        [
            "--config",
            "lab.yaml",
            "--include",
            "MBY-*",
            "--exclude",
            "*TEST*",
            "--all",
            "--speed-threshold",
            "2500",
        ]
    )

    assert args.config == "lab.yaml"
    assert args.include == ["MBY-*"]
    assert args.exclude == ["*TEST*"]
    assert args.all is True
    assert args.speed_threshold == 2500


def test_parse_args_supports_wlc_selection_and_concurrency():
    args = parse_args(["--wlc", "mby-1", "--wlc", "mby-2", "--wlc-concurrency", "5"])

    assert args.wlc == ["mby-1", "mby-2"]
    assert args.wlc_concurrency == 5


def test_main_loads_config_applies_overrides_and_runs_multi():
    loaded = Mock()
    loaded.wlc_targets = [Mock(name="default", config=Mock())]
    loaded.ap_ports = APPortAuditConfig()
    loaded.wlc_concurrency = 3
    run_multi = Mock(return_value=0)

    with (
        patch("ap_port_audit.cli.load_config", return_value=loaded),
        patch("ap_port_audit.cli.run_multi", run_multi),
    ):
        exit_code = main(["--config", "config.yaml", "--include", "MBY-*", "--all", "--speed-threshold", "2500"])

    assert exit_code == 0
    passed_config = run_multi.call_args.args[1]
    assert passed_config.include == ("MBY-*",)
    assert passed_config.show_all is True
    assert passed_config.speed_threshold == 2500


def test_main_selects_wlcs_and_overrides_concurrency():
    loaded = Mock()
    loaded.wlc_targets = [
        SimpleNamespace(name="mby-1", config=Mock()),
        SimpleNamespace(name="mby-2", config=Mock()),
    ]
    loaded.ap_ports = APPortAuditConfig()
    loaded.wlc_concurrency = 3
    run_multi = Mock(return_value=0)

    with (
        patch("ap_port_audit.cli.load_config", return_value=loaded),
        patch("ap_port_audit.cli.run_multi", run_multi),
    ):
        exit_code = main(["--config", "config.yaml", "--wlc", "mby-2", "--wlc-concurrency", "5"])

    assert exit_code == 0
    assert [target.name for target in run_multi.call_args.args[0]] == ["mby-2"]
    assert run_multi.call_args.args[2] == 5


def test_main_returns_nonzero_for_wlc_command_failure(monkeypatch):
    class FailingSession:
        def __init__(self, _config):
            pass

        def connect(self):
            pass

        def get_ethernet_statistics(self):
            raise RuntimeError("command failed")

        def disconnect(self):
            pass

    config = APPortConfig(
        wlc_targets=[WlcTarget("default", WLCConfig(host="192.0.2.10", username="u", password="p"))],
        ap_ports=APPortAuditConfig(),
    )
    monkeypatch.setattr("ap_port_audit.cli.load_config", lambda _path: config)
    monkeypatch.setattr("ap_port_audit.app.APPortAuditSession", FailingSession)

    assert main(["--config", "config.yaml"]) == 1


def test_main_returns_nonzero_for_total_parse_failure(monkeypatch):
    class EmptySession:
        def __init__(self, _config):
            pass

        def connect(self):
            pass

        def get_ethernet_statistics(self):
            return "not AP Ethernet statistics"

        def disconnect(self):
            pass

    config = APPortConfig(
        wlc_targets=[WlcTarget("default", WLCConfig(host="192.0.2.10", username="u", password="p"))],
        ap_ports=APPortAuditConfig(),
    )
    monkeypatch.setattr("ap_port_audit.cli.load_config", lambda _path: config)
    monkeypatch.setattr("ap_port_audit.app.APPortAuditSession", EmptySession)

    assert main(["--config", "config.yaml"]) == 1
