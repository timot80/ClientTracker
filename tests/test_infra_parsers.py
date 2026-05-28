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


def test_parse_ap_config_general_ip_prefers_ap_ip_address():
    output = """
IP Address Configuration                        : DHCP
IP Address                                      : 10.2.202.37
IP Netmask                                      : 255.255.255.128
Gateway IP Address                              : 10.2.202.1
Primary Cisco Controller IP Address             : 10.23.76.81
Secondary Cisco Controller IP Address           : 10.23.76.93
NAT External IP Address                         : 10.2.202.37
"""

    assert WLCSession.parse_ap_config_general_ip(output) == "10.2.202.37"


def test_parse_ap_summary_ip_fallback_extracts_matching_ap_row():
    output = """
AP Name                           Slots AP Model              Ethernet MAC     Radio MAC        Location        Country IP Address
--------------------------------------------------------------------------------------------------------------------------------
OTHER-AP                          3     C9166I-B              aaaa.bbbb.cccc   dddd.eeee.ffff   default         US      10.1.2.11
MBY-CON-SCC1_BAYSIDE_D-32         3     C9166I-B              1111.2222.3333   4444.5555.6666   default         US      10.2.202.37
"""

    assert WLCSession.parse_ap_summary_ip(output, "MBY-CON-SCC1_BAYSIDE_D-32") == "10.2.202.37"


def test_parse_dot11_clients_preserves_multi_word_ssid():
    output = """
MAC Address     SlotID WLANID AID  WLAN Name       RSSI  Maxrate is_wgb_wired is_mld_sta
aabb.ccdd.eeff  1      17     36   Corp Guest WiFi -51   MCS92SS false        false
"""
    state = APSessionPool.parse_dot11_clients(
        output, "aa:bb:cc:dd:ee:ff", "AP-9166-1"
    )

    assert state.ap_name == "AP-9166-1"
    assert state.channel == ""
    assert state.slot_id == "1"
    assert state.ssid == "Corp Guest WiFi"
    assert state.rssi == "-51"
    assert state.mcs_rate == "MCS92SS"


def test_parse_dot11_clients_does_not_treat_aid_as_channel():
    output = """
       Client MAC Slot ID WLAN ID AID         WLAN Name RSSI  Maxrate is_wgb_wired
9A:ED:EE:EF:CE:E9       1       1  12          DarkStar  -61 MCS112SS           No
"""

    state = APSessionPool.parse_dot11_clients(
        output, "9a:ed:ee:ef:ce:e9", "MBY-CON-SCC1_BAYSIDE_D-32"
    )

    assert state.channel == ""
    assert state.slot_id == "1"
    assert state.rssi == "-61"
    assert state.mcs_rate == "MCS112SS"
