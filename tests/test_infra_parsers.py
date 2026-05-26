from client_tracker.infra import APSessionPool, WLCSession


def test_parse_client_detail_preserves_multi_word_ssid():
    output = """
Client MAC Address : aabb.ccdd.eeff
AP Name : AP-9166-1
Wireless LAN Network Name (SSID) : Corp Guest WiFi
Protocol : 802.11ax - 5 GHz
Policy Manager State : Run
Radio Signal Strength Indicator : -42 dBm
Signal to Noise Ratio : 38 dB
"""
    state = WLCSession.parse_client_detail(output, "aa:bb:cc:dd:ee:ff")

    assert state.ap_name == "AP-9166-1"
    assert state.ssid == "Corp Guest WiFi"
    assert state.protocol == "802.11ax - 5 GHz"
    assert state.state == "Run"
    assert state.rssi == "-42"
    assert state.snr == "38"


def test_parse_dot11_clients_preserves_multi_word_ssid():
    output = """
MAC Address     SlotID WLANID AID  WLAN Name       RSSI  Maxrate is_wgb_wired is_mld_sta
aabb.ccdd.eeff  1      17     36   Corp Guest WiFi -51   MCS92SS false        false
"""
    state = APSessionPool.parse_dot11_clients(
        output, "aa:bb:cc:dd:ee:ff", "AP-9166-1"
    )

    assert state.ap_name == "AP-9166-1"
    assert state.channel == "36"
    assert state.ssid == "Corp Guest WiFi"
    assert state.rssi == "-51"
    assert state.mcs_rate == "MCS92SS"
