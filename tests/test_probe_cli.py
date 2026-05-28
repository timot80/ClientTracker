from __future__ import annotations

from wifiops_probe.cli import build_parser


def test_probe_receive_parser_defaults_to_loopback():
    args = build_parser().parse_args(["--pair"])

    assert args.pair is True
    assert args.host == "127.0.0.1"
    assert args.port == 8765
    assert args.advertise_host == ""


def test_probe_receive_parser_accepts_log_and_advertise_host():
    args = build_parser().parse_args(
        ["--pair", "--host", "0.0.0.0", "--advertise-host", "192.0.2.10", "--log", "walk.csv"]
    )

    assert args.host == "0.0.0.0"
    assert args.advertise_host == "192.0.2.10"
    assert args.log == "walk.csv"
