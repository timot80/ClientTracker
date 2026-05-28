from __future__ import annotations

from wifiops_probe.adapters import event_from_record, local_state_from_record
from wifiops_probe.models import AndroidTelemetryRecord


def record(payload: dict, record_type: str = "sample") -> AndroidTelemetryRecord:
    return AndroidTelemetryRecord(
        schema_version=1,
        session_id="walk_1",
        device_id="android_1",
        record_id="r1",
        sequence_number=7,
        record_type=record_type,
        client_timestamp="2026-05-27T14:05:31-07:00",
        app_version="0.1.0",
        android_api_level=35,
        payload=payload,
    )


def test_local_state_from_record_maps_android_sample():
    state = local_state_from_record(
        record(
            {
                "ssid": "corp-wifi",
                "bssid": "aa:bb:cc:dd:ee:ff",
                "channel": "36",
                "rssi": -63,
                "tx_link_mbps": 432,
                "rx_link_mbps": 390,
                "ipv4_address": "192.0.2.45",
                "gateway": "192.0.2.1",
                "probes": {"gateway": {"ok": True, "latency_ms": 8}},
            }
        )
    )

    assert state.platform == "android"
    assert state.ssid == "corp-wifi"
    assert state.signal == "-63"
    assert state.tx_rate == "432"
    assert state.ping_status == "gateway ok 8ms"


def test_event_from_record_maps_bssid_change():
    event = event_from_record(
        record(
            {
                "event_type": "bssid-change",
                "previous_bssid": "aa:bb:cc:dd:ee:ff",
                "current_bssid": "11:22:33:44:55:66",
                "rssi": -61,
                "channel": "44",
            },
            record_type="event",
        )
    )

    assert event is not None
    assert event.type == "bssid-change"
    assert event.current_bssid == "11:22:33:44:55:66"
