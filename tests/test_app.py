from rich.console import Console

from ap_radio_monitor.app import StartupReporter, _render_snapshot, collect_once, run_once
from ap_radio_monitor.models import APBalanceConfig


class FakeWLC:
    def __init__(self, output):
        self.output = output
        self.admin_down_requests = []

    def get_load_info(self):
        return self.output

    def get_admin_down_slots(self, ap_name, slot_numbers):
        self.admin_down_requests.append((ap_name, tuple(slot_numbers)))
        return {2} if ap_name == "MBY-EVNT-CNTR_HLWY-22" else set()


class RecordingReporter:
    def __init__(self):
        self.steps = []

    def step(self, message):
        self.steps.append(message)


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


def test_collect_once_auto_excludes_admin_down_zero_zero_slots():
    output = """
AP Name                           Radio Mac       Slots  Clients       Slot0                   Slot1                   Slot2
                                                                Clients  Utilisation(%)  Clients  Utilisation(%)  Clients  Utilisation(%)
-----------------------------------------------------------------------------------------------------
MBY-EVNT-CNTR_HLWY-22             2416.1b75.2f60   3      24      0        41              23       34              0        0
"""
    session = FakeWLC(output)

    snapshot = collect_once(session, APBalanceConfig(auto_exclude_admin_down_slots=True))

    ap = snapshot.ap_loads[0]
    assert session.admin_down_requests == [("MBY-EVNT-CNTR_HLWY-22", (2,))]
    assert [(slot.slot, slot.clients, slot.utilization) for slot in ap.slot_loads] == [
        (0, 0, 41),
        (1, 23, 34),
        (2, None, None),
    ]
    assert "auto-excluded admin-down slots: S2" in ap.warnings


def test_collect_once_auto_exclude_respects_ap_filters():
    output = """
AP Name                           Radio Mac       Slots  Clients       Slot0                   Slot1
                                                                Clients  Utilisation(%)  Clients  Utilisation(%)
-----------------------------------------------------------------------------------------------------
MATCH-AP                          0c75.bdb5.6380   2      0       0        0               0        0
SKIP-AP                           0c75.bdb5.6381   2      0       0        0               0        0
"""
    session = FakeWLC(output)

    collect_once(session, APBalanceConfig(auto_exclude_admin_down_slots=True, include=("MATCH-*",)))

    assert session.admin_down_requests == [("MATCH-AP", (0, 1))]


def test_startup_reporter_prints_status_messages():
    console = Console(record=True, width=120)
    reporter = StartupReporter(console)

    reporter.step("Connecting to WLC 192.0.2.10")

    assert "Connecting to WLC 192.0.2.10" in console.export_text()


def test_run_once_reports_startup_steps(monkeypatch):
    output = """
AP Name                           Radio Mac       Slots  Clients       Slot0                   Slot1
                                                                Clients  Utilisation(%)  Clients  Utilisation(%)
-----------------------------------------------------------------------------------------------------
NOC-AP-1                          0c75.bdb5.6380   2      51      1        5               50       80
"""

    class FakeSession(FakeWLC):
        def __init__(self, _config):
            super().__init__(output)
            self.connected = False

        def connect(self):
            self.connected = True

        def disconnect(self):
            self.connected = False

    reporter = RecordingReporter()
    console = Console(record=True, width=120)
    monkeypatch.setattr("ap_radio_monitor.app.WLCLoadInfoSession", FakeSession)

    run_once(
        type("Config", (), {"host": "192.0.2.10"})(),
        APBalanceConfig(auto_exclude_admin_down_slots=True),
        console,
        reporter=reporter,
    )

    assert reporter.steps == [
        "Connecting to WLC 192.0.2.10",
        "Collecting AP radio load-info",
        "Loading radio admin/oper state",
        "Rendering monitor",
    ]


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
