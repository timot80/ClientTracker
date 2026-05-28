from rich.console import Console

from ap_port_audit.app import collect_once, run_once
from ap_port_audit.models import APPortAuditConfig
from ap_radio_monitor.models import WLCConfig
from wifiops.wlc_targets import WlcTarget


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


def test_run_multi_aggregates_rows_and_returns_nonzero_for_partial_failure(monkeypatch):
    from ap_port_audit.app import run_multi

    class MultiSession:
        def __init__(self, config):
            self.config = config

        def connect(self):
            pass

        def get_ethernet_statistics(self):
            if self.config.host == "192.0.2.11":
                raise RuntimeError("connection lost")
            return SAMPLE_OUTPUT

        def disconnect(self):
            pass

    targets = [
        WlcTarget("mby-1", WLCConfig(host="192.0.2.10", username="u", password="p")),
        WlcTarget("mby-2", WLCConfig(host="192.0.2.11", username="u", password="p")),
    ]
    console = Console(record=True, width=160)
    monkeypatch.setattr("ap_port_audit.app.APPortAuditSession", MultiSession)

    exit_code = run_multi(targets, APPortAuditConfig(), 2, console)

    rendered = console.export_text()
    assert exit_code == 1
    assert "mby-1" in rendered
    assert "BAD-AP" in rendered
    assert "mby-2" in rendered
    assert "connection lost" in rendered
