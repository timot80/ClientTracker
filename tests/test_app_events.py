from datetime import datetime

from client_tracker.app import detect_infra_roam, detect_local_change
from client_tracker.models import APClientState, LocalClientState, WLCClientState


def test_detect_infra_roam_uses_last_ap_stats():
    event = detect_infra_roam(
        previous_ap="AP-1",
        current=WLCClientState(ap_name="AP-2"),
        last_ap_state=APClientState(rssi="-51", mcs_rate="MCS92SS", channel="36"),
        now=datetime(2026, 5, 26, 12, 0, 0),
    )

    assert event is not None
    assert event.type == "roam"
    assert event.previous_ap == "AP-1"
    assert event.current_ap == "AP-2"
    assert event.rssi == "-51"
    assert event.channel == "36"


def test_detect_local_change_reports_bssid_change():
    event = detect_local_change(
        previous=LocalClientState(bssid="aa:bb:cc:dd:ee:ff"),
        current=LocalClientState(bssid="11:22:33:44:55:66", signal="-60", channel="40"),
        now=datetime(2026, 5, 26, 12, 0, 0),
    )

    assert event is not None
    assert event.type == "bssid-change"
    assert event.previous_bssid == "aa:bb:cc:dd:ee:ff"
    assert event.current_bssid == "11:22:33:44:55:66"
