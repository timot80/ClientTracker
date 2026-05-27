from ap_radio_monitor.app import collect_once
from ap_radio_monitor.models import APBalanceConfig


class FakeWLC:
    def __init__(self, output):
        self.output = output

    def get_load_info(self):
        return self.output


def test_collect_once_parses_output_from_wlc_session():
    output = """
AP Name                           Radio Mac       Slots  Clients       Slot0                   Slot1
                                                                Clients  Utilisation(%)  Clients  Utilisation(%)
-----------------------------------------------------------------------------------------------------
NOC-AP-1                          0c75.bdb5.6380   2      51      1        5               50       80
"""
    snapshot = collect_once(FakeWLC(output), APBalanceConfig())

    assert snapshot.ap_loads[0].name == "NOC-AP-1"
    assert snapshot.ap_loads[0].total_clients == 51
