from client_tracker.local import parse_airport_output, parse_netsh_output


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
