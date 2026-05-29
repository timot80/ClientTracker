from __future__ import annotations

import json

from wifiops_probe.cli import (
    build_pairing_payload,
    build_parser,
    format_host_port,
    is_loopback_host,
    render_pairing_qr,
    receiver_url_for_host,
)


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


def test_receiver_url_brackets_ipv6_literals():
    assert receiver_url_for_host("2001:db8::10", 8765) == "http://[2001:db8::10]:8765"
    assert receiver_url_for_host("192.0.2.10", 8765) == "http://192.0.2.10:8765"


def test_format_host_port_and_loopback_support_ipv6():
    assert format_host_port("::1", 8765) == "[::1]:8765"
    assert is_loopback_host("::1") is True
    assert is_loopback_host("::") is False


def test_build_pairing_payload_matches_android_contract():
    payload = build_pairing_payload("http://192.0.2.10:8765", "walk_1", "secret")

    assert payload == {
        "receiver_url": "http://192.0.2.10:8765",
        "session_id": "walk_1",
        "token": "secret",
    }


def test_render_pairing_qr_includes_scannable_payload():
    payload = build_pairing_payload("http://192.0.2.10:8765", "walk_1", "secret")
    rendered = render_pairing_qr(payload)

    assert "Scan receiver QR code:" in rendered
    assert json.dumps(payload, sort_keys=True) not in rendered
    assert "██" in rendered or "##" in rendered
