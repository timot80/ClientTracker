from ap_radio_monitor.models import WLCConfig
from ap_port_audit.wlc import APPortAuditSession


def test_get_ethernet_statistics_runs_expected_command(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.commands = []

        def check_enable_mode(self):
            return True

        def send_command(self, command, **kwargs):
            self.commands.append((command, kwargs))
            return "output"

        def disconnect(self):
            pass

    fake = FakeConnection()
    monkeypatch.setattr("ap_port_audit.wlc.ConnectHandler", lambda **_kwargs: fake)
    session = APPortAuditSession(WLCConfig(host="192.0.2.10", username="u", password="p", read_timeout=120))

    session.connect()
    output = session.get_ethernet_statistics()

    assert output == "output"
    assert fake.commands == [
        ("terminal length 0", {"expect_string": r"#", "read_timeout": 30}),
        ("show ap ethernet statistics", {"expect_string": r"#", "read_timeout": 120}),
    ]
