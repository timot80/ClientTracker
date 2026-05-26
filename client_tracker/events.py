from __future__ import annotations

import csv
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import TrackerEvent

CSV_COLUMNS = [
    "timestamp",
    "row_type",
    "mode",
    "infra_ap_name",
    "infra_ap_ip",
    "infra_ssid",
    "infra_rssi",
    "infra_snr",
    "ap_rssi",
    "ap_channel",
    "ap_mcs_rate",
    "local_ssid",
    "local_bssid",
    "local_channel",
    "local_signal",
    "local_noise",
    "event_source",
    "event_type",
    "event_message",
    "error",
]


class EventTimeline:
    def __init__(self, max_events: int = 10):
        self._events: deque[TrackerEvent] = deque(maxlen=max_events)

    def append(self, event: TrackerEvent):
        self._events.append(event)

    def items(self) -> list[TrackerEvent]:
        return list(self._events)


class CSVLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not self.path.exists()
        self._fh = self.path.open("a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=CSV_COLUMNS)
        if new_file:
            self._writer.writeheader()
            self._fh.flush()

    def write_sample(self, mode: str, **fields: Any):
        row = self._base_row(mode, "sample")
        row.update({key: value for key, value in fields.items() if key in row})
        self._writer.writerow(row)
        self._fh.flush()

    def write_event(self, mode: str, event: TrackerEvent):
        row = self._base_row(mode, "event")
        row.update(
            {
                "timestamp": event.timestamp.isoformat(),
                "event_source": event.source,
                "event_type": event.type,
                "event_message": event.message,
                "infra_ap_name": event.current_ap,
                "ap_rssi": event.rssi,
                "ap_channel": event.channel,
                "local_bssid": event.current_bssid,
                "error": event.error,
            }
        )
        self._writer.writerow(row)
        self._fh.flush()

    def close(self):
        self._fh.close()

    @staticmethod
    def _base_row(mode: str, row_type: str) -> dict[str, Any]:
        return {column: "" for column in CSV_COLUMNS} | {
            "timestamp": datetime.now().isoformat(),
            "row_type": row_type,
            "mode": mode,
        }
