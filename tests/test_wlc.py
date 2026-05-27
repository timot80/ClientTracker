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
