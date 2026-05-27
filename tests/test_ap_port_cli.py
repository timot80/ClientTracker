from unittest.mock import Mock, patch

from ap_port_audit.cli import main, parse_args
from ap_port_audit.models import APPortAuditConfig


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


def test_main_loads_config_applies_overrides_and_runs_once():
    loaded = Mock()
    loaded.wlc = Mock()
    loaded.ap_ports = APPortAuditConfig()
    run_once = Mock()

    with (
        patch("ap_port_audit.cli.load_config", return_value=loaded),
        patch("ap_port_audit.cli.run_once", run_once),
    ):
        exit_code = main(["--config", "config.yaml", "--include", "MBY-*", "--all", "--speed-threshold", "2500"])

    assert exit_code == 0
    passed_config = run_once.call_args.args[1]
    assert passed_config.include == ("MBY-*",)
    assert passed_config.show_all is True
    assert passed_config.speed_threshold == 2500
