from __future__ import annotations

from datetime import datetime, timezone

from wifiops_probe.adapters import event_from_record, local_state_from_record
from wifiops_probe.models import AndroidTelemetryRecord


def record(
    payload: dict,
    record_type: str = "sample",
    client_timestamp: str = "2026-05-27T14:05:31-07:00",
) -> AndroidTelemetryRecord:
    return AndroidTelemetryRecord(
        schema_version=1,
        session_id="walk_1",
        device_id="android_1",
        record_id="r1",
        sequence_number=7,
        record_type=record_type,
        client_timestamp=client_timestamp,
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
    assert state.timestamp == datetime.fromisoformat("2026-05-27T14:05:31-07:00")


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
    assert event.timestamp == datetime.fromisoformat("2026-05-27T14:05:31-07:00")


def test_event_from_record_maps_upload_failed_with_client_timestamp():
    event = event_from_record(
        record(
            {
                "event_type": "upload-failed",
                "message": "receiver unavailable",
                "error": "HTTP 503",
            },
            record_type="event",
            client_timestamp="2026-05-27T21:05:31Z",
        )
    )

    assert event is not None
    assert event.source == "local"
    assert event.type == "poll-error"
    assert event.message == "HTTP 503"
    assert event.error == "HTTP 503"
    assert event.timestamp == datetime(2026, 5, 27, 21, 5, 31, tzinfo=timezone.utc)
