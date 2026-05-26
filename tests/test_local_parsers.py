import subprocess

from client_tracker.local import LocalTelemetryPoller
from client_tracker.local import parse_airport_output, parse_netsh_output, parse_wdutil_output


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
"""
    state = parse_wdutil_output(output)

    assert state.ssid == "Corp Guest WiFi"
    assert state.bssid == "aa:bb:cc:dd:ee:ff"
    assert state.channel == "36"
    assert state.signal == "-61"
    assert state.noise == "-92"
    assert state.tx_rate == "1201"
    assert state.platform == "darwin"


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


def test_macos_poller_falls_back_when_wdutil_and_airport_are_unavailable(monkeypatch):
    calls = []

    def fake_check_output(argv, timeout, **_kwargs):
        calls.append(argv)
        if argv == ["sudo", "-n", "wdutil", "info"]:
            raise subprocess.CalledProcessError(1, argv, b"sudo: a password is required")
        if argv[0].endswith("/airport"):
            raise FileNotFoundError(argv[0])
        if argv == ["networksetup", "-getairportnetwork", "en0"]:
            return b"Current Wi-Fi Network: Corp Guest WiFi\n"
        if argv == ["system_profiler", "SPAirPortDataType", "-detailLevel", "mini"]:
            return b"""
Wi-Fi:
  Interfaces:
    en0:
      MAC Address: 7a:42:25:0f:94:66
      Status: Connected
"""
        raise AssertionError(f"unexpected command: {argv}")

    monkeypatch.setattr("subprocess.check_output", fake_check_output)

    state = LocalTelemetryPoller(platform="darwin").poll()

    assert calls[0] == ["sudo", "-n", "wdutil", "info"]
    assert state.platform == "darwin"
    assert state.ssid == "Corp Guest WiFi"
    assert state.bssid == ""
    assert state.ping_status == "Status: Connected"
