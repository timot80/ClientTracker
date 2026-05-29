from __future__ import annotations

from client_tracker.display import LiveDisplay
from client_tracker.events import EventTimeline

from .adapters import event_from_record, local_state_from_record
from .models import AndroidTelemetryRecord


class ProbeDisplayState:
    def __init__(self):
        self.display = LiveDisplay()
        self.timeline = EventTimeline()
        self.local_state = None

    def ingest_for_display(self, record: AndroidTelemetryRecord):
        if record.record_type == "sample":
            self.local_state = local_state_from_record(record)
        event = event_from_record(record)
        if event:
            self.timeline.append(event)

    def render(self):
        return self.display.build(
            wlc_hostname="",
            wlc_state=None,
            ap_state=None,
            local_state=self.local_state,
            events=self.timeline.items(),
            mode="local",
        )
