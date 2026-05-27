from ap_radio_monitor import __version__
from ap_radio_monitor.cli import main, parse_args as parse_radio_args

import pytest

from client_tracker.cli import parse_args as parse_client_args


def test_version_import_is_available():
    assert __version__ == "0.1.0"


def test_parse_args_supports_monitor_options():
    args = parse_radio_args(
        [
            "--config",
            "lab.yaml",
            "--refresh",
            "15",
            "--once",
            "--only-imbalanced",
            "--limit",
            "10",
            "--columns",
            "2",
            "--auto-exclude-admin-down-slots",
            "--busy-idle-util",
            "25",
            "--include-slot",
            "1",
            "--exclude-slot",
            "0",
        ]
    )

    assert args.config == "lab.yaml"
    assert args.refresh == 15
    assert args.once is True
    assert args.only_imbalanced is True
    assert args.limit == 10
    assert args.columns == 2
    assert args.auto_exclude_admin_down_slots is True
    assert args.busy_idle_util == 25
    assert args.include_slot == [1]
    assert args.exclude_slot == [0]


def test_parse_args_rejects_conflicting_radio_visibility_options():
    with pytest.raises(SystemExit):
        parse_radio_args(["--only-imbalanced", "--only-problem"])

    with pytest.raises(SystemExit):
        parse_radio_args(["--show-idle", "--hide-idle"])


def test_main_returns_clean_error_for_bad_config(tmp_path, capsys):
    missing = tmp_path / "missing.yaml"

    exit_code = main(["--config", str(missing), "--once"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Config file not found" in captured.err


def test_default_mode_is_infra_when_mac_supplied():
    args = parse_client_args(["aa:bb:cc:dd:ee:ff"])

    assert args.mode == "infra"
    assert args.mac == "aa:bb:cc:dd:ee:ff"


def test_local_mode_does_not_require_mac():
    args = parse_client_args(["--mode", "local"])

    assert args.mode == "local"
    assert args.mac is None


def test_combined_mode_requires_mac():
    with pytest.raises(SystemExit):
        parse_client_args(["--mode", "combined"])


def test_invalid_mac_exits():
    with pytest.raises(SystemExit):
        parse_client_args(["not-a-mac"])


def test_default_intervals_are_mode_specific():
    assert parse_client_args(["--mode", "local"]).interval == 1.0
    assert parse_client_args(["aa:bb:cc:dd:ee:ff"]).interval == 5.0
    assert parse_client_args(["aa:bb:cc:dd:ee:ff", "--mode", "combined"]).interval == 2.0


def test_interval_can_be_overridden():
    args = parse_client_args(["--mode", "local", "--interval", "0.5"])

    assert args.interval == 0.5
