import csv
from datetime import datetime

from client_tracker.events import CSVLogger, EventTimeline
from client_tracker.models import TrackerEvent


def test_event_timeline_keeps_max_events():
    timeline = EventTimeline(max_events=2)
    timeline.append(TrackerEvent(datetime(2026, 5, 26, 1), "system", "startup", "one"))
    timeline.append(TrackerEvent(datetime(2026, 5, 26, 2), "local", "bssid-change", "two"))
    timeline.append(TrackerEvent(datetime(2026, 5, 26, 3), "infra", "roam", "three"))

    assert [event.message for event in timeline.items()] == ["two", "three"]


def test_csv_logger_writes_header_sample_and_event(tmp_path):
    path = tmp_path / "roam.csv"
    logger = CSVLogger(path)
    logger.write_sample(
        mode="combined",
        infra_ap_name="AP-1",
        local_bssid="aa:bb:cc:dd:ee:ff",
    )
    logger.write_event(
        mode="combined",
        event=TrackerEvent(
            datetime(2026, 5, 26, 12, 0, 0),
            "infra",
            "roam",
            "AP changed",
            previous_ap="AP-1",
            current_ap="AP-2",
        ),
    )

    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert rows[0]["row_type"] == "sample"
    assert rows[0]["mode"] == "combined"
    assert rows[0]["infra_ap_name"] == "AP-1"
    assert rows[0]["local_bssid"] == "aa:bb:cc:dd:ee:ff"
    assert rows[1]["row_type"] == "event"
    assert rows[1]["event_source"] == "infra"
    assert rows[1]["event_type"] == "roam"
    assert rows[1]["event_message"] == "AP changed"
