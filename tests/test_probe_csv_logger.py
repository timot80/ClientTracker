from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor

from wifiops_probe.csv_logger import AndroidCSVLogger
from wifiops_probe.models import AndroidTelemetryRecord


def test_android_csv_logger_writes_probe_columns(tmp_path):
    path = tmp_path / "probe.csv"
    logger = AndroidCSVLogger(path)
    logger.write_record(
        AndroidTelemetryRecord(
            schema_version=1,
            session_id="walk_1",
            device_id="android_1",
            record_id="r1",
            sequence_number=7,
            record_type="sample",
            client_timestamp="2026-05-27T14:05:31-07:00",
            app_version="0.1.0",
            android_api_level=35,
            payload={
                "ssid": "corp-wifi",
                "bssid": "aa:bb:cc:dd:ee:ff",
                "rssi": -63,
                "frequency_mhz": 5180,
                "channel": "36",
                "tx_link_mbps": 432,
                "rx_link_mbps": 390,
                "dns": ["192.0.2.53", "2001:db8::53"],
                "manufacturer": "Google",
                "model": "Pixel",
                "availability": {"ssid": "unavailable_or_redacted"},
                "probes": {
                    "gateway": {"ok": True, "latency_ms": 8},
                    "dns": {"ok": True, "latency_ms": 24, "detail": "93.184.216.34"},
                    "http": {"ok": True, "latency_ms": 90, "detail": "200"},
                },
            },
        ),
        status="accepted",
    )
    logger.close()

    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert rows[0]["session_id"] == "walk_1"
    assert rows[0]["record_id"] == "r1"
    assert rows[0]["local_ssid"] == "corp-wifi"
    assert rows[0]["local_frequency_mhz"] == "5180"
    assert rows[0]["tx_link_mbps"] == "432"
    assert rows[0]["rx_link_mbps"] == "390"
    assert rows[0]["dns"] == "192.0.2.53;2001:db8::53"
    assert rows[0]["manufacturer"] == "Google"
    assert rows[0]["model"] == "Pixel"
    assert rows[0]["availability"] == "ssid=unavailable_or_redacted"
    assert rows[0]["probe_gateway"] == "ok 8ms"
    assert rows[0]["probe_dns"] == "ok 24ms"
    assert rows[0]["probe_http"] == "ok 90ms"


def test_android_csv_logger_writes_ipv6_columns(tmp_path):
    path = tmp_path / "probe.csv"
    logger = AndroidCSVLogger(path)
    logger.write_record(
        AndroidTelemetryRecord(
            schema_version=1,
            session_id="walk_1",
            device_id="android_1",
            record_id="r1",
            sequence_number=7,
            record_type="sample",
            client_timestamp="2026-05-27T14:05:31-07:00",
            app_version="0.1.0",
            android_api_level=35,
            payload={
                "ipv4_address": "192.0.2.45",
                "ipv6_addresses": ["2001:db8::45", "fe80::45"],
                "ip_addresses": ["192.0.2.45", "2001:db8::45", "fe80::45"],
                "gateway": "fe80::1",
            },
        ),
        status="accepted",
    )
    logger.close()

    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert rows[0]["local_ipv4_address"] == "192.0.2.45"
    assert rows[0]["local_ipv6_addresses"] == "2001:db8::45;fe80::45"
    assert rows[0]["local_ip_addresses"] == "192.0.2.45;2001:db8::45;fe80::45"
    assert rows[0]["gateway"] == "fe80::1"


def test_android_csv_logger_writes_event_diagnostics_and_flushes(tmp_path):
    path = tmp_path / "probe.csv"
    logger = AndroidCSVLogger(path)
    logger.write_record(
        AndroidTelemetryRecord(
            schema_version=1,
            session_id="walk_1",
            device_id="android_1",
            record_id="r2",
            sequence_number=8,
            record_type="event",
            client_timestamp="2026-05-27T14:05:32-07:00",
            app_version="0.1.0",
            android_api_level=35,
            payload={
                "event_type": "upload-failed",
                "message": "receiver unavailable",
                "error": "HTTP 503",
            },
        ),
        status="accepted",
    )

    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    logger.close()

    assert rows[0]["event_type"] == "upload-failed"
    assert rows[0]["event_message"] == "receiver unavailable"
    assert rows[0]["error"] == "HTTP 503"


def test_android_csv_logger_writes_concurrent_records(tmp_path):
    path = tmp_path / "probe.csv"
    logger = AndroidCSVLogger(path)
    record_count = 200

    def write_record(index: int):
        logger.write_record(
            AndroidTelemetryRecord(
                schema_version=1,
                session_id="walk_1",
                device_id="android_1",
                record_id=f"r{index}",
                sequence_number=index,
                record_type="sample",
                client_timestamp="2026-05-27T14:05:31-07:00",
                app_version="0.1.0",
                android_api_level=35,
                payload={"ssid": "corp-wifi", "bssid": "aa:bb:cc:dd:ee:ff", "rssi": -63},
            ),
            status="accepted",
        )

    with ThreadPoolExecutor(max_workers=12) as executor:
        list(executor.map(write_record, range(record_count)))
    logger.close()

    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    record_ids = {row["record_id"] for row in rows}
    assert len(rows) == record_count
    assert len(record_ids) == record_count
