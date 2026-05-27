import subprocess
import os

import pytest

from client_tracker.local import LocalTelemetryPoller
from client_tracker.local import default_macos_identity_helper_path
from client_tracker.local import parse_airport_output, parse_identity_helper_output
from client_tracker.local import parse_netsh_output, parse_wdutil_output


def test_parse_airport_output_preserves_multi_word_ssid():
    output = """
     agrCtlRSSI: -55
     agrCtlNoise: -92
           state: running
         lastTxRate: 286
             SSID: Corp Guest WiFi
            BSSID: aa:bb:cc:dd:ee:ff
          channel: 36,80
"""
    state = parse_airport_output(output)

    assert state.ssid == "Corp Guest WiFi"
    assert state.bssid == "aa:bb:cc:dd:ee:ff"
    assert state.channel == "36,80"
    assert state.tx_rate == "286"
    assert state.signal == "-55"
    assert state.noise == "-92"
    assert state.platform == "darwin"


def test_parse_netsh_output_preserves_multi_word_ssid_and_signal():
    output = """
    SSID                   : Corp Guest WiFi
    BSSID                  : aa:bb:cc:dd:ee:ff
    Signal                 : 82%
    Channel                : 36
    Receive rate (Mbps)    : 1201
    Transmit rate (Mbps)   : 960
"""
    state = parse_netsh_output(output)

    assert state.ssid == "Corp Guest WiFi"
    assert state.bssid == "aa:bb:cc:dd:ee:ff"
    assert state.channel == "36"
    assert state.rx_rate == "1201"
    assert state.tx_rate == "960"
    assert state.signal == "-59.0 approx dBm"
    assert state.platform == "win32"


def test_parse_wdutil_output_preserves_roam_fields():
    output = """
    SSID                 : Corp Guest WiFi
    BSSID                : aa:bb:cc:dd:ee:ff
    Channel              : 36
    RSSI                 : -61 dBm
    Noise                : -92 dBm
    Tx Rate              : 1201 Mbps
    Security             : WPA3 Enterprise
    PHY Mode             : 11ax
    MCS Index            : 11
    Guard Interval       : 800
    NSS                  : 2
    CCA                  : 43 %
    Country Code         : US
    Interface Name       : en0
    IPv4 Address         : 10.23.4.156
    IPv4 Router          : 10.23.4.1
"""
    state = parse_wdutil_output(output)

    assert state.ssid == "Corp Guest WiFi"
    assert state.bssid == "aa:bb:cc:dd:ee:ff"
    assert state.channel == "36"
    assert state.signal == "-61"
    assert state.noise == "-92"
    assert state.tx_rate == "1201"
    assert state.security == "WPA3 Enterprise"
    assert state.phy_mode == "11ax"
    assert state.mcs_index == "11"
    assert state.guard_interval == "800"
    assert state.nss == "2"
    assert state.cca == "43"
    assert state.country_code == "US"
    assert state.interface_name == "en0"
    assert state.ipv4_address == "10.23.4.156"
    assert state.ipv4_router == "10.23.4.1"
    assert state.platform == "darwin"


def test_parse_wdutil_output_ignores_awdl_section():
    output = """
————————————————————————————————————————————————————————————————————
WIFI
————————————————————————————————————————————————————————————————————
    Interface Name       : en0
    SSID                 : Corp Guest WiFi
    BSSID                : aa:bb:cc:dd:ee:ff
    Channel              : 5g153/20
    RSSI                 : -64 dBm
————————————————————————————————————————————————————————————————————
AWDL
————————————————————————————————————————————————————————————————————
    Interface Name       : awdl0
    Channel Sequence     : 153++ 0 149++ 0
"""
    state = parse_wdutil_output(output)

    assert state.interface_name == "en0"
    assert state.channel == "5g153/20"


def test_parse_identity_helper_output_reads_ssid_bssid():
    ssid, bssid = parse_identity_helper_output(
        '{"interface":"en0","ssid":"Corp Guest WiFi","bssid":"aa:bb:cc:dd:ee:ff"}'
    )

    assert ssid == "Corp Guest WiFi"
    assert bssid == "aa:bb:cc:dd:ee:ff"


def test_parse_identity_helper_output_ignores_failed_sentinel_values():
    ssid, bssid = parse_identity_helper_output(
        '{"ssid":"failed to retrieve SSID","bssid":"failed to retrieve BSSID"}'
    )

    assert ssid == ""
    assert bssid == ""


