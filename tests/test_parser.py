import pytest

from ap_radio_monitor.parser import LoadInfoParseError, parse_load_info


OBSERVED_OUTPUT = """
NOC-MBY-SSO-1#sh ap summary load-info
Load for five secs: 1%/0%; one minute: 2%; five minutes: 2%
Time source is NTP, 16:06:31.133 PDT Tue May 26 2026

AP Name                           Radio Mac       Slots  Clients       Slot0                   Slot1                   Slot2                   Slot3
                                                                Clients  Utilisation(%)  Clients  Utilisation(%)  Clients  Utilisation(%)  Clients  Utilisation(%)
---------------------------------------------------------------------------------------------------------------------------------------------------------------------

NOC-AP-MBY-1                      0c75.bdb5.6380   3      2       0        43              1        3               1        8               NA       NA
"""


DOCUMENTED_OUTPUT = """
WTP-Mac         AP-Name          Tot-Slots Tot-Clients  Slot0                  Slot1                   Slot2
                                                        Clients Utilisation(%) Clients Utilisation(%)  Clients Utilisation(%)
---------------------------------------------------------------------------------------------------------------
0c75.bdb5.6380  NOC-AP-MBY-1     3         2            0       43             1       3               1       8
"""


def test_parse_observed_ap_name_first_output():
    snapshot = parse_load_info(OBSERVED_OUTPUT)

    ap = snapshot.ap_loads[0]
    assert ap.name == "NOC-AP-MBY-1"
    assert ap.radio_mac == "0c75.bdb5.6380"
    assert ap.identity_label == "Radio Mac"
    assert ap.slots == 3
    assert ap.total_clients == 2
    assert [(slot.slot, slot.clients, slot.utilization) for slot in ap.slot_loads] == [
        (0, 0, 43),
        (1, 1, 3),
        (2, 1, 8),
        (3, None, None),
    ]


def test_parse_documented_wtp_mac_first_output():
    snapshot = parse_load_info(DOCUMENTED_OUTPUT)

    ap = snapshot.ap_loads[0]
    assert ap.name == "NOC-AP-MBY-1"
    assert ap.radio_mac == "0c75.bdb5.6380"
    assert ap.identity_label == "WTP-Mac"
    assert ap.total_clients == 2
    assert [(slot.slot, slot.clients, slot.utilization) for slot in ap.slot_loads] == [
        (0, 0, 43),
        (1, 1, 3),
        (2, 1, 8),
    ]


def test_parse_keeps_wlc_total_without_warning_when_slot_sum_differs():
    output = OBSERVED_OUTPUT.replace("   3      2       0", "   3      1       0")
    snapshot = parse_load_info(output)

    assert snapshot.ap_loads[0].total_clients == 1
    assert [slot.clients for slot in snapshot.ap_loads[0].slot_loads] == [0, 1, 1, None]
    assert snapshot.ap_loads[0].warnings == []
    assert snapshot.parser_warnings == []


def test_parse_skips_malformed_rows_but_keeps_valid_rows():
    output = OBSERVED_OUTPUT + "\nthis row is not valid\n"
    snapshot = parse_load_info(output)

    assert len(snapshot.ap_loads) == 1
    assert snapshot.parser_warnings


def test_parse_raises_for_unsupported_output():
    with pytest.raises(LoadInfoParseError, match="load-info header"):
        parse_load_info("Invalid input detected at '^' marker.")
