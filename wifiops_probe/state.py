from __future__ import annotations

from dataclasses import dataclass, field

from wifiops_probe.models import AndroidTelemetryRecord


@dataclass
class ReceiverSession:
    session_id: str
    token: str
    device_id: str = ""
    accepted_record_ids: set[str] = field(default_factory=set)
    latest_record: AndroidTelemetryRecord | None = None

    def ingest(self, record: AndroidTelemetryRecord) -> str:
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