def test_macos_poller_enriches_redacted_wdutil_with_identity_helper(monkeypatch):
    calls = []

    def fake_check_output(argv, timeout, **_kwargs):
        calls.append(argv)
        if argv == ["sudo", "-n", "wdutil", "info"]:
            return b"""
WIFI
    Interface Name       : en0
    SSID                 : <redacted>
    BSSID                : <redacted>
    RSSI                 : -61 dBm
"""
        if argv == ["/Users/test/Applications/wifi-unredactor.app/Contents/MacOS/wifi-unredactor"]:
            return b'{"interface":"en0","ssid":"Corp Guest WiFi","bssid":"aa:bb:cc:dd:ee:ff"}'
        raise AssertionError(f"unexpected command: {argv}")

    monkeypatch.setattr("subprocess.check_output", fake_check_output)

    state = LocalTelemetryPoller(
        platform="darwin",
        identity_helper_path="/Users/test/Applications/wifi-unredactor.app/Contents/MacOS/wifi-unredactor",
    ).poll()

    assert state.ssid == "Corp Guest WiFi"
    assert state.bssid == "aa:bb:cc:dd:ee:ff"
    assert state.signal == "-61"


def test_macos_poller_auto_detects_repo_owned_identity_helper(tmp_path, monkeypatch):
    output_path = tmp_path / "helper-output.json"
    helper = (
        tmp_path
        / "Applications"
        / "client-tracker-wifi-identity.app"
        / "Contents"
        / "MacOS"
        / "client-tracker-wifi-identity"
    )
    helper.parent.mkdir(parents=True)
    helper.write_text("#!/bin/sh\n", encoding="utf-8")
    calls = []

    def fake_check_output(argv, timeout, **_kwargs):
        calls.append(argv)
        if argv == ["sudo", "-n", "wdutil", "info"]:
            return b"""
WIFI
    Interface Name       : en0
    SSID                 : <redacted>
    BSSID                : <redacted>
    RSSI                 : -61 dBm
"""
        if argv == [
            "open",
            "-W",
            "-n",
            str(helper.parents[2]),
            "--args",
            "--output",
            str(output_path),
        ]:
            output_path.write_text(
                '{"interface":"en0","ssid":"Corp Guest WiFi","bssid":"aa:bb:cc:dd:ee:ff"}',
                encoding="utf-8",
            )
            return b""
        raise AssertionError(f"unexpected command: {argv}")

    class FakeTempFile:
        name = str(output_path)

        def close(self):
            return None

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("subprocess.check_output", fake_check_output)
    monkeypatch.setattr("tempfile.NamedTemporaryFile", lambda **_kwargs: FakeTempFile())

    state = LocalTelemetryPoller(platform="darwin").poll()

    assert default_macos_identity_helper_path() == str(helper)
    assert state.ssid == "Corp Guest WiFi"
    assert state.bssid == "aa:bb:cc:dd:ee:ff"


def test_sudo_run_invokes_identity_helper_as_original_user(monkeypatch):
    calls = []

    def fake_check_output(argv, timeout, **_kwargs):
        calls.append(argv)
        if argv == ["sudo", "-n", "wdutil", "info"]:
            return b"""
WIFI
    SSID                 : <redacted>
    BSSID                : <redacted>
"""
        if argv == [
            "sudo",
            "-n",
            "-u",
            "timotbar",
            "/Users/test/Applications/wifi-unredactor.app/Contents/MacOS/wifi-unredactor",
        ]:
            return b'{"ssid":"Corp Guest WiFi","bssid":"aa:bb:cc:dd:ee:ff"}'
        raise AssertionError(f"unexpected command: {argv}")

    monkeypatch.setattr("subprocess.check_output", fake_check_output)
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setenv("SUDO_USER", "timotbar")

    state = LocalTelemetryPoller(
        platform="darwin",
        identity_helper_path="/Users/test/Applications/wifi-unredactor.app/Contents/MacOS/wifi-unredactor",
    ).poll()

    assert state.ssid == "Corp Guest WiFi"
    assert state.bssid == "aa:bb:cc:dd:ee:ff"


