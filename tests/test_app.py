from rich.console import Console

from ap_radio_monitor.app import _render_snapshot, collect_once
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


def test_render_parse_error_panel_includes_output_excerpt():
    snapshot = collect_once_with_error_excerpt("Invalid input detected at '^' marker.")
    console = Console(record=True, width=120)

    console.print(_render_snapshot(snapshot, APBalanceConfig()))
    rendered = console.export_text()

    assert "Could not find supported load-info header" in rendered
    assert "Invalid input detected" in rendered


def collect_once_with_error_excerpt(output):
    from ap_radio_monitor.app import _collect_with_error_handling

    return _collect_with_error_handling(FakeWLC(output), APBalanceConfig())
