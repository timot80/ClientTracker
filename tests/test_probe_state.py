from __future__ import annotations

from wifiops_probe.models import AndroidTelemetryRecord
from wifiops_probe.state import ReceiverSession


def telemetry_record(
    record_id: str = "01JABC",
    device_id: str = "android_probe_9f3c",
    session_id: str = "walk_20260527_abc123",
) -> AndroidTelemetryRecord:
    return AndroidTelemetryRecord(
        schema_version=1,
        session_id=session_id,
        device_id=device_id,
        record_id=record_id,
        sequence_number=42,
        record_type="sample",
        client_timestamp="2026-05-27T14:05:31.123-07:00",
        payload={"ssid": "corp-wifi"},
        app_version="0.1.0",
        android_api_level=35,
    )


def test_receiver_session_accepts_first_record_and_binds_device():
    session = ReceiverSession(session_id="walk_20260527_abc123", token="secret")
    record = telemetry_record()

    result = session.ingest(record)

    assert result == "accepted"
    assert session.device_id == "android_probe_9f3c"
    assert session.latest_record == record


def test_receiver_session_deduplicates_record_id():
    session = ReceiverSession(session_id="walk_20260527_abc123", token="secret")
    record = telemetry_record(record_id="01JABC")

    assert session.ingest(record) == "accepted"
    assert session.ingest(record) == "duplicate"


def test_receiver_session_rejects_mismatched_device_after_binding():
    session = ReceiverSession(session_id="walk_20260527_abc123", token="secret")

    assert session.ingest(telemetry_record(device_id="android_probe_9f3c")) == "accepted"
    assert session.ingest(telemetry_record(record_id="01JABD", device_id="android_probe_other")) == "rejected_device"

