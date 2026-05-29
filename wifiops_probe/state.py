from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from wifiops_probe.models import AndroidTelemetryRecord


@dataclass
class ReceiverSession:
    session_id: str
    token: str
    device_id: str = ""
    accepted_record_ids: set[str] = field(default_factory=set)
    latest_record: AndroidTelemetryRecord | None = None
    _lock: Lock = field(default_factory=Lock, repr=False, compare=False)

    def ingest(self, record: AndroidTelemetryRecord) -> str:
        with self._lock:
            if record.session_id != self.session_id:
                return "rejected_session"
            if self.device_id and record.device_id != self.device_id:
                return "rejected_device"
            if record.record_id in self.accepted_record_ids:
                return "duplicate"
            if not self.device_id:
                self.device_id = record.device_id
            self.accepted_record_ids.add(record.record_id)
            self.latest_record = record
            return "accepted"
