from __future__ import annotations

from wifiops_probe.models import TelemetryValidationError, parse_record_batch


def valid_sample(record_id: str = "01JABC") -> dict:
    return {
        "schema_version": 1,
        "session_id": "walk_20260527_abc123",
        "device_id": "android_probe_9f3c",
        "record_id": record_id,
        "sequence_number": 42,
        "record_type": "sample",
        "client_timestamp": "2026-05-27T14:05:31.123-07:00",
        "app_version": "0.1.0",
        "android_api_level": 35,
        "payload": {
            "ssid": "corp-wifi",
            "bssid": "aa:bb:cc:dd:ee:ff",
            "rssi": -63,
            "frequency_mhz": 5180,
            "channel": "36",
            "tx_link_mbps": 432,
            "rx_link_mbps": 390,
            "ipv4_address": "192.0.2.45",
            "gateway": "192.0.2.1",
            "dns": ["192.0.2.53"],
            "availability": {},
            "probes": {
                "gateway": {"ok": True, "latency_ms": 8},
                "dns": {"ok": True, "latency_ms": 24, "hostname": "example.com"},
                "http": {"ok": True, "latency_ms": 90, "status": 204, "url": "https://example.com/health"},
            },
        },
    }


def test_parse_record_batch_accepts_valid_sample():
    records = parse_record_batch({"records": [valid_sample()]})

    assert len(records) == 1
    assert records[0].record_id == "01JABC"
    assert records[0].record_type == "sample"
    assert records[0].payload["ssid"] == "corp-wifi"


def test_parse_record_batch_rejects_missing_records_array():
    try:
        parse_record_batch({"record": valid_sample()})
    except TelemetryValidationError as exc:
        assert exc.code == "missing_records"
    else:
        raise AssertionError("expected TelemetryValidationError")


def test_parse_record_batch_rejects_too_many_records():
    payload = {"records": [valid_sample(str(index)) for index in range(101)]}

    try:
        parse_record_batch(payload)
    except TelemetryValidationError as exc:
        assert exc.code == "too_many_records"
    else:
        raise AssertionError("expected TelemetryValidationError")


def test_parse_record_batch_rejects_missing_required_field():
    sample = valid_sample()
    del sample["device_id"]

    try:
        parse_record_batch({"records": [sample]})
    except TelemetryValidationError as exc:
        assert exc.code == "missing_field"
        assert "device_id" in exc.message
    else:
        raise AssertionError("expected TelemetryValidationError")


def test_parse_record_batch_rejects_missing_app_version():
    sample = valid_sample()
    del sample["app_version"]

    try:
        parse_record_batch({"records": [sample]})
    except TelemetryValidationError as exc:
        assert exc.code == "missing_field"
        assert "app_version" in exc.message
    else:
        raise AssertionError("expected TelemetryValidationError")


def test_parse_record_batch_rejects_missing_android_api_level():
    sample = valid_sample()
    del sample["android_api_level"]

    try:
        parse_record_batch({"records": [sample]})
    except TelemetryValidationError as exc:
        assert exc.code == "missing_field"
        assert "android_api_level" in exc.message
    else:
        raise AssertionError("expected TelemetryValidationError")


def test_parse_record_batch_rejects_array_body():
    try:
        parse_record_batch([])
    except TelemetryValidationError as exc:
        assert exc.code == "invalid_body"
    else:
        raise AssertionError("expected TelemetryValidationError")


def test_parse_record_batch_rejects_none_body():
    try:
        parse_record_batch(None)
    except TelemetryValidationError as exc:
        assert exc.code == "invalid_body"
    else:
        raise AssertionError("expected TelemetryValidationError")


def test_parse_record_batch_rejects_bool_sequence_number():
    sample = valid_sample()
    sample["sequence_number"] = True

    try:
        parse_record_batch({"records": [sample]})
    except TelemetryValidationError as exc:
        assert exc.code == "invalid_sequence"
    else:
        raise AssertionError("expected TelemetryValidationError")


def test_parse_record_batch_rejects_non_string_device_id():
    sample = valid_sample()
    sample["device_id"] = 123

    try:
        parse_record_batch({"records": [sample]})
    except TelemetryValidationError as exc:
        assert exc.code == "invalid_string"
        assert "device_id" in exc.message
    else:
        raise AssertionError("expected TelemetryValidationError")


def test_parse_record_batch_rejects_empty_app_version():
    sample = valid_sample()
    sample["app_version"] = ""

    try:
        parse_record_batch({"records": [sample]})
    except TelemetryValidationError as exc:
        assert exc.code == "invalid_string"
        assert "app_version" in exc.message
    else:
        raise AssertionError("expected TelemetryValidationError")


def test_parse_record_batch_rejects_invalid_android_api_level():
    sample = valid_sample()
    sample["android_api_level"] = True

    try:
        parse_record_batch({"records": [sample]})
    except TelemetryValidationError as exc:
        assert exc.code == "invalid_android_api_level"
    else:
        raise AssertionError("expected TelemetryValidationError")
