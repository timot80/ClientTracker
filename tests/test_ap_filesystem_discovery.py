from ap_filesystem_audit.discovery import discover_aps_from_wlc, parse_show_ap_summary
from ap_radio_monitor.models import WLCConfig
from wifiops.wlc_targets import WlcTarget


def test_parse_show_ap_summary_extracts_names_and_ips():
    output = """
AP Name                           Slots AP Model              Ethernet MAC     Radio MAC        Location        Country IP Address
-----------------------------------------------------------------------------------------------------
MBY-AP-1                          2     C9120AXI-B            aaaa.bbbb.cccc   dddd.eeee.ffff   default         US      10.1.2.3
MBY-AP-2                          2     C9120AXI-B            aaaa.bbbb.cccd   dddd.eeee.fff0   default         US      10.1.2.4
"""

    aps = parse_show_ap_summary(output, WlcTarget("wlc-1", WLCConfig(host="192.0.2.10", username="u", password="p")))

    assert [(ap.name, ap.host, ap.wlc_name) for ap in aps] == [
        ("MBY-AP-1", "10.1.2.3", "wlc-1"),
        ("MBY-AP-2", "10.1.2.4", "wlc-1"),
    ]


def test_discover_aps_from_wlc_runs_show_ap_summary(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.commands = []

        def check_enable_mode(self):
            return True

        def send_command(self, command, **kwargs):
            self.commands.append((command, kwargs))
            if command == "terminal length 0":
                return ""
            return "MBY-AP-1 2 model mac radio loc US 10.1.2.3"

        def disconnect(self):
            pass

    fake = FakeConnection()
    monkeypatch.setattr("ap_filesystem_audit.discovery.ConnectHandler", lambda **_kwargs: fake)

    aps = discover_aps_from_wlc(WlcTarget("wlc-1", WLCConfig(host="192.0.2.10", username="u", password="p")))

    assert aps[0].name == "MBY-AP-1"
    assert fake.commands[0][0] == "terminal length 0"
    assert fake.commands[1][0] == "show ap summary"
