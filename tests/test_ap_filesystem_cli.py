from unittest.mock import Mock, patch

from ap_filesystem_audit.cli import main, parse_args
from ap_filesystem_audit.models import APFilesystemAuditConfig, APCredentials


def test_parse_args_supports_filesystem_options():
    args = parse_args(
        [
            "--config",
            "config.yaml",
            "--wlc",
            "wlc-1",
            "--include",
            "MBY-*",
            "--exclude",
            "*TEST*",
            "--ap-name",
            "AP-1",
            "--ap-host",
            "10.1.2.3",
            "--min-used-percent",
            "90",
            "--all",
            "--wlc-concurrency",
            "4",
            "--ap-concurrency",
            "10",
            "--output",
            "out.csv",
        ]
    )

    assert args.wlc == ["wlc-1"]
    assert args.include == ["MBY-*"]
    assert args.exclude == ["*TEST*"]
    assert args.ap_name == ["AP-1"]
    assert args.ap_host == ["10.1.2.3"]
    assert args.min_used_percent == 90
    assert args.all is True
    assert args.wlc_concurrency == 4
    assert args.ap_concurrency == 10
    assert args.output == "out.csv"


def test_main_loads_config_applies_overrides_and_runs_audit():
    loaded = Mock()
    loaded.wlc_targets = [Mock(name="wlc-1")]
    loaded.ap_credentials = APCredentials("u", "p")
    loaded.audit = APFilesystemAuditConfig()
    loaded.wlc_concurrency = 3
    run_audit = Mock(return_value=0)

    with (
        patch("ap_filesystem_audit.cli.load_config", return_value=loaded),
        patch("ap_filesystem_audit.cli.run_audit", run_audit),
    ):
        assert main(["--config", "config.yaml", "--include", "MBY-*", "--output", "out.csv"]) == 0

    passed_config = run_audit.call_args.args[2]
    assert passed_config.include == ("MBY-*",)
    assert passed_config.output == "out.csv"
