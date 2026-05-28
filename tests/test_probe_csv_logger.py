from __future__ import annotations

import csv

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
            payload={"ssid": "corp-wifi", "bssid": "aa:bb:cc:dd:ee:ff", "rssi": -63},
        ),
        status="accepted",
    )
    logger.close()

    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert rows[0]["session_id"] == "walk_1"
    assert rows[0]["record_id"] == "r1"
    assert rows[0]["local_ssid"] == "corp-wifi"
