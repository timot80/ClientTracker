from ap_port_audit.parser import parse_ethernet_statistics


SAMPLE_OUTPUT = """
AP Name : MBY-CON-SCC1_BAYSIDE_B-51

Interface Name      Status  Speed       Duplex  Rx Packets    Tx Packets    Discarded Packets
------------------------------------------------------------------------------------------------
GigabitEthernet0    UP       5000 Mbps   Full    160345        47098         0

AP Name : MBY-CON-SCC1_BAYSIDE_B-57

Interface Name      Status  Speed       Duplex  Rx Packets    Tx Packets    Discarded Packets
------------------------------------------------------------------------------------------------
GigabitEthernet0    UP       2500 Mbps   Full    6840          1455          0
"""


def test_parse_ethernet_statistics_reads_ap_sections_and_ports():
    snapshot = parse_ethernet_statistics(SAMPLE_OUTPUT)

    assert snapshot.raw_command == "show ap ethernet statistics"
    assert len(snapshot.rows) == 2
    assert snapshot.rows[0].ap_name == "MBY-CON-SCC1_BAYSIDE_B-51"
    assert snapshot.rows[0].interface == "GigabitEthernet0"
    assert snapshot.rows[0].link_status == "UP"
    assert snapshot.rows[0].speed_mbps == 5000
    assert snapshot.rows[0].speed_text == "5000 Mbps"
    assert snapshot.rows[0].duplex == "Full"
    assert snapshot.rows[0].rx_packets == 160345
    assert snapshot.rows[0].tx_packets == 47098
    assert snapshot.rows[0].discarded_packets == 0
    assert snapshot.parser_warnings == []


def test_parse_ethernet_statistics_keeps_unknown_speed_and_duplex():
    output = """
AP Name : TEST-AP

Interface Name      Status  Speed       Duplex  Rx Packets    Tx Packets    Discarded Packets
------------------------------------------------------------------------------------------------
GigabitEthernet0    UP       Unknown     Auto    1             2             3
"""

    snapshot = parse_ethernet_statistics(output)

    assert len(snapshot.rows) == 1
    assert snapshot.rows[0].speed_mbps is None
    assert snapshot.rows[0].speed_text == "Unknown"
    assert snapshot.rows[0].duplex == "Auto"


def test_parse_ethernet_statistics_records_malformed_rows():
    output = """
AP Name : TEST-AP
Interface Name      Status  Speed       Duplex  Rx Packets    Tx Packets    Discarded Packets
------------------------------------------------------------------------------------------------
this is not a valid interface row
"""

    snapshot = parse_ethernet_statistics(output)

    assert snapshot.rows == []
    assert snapshot.parser_warnings
    assert "TEST-AP" in snapshot.parser_warnings[0]
