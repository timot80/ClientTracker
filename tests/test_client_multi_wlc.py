from __future__ import annotations

from client_tracker.app import ClientTrackerApp
from client_tracker.config import APConfig, AppConfig, LocalConfig, WLCConfig, WlcClientTarget
from client_tracker.models import APClientState, WLCClientState


def make_config() -> AppConfig:
    targets = [
        WlcClientTarget("mby-1", WLCConfig(host="192.0.2.10", username="u", password="p")),
        WlcClientTarget("mby-2", WLCConfig(host="192.0.2.11", username="u", password="p")),
    ]
    return AppConfig(
        wlc=targets[0].config,
        wlc_targets=targets,
        ap=APConfig(username="ap-u", password="ap-p"),
        local=LocalConfig(),
    )


def test_client_tracker_searches_selected_wlcs_until_client_is_found(monkeypatch):
    sessions = []

    class FakeWLCSession:
        def __init__(self, host, username, password, enable=""):
            self.host = host
            self.hostname = f"host-{host}"
            self.queries = []
            self.disconnected = False
            sessions.append(self)

        def connect(self):
            pass

        def get_client_state(self, mac):
            self.queries.append(mac)
            if self.host == "192.0.2.11":
                return WLCClientState(mac=mac, timestamp=None)
            return None

        def disconnect(self):
            self.disconnected = True

    monkeypatch.setattr("client_tracker.app.WLCSession", FakeWLCSession)

    app = ClientTrackerApp("infra", make_config(), mac="7a:42:25:0f:94:66")
    app._setup()
    app.poll_once()
    app.cleanup()

    assert [session.host for session in sessions] == ["192.0.2.10", "192.0.2.11"]
    assert [session.queries for session in sessions] == [
        ["7a:42:25:0f:94:66"],
        ["7a:42:25:0f:94:66"],
    ]
    assert app.wlc_state is not None
    assert app.active_wlc_name == "mby-2"
    assert app._wlc_display_name() == "mby-2 (host-192.0.2.11)"
    assert all(session.disconnected for session in sessions)


def test_client_tracker_clears_stale_ap_state_when_client_not_found(monkeypatch):
    class FakeWLCSession:
        def __init__(self, host, username, password, enable=""):
            self.host = host
            self.hostname = f"host-{host}"

        def connect(self):
            pass

        def get_client_state(self, mac):
            return None

        def disconnect(self):
            pass

    monkeypatch.setattr("client_tracker.app.WLCSession", FakeWLCSession)

    app = ClientTrackerApp("infra", make_config(), mac="7a:42:25:0f:94:66")
    app.ap_state = APClientState(ap_name="MBY-CON-SCC1_BAYSIDE_D-49", rssi="-60")
    app.ap_error = "old AP error"

    app._setup()
    app.poll_once()
    app.cleanup()

    assert app.wlc_state is None
    assert app.ap_state is None
    assert app.ap_error == ""
