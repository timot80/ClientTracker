from rich.console import Console

from ap_port_audit.app import collect_once, run_once
from ap_port_audit.models import APPortAuditConfig
from ap_radio_monitor.models import WLCConfig


SAMPLE_OUTPUT = """
AP Name : BAD-AP
Interface Name      Status  Speed       Duplex  Rx Packets    Tx Packets    Discarded Packets
------------------------------------------------------------------------------------------------
GigabitEthernet0    UP       100 Mbps    Half    1             2             0
"""


class FakeSession:
    def __init__(self, _config=None):
        self.connected = False

    def connect(self):
        self.connected = True

    def get_ethernet_statistics(self):
        return SAMPLE_OUTPUT

    def disconnect(self):
        self.connected = False


def test_collect_once_parses_session_output():
    snapshot = collect_once(FakeSession(), APPortAuditConfig())

    assert snapshot.rows[0].ap_name == "BAD-AP"
    assert snapshot.rows[0].speed_mbps == 100


def test_run_once_renders_audit_table(monkeypatch):
    console = Console(record=True, width=140)
    monkeypatch.setattr("ap_port_audit.app.APPortAuditSession", FakeSession)

    exit_code = run_once(WLCConfig(host="192.0.2.10", username="u", password="p"), APPortAuditConfig(), console)

    rendered = console.export_text()
    assert exit_code == 0
    assert "BAD-AP" in rendered
    assert "LOW-SPEED" in rendered
    assert "HALF-DUPLEX" in rendered


def test_run_once_returns_nonzero_for_unparseable_output(monkeypatch):
    class EmptySession(FakeSession):
        def get_ethernet_statistics(self):
            return "not AP Ethernet statistics"

    console = Console(record=True, width=140)
    monkeypatch.setattr("ap_port_audit.app.APPortAuditSession", EmptySession)

    exit_code = run_once(WLCConfig(host="192.0.2.10", username="u", password="p"), APPortAuditConfig(), console)

    rendered = console.export_text()
    assert exit_code == 1
    assert "no AP Ethernet port rows parsed" in rendered