def test_sudo_run_invokes_default_identity_helper_app_as_original_user(tmp_path, monkeypatch):
    output_path = tmp_path / "helper-output.json"
    helper = (
        tmp_path
        / "Applications"
        / "client-tracker-wifi-identity.app"
        / "Contents"
        / "MacOS"
        / "client-tracker-wifi-identity"
    )
    helper.parent.mkdir(parents=True)
    helper.write_text("#!/bin/sh\n", encoding="utf-8")
    calls = []
    chown_calls = []
    chmod_calls = []

    class UserInfo:
        pw_uid = 501
        pw_gid = 20

    class FakeTempFile:
        name = str(output_path)

        def close(self):
            return None

    def fake_named_temporary_file(**kwargs):
        assert kwargs["dir"] == "/tmp"
        output_path.write_text("", encoding="utf-8")
        return FakeTempFile()

    def fake_check_output(argv, timeout, **_kwargs):
        calls.append(argv)
        if argv == ["sudo", "-n", "wdutil", "info"]:
            return b"""
WIFI
    SSID                 : <redacted>
    BSSID                : <redacted>
"""
        if argv == [
            "sudo",
            "-n",
            "-u",
            "timotbar",
            "open",
            "-W",
            "-n",
            str(helper.parents[2]),
            "--args",
            "--output",
            str(output_path),
        ]:
            output_path.write_text(
                '{"ssid":"Corp Guest WiFi","bssid":"aa:bb:cc:dd:ee:ff"}',
                encoding="utf-8",
            )
            return b""
        raise AssertionError(f"unexpected command: {argv}")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SUDO_USER", "timotbar")
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr("pwd.getpwnam", lambda username: UserInfo())
    monkeypatch.setattr("os.chown", lambda path, uid, gid: chown_calls.append((path, uid, gid)))
    monkeypatch.setattr("os.chmod", lambda path, mode: chmod_calls.append((path, mode)))
    monkeypatch.setattr("tempfile.NamedTemporaryFile", fake_named_temporary_file)
    monkeypatch.setattr("subprocess.check_output", fake_check_output)

    state = LocalTelemetryPoller(platform="darwin").poll()

    assert state.ssid == "Corp Guest WiFi"
    assert state.bssid == "aa:bb:cc:dd:ee:ff"
    assert chown_calls == [(str(output_path), 501, 20)]
    assert chmod_calls == [(str(output_path), 0o600)]


def test_identity_helper_path_must_be_absolute():
    state = parse_wdutil_output(
        """
WIFI
    SSID                 : <redacted>
    BSSID                : <redacted>
"""
    )
    poller = LocalTelemetryPoller(
        platform="darwin",
        identity_helper_path="wifi-unredactor",
    )

    with pytest.raises(RuntimeError, match="absolute path"):
        poller._enrich_identity(state)


def test_macos_poller_uses_sudo_wdutil_by_default(monkeypatch):
    calls = []

    def fake_check_output(argv, timeout, **_kwargs):
        calls.append(argv)
        if argv == ["sudo", "-n", "wdutil", "info"]:
            return b"""
SSID                 : Corp Guest WiFi
BSSID                : aa:bb:cc:dd:ee:ff
Channel              : 36
RSSI                 : -61 dBm
"""
        raise AssertionError(f"unexpected command: {argv}")

    monkeypatch.setattr("subprocess.check_output", fake_check_output)

    state = LocalTelemetryPoller(platform="darwin").poll()

    assert calls[0] == ["sudo", "-n", "wdutil", "info"]
    assert state.ssid == "Corp Guest WiFi"
    assert state.bssid == "aa:bb:cc:dd:ee:ff"
    assert state.channel == "36"
    assert state.signal == "-61"


def test_macos_poller_requires_sudo_when_wdutil_cannot_run(monkeypatch):
    calls = []

    def fake_check_output(argv, timeout, **_kwargs):
        calls.append(argv)
        if argv == ["sudo", "-n", "wdutil", "info"]:
            raise subprocess.CalledProcessError(1, argv, b"sudo: a password is required")
        raise AssertionError(f"unexpected command: {argv}")

    monkeypatch.setattr("subprocess.check_output", fake_check_output)

    with pytest.raises(RuntimeError, match="requires sudo"):
        LocalTelemetryPoller(platform="darwin").poll()

    assert calls[0] == ["sudo", "-n", "wdutil", "info"]
