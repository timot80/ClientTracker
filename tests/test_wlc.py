from ap_radio_monitor.models import WLCConfig
from ap_radio_monitor.wlc import WLCLoadInfoSession


class FakeConnection:
    def __init__(self):
        self.commands = []

    def check_enable_mode(self):
        return True

    def send_command(self, command, **kwargs):
        self.commands.append((command, kwargs))
        return "ok"

    def disconnect(self):
        pass


def test_connect_disables_terminal_paging(monkeypatch):
    fake = FakeConnection()
    monkeypatch.setattr("ap_radio_monitor.wlc.ConnectHandler", lambda **_kwargs: fake)

    session = WLCLoadInfoSession(WLCConfig(host="192.0.2.10", username="u", password="p"))
    session.connect()

    assert fake.commands == [
        ("terminal length 0", {"expect_string": r"#", "read_timeout": 30})
    ]


def test_get_load_info_uses_prompt_pattern_and_long_timeout():
    fake = FakeConnection()
    config = WLCConfig(host="192.0.2.10", username="u", password="p", read_timeout=120)
    session = WLCLoadInfoSession(config)
    session.connection = fake

    output = session.get_load_info()

    assert output == "ok"
    assert fake.commands == [
        ("show ap summary load-info", {"expect_string": r"#", "read_timeout": 120})
    ]


def test_get_admin_down_slots_parses_disabled_and_down_slots():
    class SlotConfigConnection(FakeConnection):
        def send_command(self, command, **kwargs):
            self.commands.append((command, kwargs))
            if command.endswith("slot 0"):
                return """
Attributes for Slot 0
  Administrative State                          : Enabled
  Operation State                               : Up
"""
            if command.endswith("slot 2"):
                return """
Attributes for Slot 2
  Administrative State                          : Disabled
  Operation State                               : Down
"""
            return "No Attributes for the selected slot."

    fake = SlotConfigConnection()
    config = WLCConfig(host="192.0.2.10", username="u", password="p", read_timeout=120)
    session = WLCLoadInfoSession(config)
    session.connection = fake

    assert session.get_admin_down_slots("MBY-EVNT-CNTR_HLWY-22", (0, 2, 3)) == {2}
    assert session.get_admin_down_slots("MBY-EVNT-CNTR_HLWY-22", (0, 2, 3)) == {2}

    slot_commands = [command for command, _kwargs in fake.commands]
    assert slot_commands == [
        "show ap dot11 24ghz summary",
        "show ap dot11 5ghz summary",
        "show ap dot11 6ghz summary",
        "show ap name MBY-EVNT-CNTR_HLWY-22 config slot 0",
        "show ap name MBY-EVNT-CNTR_HLWY-22 config slot 2",
        "show ap name MBY-EVNT-CNTR_HLWY-22 config slot 3",
    ]


def test_get_admin_down_slots_prefers_dot11_summary_over_per_ap_queries():
    class RadioSummaryConnection(FakeConnection):
        def send_command_timing(self, command, **kwargs):
            self.commands.append((command, kwargs))
            if command == "show ap dot11 24ghz summary":
                return """
AP Name                           Mac Address     Slot    Admin State    Oper State    Width    Txpwr           Channel                             Mode
---------------------------------------------------------------------------------------------------------------------------------------------------------
MBY-EVNT-CNTR_HLWY-22             2416.1b75.2f60  0       Enabled        Up            20       *6/8 (8 dBm)    (6)*                                Local
"""
            if command == "show ap dot11 5ghz summary":
                return """
AP Name                           Mac Address     Slot    Admin State    Oper State    Width    Txpwr           Channel                             Mode
---------------------------------------------------------------------------------------------------------------------------------------------------------
MBY-EVNT-CNTR_HLWY-22             2416.1b75.2f60  1       Enabled        Up            20       *2/5 (12 dBm)   (56)*                               Local
MBY-EVNT-CNTR_HLWY-22             2416.1b75.2f60  2       Disabled       Down          20       *1/8 (0 dBm)    (36)*                               Local
"""
            return ""

    fake = RadioSummaryConnection()
    config = WLCConfig(host="192.0.2.10", username="u", password="p", read_timeout=120)
    session = WLCLoadInfoSession(config)
    session.connection = fake

    assert session.get_admin_down_slots("MBY-EVNT-CNTR_HLWY-22", (2,)) == {2}
    assert session.get_admin_down_slots("MBY-EVNT-CNTR_HLWY-22", (2,)) == {2}

    assert [command for command, _kwargs in fake.commands] == [
        "show ap dot11 24ghz summary",
        "show ap dot11 5ghz summary",
        "show ap dot11 6ghz summary",
    ]
