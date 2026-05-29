from __future__ import annotations

import csv
import threading
from pathlib import Path
from typing import Any

from wifiops_probe.models import AndroidTelemetryRecord


ANDROID_CSV_COLUMNS = (
    "session_id",
    "device_id",
    "record_id",
    "sequence_number",
    "record_type",
    "client_timestamp",
    "status",
    "local_ssid",
    "local_bssid",
    "local_channel",
    "local_frequency_mhz",
    "local_signal",
    "tx_link_mbps",
    "rx_link_mbps",
    "local_ipv4_address",
    "local_ipv6_addresses",
    "local_ip_addresses",
    "gateway",
    "dns",
    "manufacturer",
    "model",
    "availability",
    "probe_gateway",
    "probe_dns",
    "probe_http",
    "event_type",
    "event_message",
    "error",
)


class AndroidCSVLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.path.exists() or self.path.stat().st_size == 0
        self._file = self.path.open("a", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=ANDROID_CSV_COLUMNS)
        self._lock = threading.Lock()
        if write_header:
            self._writer.writeheader()

    def write_record(self, record: AndroidTelemetryRecord, status: str):
        payload = record.payload
        probes = payload.get("probes")
        with self._lock:
            self._writer.writerow(
                {
                    "session_id": record.session_id,
                    "device_id": record.device_id,
                    "record_id": record.record_id,
                    "sequence_number": record.sequence_number,
                    "record_type": record.record_type,
                    "client_timestamp": record.client_timestamp,
                    "status": status,
                    "local_ssid": _string(payload.get("ssid")),
                    "local_bssid": _string(payload.get("bssid")),
                    "local_channel": _string(payload.get("channel")),
                    "local_frequency_mhz": _string(payload.get("frequency_mhz")),
                    "local_signal": _string(payload.get("rssi")),
                    "tx_link_mbps": _string(payload.get("tx_link_mbps")),
                    "rx_link_mbps": _string(payload.get("rx_link_mbps")),
                    "local_ipv4_address": _string(payload.get("ipv4_address")),
                    "local_ipv6_addresses": _string_list(payload.get("ipv6_addresses")),
                    "local_ip_addresses": _string_list(payload.get("ip_addresses")),
                    "gateway": _string(payload.get("gateway")),
                    "dns": _string_list(payload.get("dns")),
                    "manufacturer": _string(payload.get("manufacturer")),
                    "model": _string(payload.get("model")),
                    "availability": _availability_cell(payload.get("availability")),
                    "probe_gateway": _probe_cell(probes, "gateway"),
                    "probe_dns": _probe_cell(probes, "dns"),
                    "probe_http": _probe_cell(probes, "http"),
                    "event_type": _string(payload.get("event_type")),
                    "event_message": _string(payload.get("message")),
                    "error": _string(payload.get("error")),
                }
            )
            self._file.flush()

    def close(self):
        self._file.close()


def _probe_cell(probes: Any, name: str) -> str:
    if not isinstance(probes, dict):
        return ""
    probe = probes.get(name)
    if not isinstance(probe, dict):
        return ""
    status = "ok" if probe.get("ok") else "failed"
    latency = probe.get("latency_ms")
    if latency is None:
        return status
    return f"{status} {latency}ms"


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _string_list(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def _availability_cell(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return ";".join(f"{key}={value[key]}" for key in sorted(value))
