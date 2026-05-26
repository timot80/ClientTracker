import pytest

from client_tracker.cli import parse_args


def test_default_mode_is_infra_when_mac_supplied():
    args = parse_args(["aa:bb:cc:dd:ee:ff"])

    assert args.mode == "infra"
    assert args.mac == "aa:bb:cc:dd:ee:ff"


def test_local_mode_does_not_require_mac():
    args = parse_args(["--mode", "local"])

    assert args.mode == "local"
    assert args.mac is None


def test_combined_mode_requires_mac():
    with pytest.raises(SystemExit):
        parse_args(["--mode", "combined"])


def test_invalid_mac_exits():
    with pytest.raises(SystemExit):
        parse_args(["not-a-mac"])


def test_default_intervals_are_mode_specific():
    assert parse_args(["--mode", "local"]).interval == 1.0
    assert parse_args(["aa:bb:cc:dd:ee:ff"]).interval == 5.0
    assert parse_args(["aa:bb:cc:dd:ee:ff", "--mode", "combined"]).interval == 2.0


def test_interval_can_be_overridden():
    args = parse_args(["--mode", "local", "--interval", "0.5"])

    assert args.interval == 0.5
