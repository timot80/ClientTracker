# Android Probe Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first Android walk-test probe that sends client Wi-Fi telemetry to `wifiops`, buffers telemetry offline, and can later target a hosted collector using the same record envelope.

**Architecture:** Implement the Python receiver contract first under a new `wifiops_probe` package, then wire it into `wifiops probe receive`. Keep Android records separate from existing `client_tracker` internals and project only the latest state/events into `LocalClientState`, `TrackerEvent`, and receiver-owned CSV output. Add a native Kotlin Android app under `android/wifiops-probe` with Room persistence, a foreground collection service, QR/manual pairing, and ordered sync.

**Tech Stack:** Python 3.10+, standard library `ThreadingHTTPServer`, Rich, pytest, Kotlin, Gradle Android plugin, Jetpack Compose, Room, Kotlin serialization or Moshi, OkHttp, ML Kit Barcode Scanning.

---

## File Structure

Python receiver:

- Create `wifiops_probe/__init__.py`: package marker and public version import if needed.
- Create `wifiops_probe/models.py`: dataclasses for telemetry records, probe payloads, acknowledgements, and validation errors.
- Create `wifiops_probe/security.py`: token generation, authorization parsing, token redaction, pairing payload generation.
- Create `wifiops_probe/state.py`: in-memory receiver session state, dedupe, device binding, latest normalized state.
- Create `wifiops_probe/adapters.py`: Android record to `LocalClientState` and `TrackerEvent` projection.
- Create `wifiops_probe/csv_logger.py`: Android-specific CSV writer that preserves existing CSV compatibility by staying receiver-owned.
- Create `wifiops_probe/http_server.py`: `ThreadingHTTPServer` handler for `/health`, `/api/v1/sessions/{session_id}/records`, and `/latest`.
- Create `wifiops_probe/display.py`: Rich live receiver display using existing `client_tracker.display.LiveDisplay`.
- Create `wifiops_probe/cli.py`: receiver command implementation.
- Modify `wifiops/cli.py`: add `wifiops probe receive` command and delegate to `wifiops_probe.cli.main`.
- Modify `pyproject.toml`: include `wifiops_probe*` in package discovery.
- Create tests under `tests/test_probe_*.py`.

Android app:

- Create `android/wifiops-probe/settings.gradle.kts`.
- Create `android/wifiops-probe/build.gradle.kts`.
- Create `android/wifiops-probe/app/build.gradle.kts`.
- Create `android/wifiops-probe/app/src/main/AndroidManifest.xml`.
- Create `android/wifiops-probe/app/src/main/res/xml/network_security_config.xml`.
- Create Kotlin packages under `android/wifiops-probe/app/src/main/java/com/wifiops/probe/`.
- Create Android unit tests under `android/wifiops-probe/app/src/test/java/com/wifiops/probe/`.

---

### Task 1: Python Telemetry Contract

**Files:**
- Create: `wifiops_probe/__init__.py`
- Create: `wifiops_probe/models.py`
- Test: `tests/test_probe_models.py`

- [ ] **Step 1: Write failing model validation tests**

Create `tests/test_probe_models.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_probe_models.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'wifiops_probe'`.

- [ ] **Step 3: Add minimal telemetry models and validation**

Create `wifiops_probe/__init__.py`:

```python
from __future__ import annotations
```

Create `wifiops_probe/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

RecordType = Literal["sample", "event"]

MAX_RECORDS_PER_BATCH = 100
MAX_BODY_BYTES = 1024 * 1024
REQUIRED_RECORD_FIELDS = (
    "schema_version",
    "session_id",
    "device_id",
    "record_id",
    "sequence_number",
    "record_type",
    "client_timestamp",
    "payload",
)


class TelemetryValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AndroidTelemetryRecord:
    schema_version: int
    session_id: str
    device_id: str
    record_id: str
    sequence_number: int
    record_type: RecordType
    client_timestamp: str
    payload: dict[str, Any]
    app_version: str = ""
    android_api_level: int | None = None


def parse_record_batch(body: dict[str, Any]) -> list[AndroidTelemetryRecord]:
    records = body.get("records")
    if not isinstance(records, list):
        raise TelemetryValidationError("missing_records", "request body must contain a records array")
    if len(records) > MAX_RECORDS_PER_BATCH:
        raise TelemetryValidationError("too_many_records", "records array exceeds 100 entries")
    return [_parse_record(record) for record in records]


def _parse_record(record: Any) -> AndroidTelemetryRecord:
    if not isinstance(record, dict):
        raise TelemetryValidationError("invalid_record", "each record must be a JSON object")
    for field in REQUIRED_RECORD_FIELDS:
        if field not in record:
            raise TelemetryValidationError("missing_field", f"record is missing required field {field}")
    if record["schema_version"] != 1:
        raise TelemetryValidationError("unsupported_schema", "schema_version must be 1")
    if record["record_type"] not in ("sample", "event"):
        raise TelemetryValidationError("invalid_record_type", "record_type must be sample or event")
    if not isinstance(record["sequence_number"], int):
        raise TelemetryValidationError("invalid_sequence", "sequence_number must be an integer")
    if not isinstance(record["payload"], dict):
        raise TelemetryValidationError("invalid_payload", "payload must be an object")
    return AndroidTelemetryRecord(
        schema_version=record["schema_version"],
        session_id=str(record["session_id"]),
        device_id=str(record["device_id"]),
        record_id=str(record["record_id"]),
        sequence_number=record["sequence_number"],
        record_type=record["record_type"],
        client_timestamp=str(record["client_timestamp"]),
        payload=record["payload"],
        app_version=str(record.get("app_version", "")),
        android_api_level=record.get("android_api_level"),
    )
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
pytest tests/test_probe_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wifiops_probe/__init__.py wifiops_probe/models.py tests/test_probe_models.py
git commit -m "Add Android probe telemetry contract"
```

---

### Task 2: Pairing Security And Receiver State

**Files:**
- Create: `wifiops_probe/security.py`
- Create: `wifiops_probe/state.py`
- Test: `tests/test_probe_security.py`
- Test: `tests/test_probe_state.py`

- [ ] **Step 1: Write failing security and state tests**

Create `tests/test_probe_security.py`:

```python
from __future__ import annotations

from wifiops_probe.security import generate_token, parse_bearer_token, redact_token


def test_generate_token_is_urlsafe_and_high_entropy():
    token = generate_token()

    assert len(token) >= 22
    assert " " not in token


def test_parse_bearer_token_accepts_authorization_header():
    assert parse_bearer_token("Bearer abc123") == "abc123"


def test_parse_bearer_token_rejects_missing_or_wrong_scheme():
    assert parse_bearer_token("") == ""
    assert parse_bearer_token("Basic abc123") == ""


def test_redact_token_preserves_small_debug_hint():
    assert redact_token("abcdefghijklmnopqrstuvwxyz").startswith("abcd")
    assert "efghijklmnopqrstuvwxyz" not in redact_token("abcdefghijklmnopqrstuvwxyz")
```

Create `tests/test_probe_state.py`:

```python
from __future__ import annotations

from wifiops_probe.models import AndroidTelemetryRecord
from wifiops_probe.state import ReceiverSession


def sample(record_id: str, device_id: str = "android_probe_1") -> AndroidTelemetryRecord:
    return AndroidTelemetryRecord(
        schema_version=1,
        session_id="walk_1",
        device_id=device_id,
        record_id=record_id,
        sequence_number=1,
        record_type="sample",
        client_timestamp="2026-05-27T14:05:31-07:00",
        payload={"ssid": "corp-wifi"},
    )


def test_session_accepts_first_record_and_binds_device():
    session = ReceiverSession(session_id="walk_1", token="secret")

    status = session.ingest(sample("r1"))

    assert status == "accepted"
    assert session.device_id == "android_probe_1"
    assert session.latest_record.record_id == "r1"


def test_session_deduplicates_record_id():
    session = ReceiverSession(session_id="walk_1", token="secret")
    session.ingest(sample("r1"))

    assert session.ingest(sample("r1")) == "duplicate"


def test_session_rejects_mismatched_device_after_binding():
    session = ReceiverSession(session_id="walk_1", token="secret")
    session.ingest(sample("r1", "android_probe_1"))

    assert session.ingest(sample("r2", "android_probe_2")) == "rejected_device"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_probe_security.py tests/test_probe_state.py -v
```

Expected: FAIL because `wifiops_probe.security` and `wifiops_probe.state` do not exist.

- [ ] **Step 3: Implement token helpers and in-memory receiver state**

Create `wifiops_probe/security.py`:

```python
from __future__ import annotations

import secrets


def generate_token() -> str:
    return secrets.token_urlsafe(24)


def parse_bearer_token(header: str) -> str:
    prefix = "Bearer "
    if not header.startswith(prefix):
        return ""
    return header[len(prefix) :].strip()


def redact_token(token: str) -> str:
    if len(token) <= 8:
        return "<redacted>"
    return f"{token[:4]}...<redacted>"
```

Create `wifiops_probe/state.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from .models import AndroidTelemetryRecord


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
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
pytest tests/test_probe_security.py tests/test_probe_state.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wifiops_probe/security.py wifiops_probe/state.py tests/test_probe_security.py tests/test_probe_state.py
git commit -m "Add Android probe pairing state"
```

---

### Task 3: Android Record Adapters And CSV Logger

**Files:**
- Create: `wifiops_probe/adapters.py`
- Create: `wifiops_probe/csv_logger.py`
- Test: `tests/test_probe_adapters.py`
- Test: `tests/test_probe_csv_logger.py`

- [ ] **Step 1: Write failing adapter and CSV tests**

Create `tests/test_probe_adapters.py`:

```python
from __future__ import annotations

from wifiops_probe.adapters import event_from_record, local_state_from_record
from wifiops_probe.models import AndroidTelemetryRecord


def record(payload: dict, record_type: str = "sample") -> AndroidTelemetryRecord:
    return AndroidTelemetryRecord(
        schema_version=1,
        session_id="walk_1",
        device_id="android_1",
        record_id="r1",
        sequence_number=7,
        record_type=record_type,
        client_timestamp="2026-05-27T14:05:31-07:00",
        payload=payload,
    )


def test_local_state_from_record_maps_android_sample():
    state = local_state_from_record(
        record(
            {
                "ssid": "corp-wifi",
                "bssid": "aa:bb:cc:dd:ee:ff",
                "channel": "36",
                "rssi": -63,
                "tx_link_mbps": 432,
                "rx_link_mbps": 390,
                "ipv4_address": "192.0.2.45",
                "gateway": "192.0.2.1",
                "probes": {"gateway": {"ok": True, "latency_ms": 8}},
            }
        )
    )

    assert state.platform == "android"
    assert state.ssid == "corp-wifi"
    assert state.signal == "-63"
    assert state.tx_rate == "432"
    assert state.ping_status == "gateway ok 8ms"


def test_event_from_record_maps_bssid_change():
    event = event_from_record(
        record(
            {
                "event_type": "bssid-change",
                "previous_bssid": "aa:bb:cc:dd:ee:ff",
                "current_bssid": "11:22:33:44:55:66",
                "rssi": -61,
                "channel": "44",
            },
            record_type="event",
        )
    )

    assert event is not None
    assert event.type == "bssid-change"
    assert event.current_bssid == "11:22:33:44:55:66"
```

Create `tests/test_probe_csv_logger.py`:

```python
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
            payload={"ssid": "corp-wifi", "bssid": "aa:bb:cc:dd:ee:ff", "rssi": -63},
        ),
        status="accepted",
    )
    logger.close()

    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert rows[0]["session_id"] == "walk_1"
    assert rows[0]["record_id"] == "r1"
    assert rows[0]["local_ssid"] == "corp-wifi"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_probe_adapters.py tests/test_probe_csv_logger.py -v
```

Expected: FAIL because adapter and CSV modules do not exist.

- [ ] **Step 3: Implement adapter and receiver-owned CSV writer**

Create `wifiops_probe/adapters.py`:

```python
from __future__ import annotations

from datetime import datetime

from client_tracker.models import LocalClientState, TrackerEvent

from .models import AndroidTelemetryRecord


def local_state_from_record(record: AndroidTelemetryRecord) -> LocalClientState:
    payload = record.payload
    return LocalClientState(
        ssid=_string(payload.get("ssid")),
        bssid=_string(payload.get("bssid")),
        channel=_string(payload.get("channel") or payload.get("frequency_mhz")),
        tx_rate=_string(payload.get("tx_link_mbps") or payload.get("link_mbps")),
        rx_rate=_string(payload.get("rx_link_mbps")),
        signal=_string(payload.get("rssi")),
        security=_string(payload.get("security")),
        phy_mode=_string(payload.get("wifi_standard")),
        ipv4_address=_string(payload.get("ipv4_address")),
        ipv4_router=_string(payload.get("gateway")),
        ping_status=_probe_summary(payload.get("probes", {})),
        platform="android",
        timestamp=datetime.now(),
    )


def event_from_record(record: AndroidTelemetryRecord) -> TrackerEvent | None:
    if record.record_type != "event":
        return None
    payload = record.payload
    event_type = _string(payload.get("event_type"))
    now = datetime.now()
    if event_type == "bssid-change":
        previous = _string(payload.get("previous_bssid"))
        current = _string(payload.get("current_bssid"))
        return TrackerEvent(
            timestamp=now,
            source="local",
            type="bssid-change",
            message=f"Android BSSID changed from {previous} to {current}",
            previous_bssid=previous,
            current_bssid=current,
            rssi=_string(payload.get("rssi")),
            channel=_string(payload.get("channel")),
        )
    if event_type == "disassociated":
        return TrackerEvent(now, "local", "disassociated", "Android client disassociated")
    if event_type == "associated":
        current = _string(payload.get("current_bssid") or payload.get("bssid"))
        return TrackerEvent(now, "local", "associated", f"Android client associated to {current}", current_bssid=current)
    if event_type == "session-started":
        return TrackerEvent(now, "system", "startup", "Android probe session started")
    if event_type == "session-stopped":
        return TrackerEvent(now, "system", "shutdown", "Android probe session stopped")
    if event_type in ("probe-failed", "upload-failed"):
        return TrackerEvent(now, "local", "poll-error", f"Android {event_type}", error=event_type)
    if event_type in ("probe-recovered", "upload-recovered"):
        return TrackerEvent(now, "local", "poll-recovered", f"Android {event_type}")
    return None


def _string(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _probe_summary(probes: object) -> str:
    if not isinstance(probes, dict):
        return ""
    gateway = probes.get("gateway")
    if isinstance(gateway, dict) and gateway.get("ok"):
        latency = gateway.get("latency_ms")
        return f"gateway ok {latency}ms" if latency is not None else "gateway ok"
    if isinstance(gateway, dict):
        return "gateway failed"
    return ""
```

Create `wifiops_probe/csv_logger.py`:

```python
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .models import AndroidTelemetryRecord

ANDROID_CSV_COLUMNS = [
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
    "local_signal",
    "local_ipv4_address",
    "gateway",
    "probe_gateway",
    "probe_dns",
    "probe_http",
    "event_type",
]


class AndroidCSVLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not self.path.exists()
        self._fh = self.path.open("a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=ANDROID_CSV_COLUMNS)
        if new_file:
            self._writer.writeheader()
            self._fh.flush()

    def write_record(self, record: AndroidTelemetryRecord, status: str):
        payload = record.payload
        probes = payload.get("probes", {})
        row: dict[str, Any] = {column: "" for column in ANDROID_CSV_COLUMNS}
        row.update(
            {
                "session_id": record.session_id,
                "device_id": record.device_id,
                "record_id": record.record_id,
                "sequence_number": record.sequence_number,
                "record_type": record.record_type,
                "client_timestamp": record.client_timestamp,
                "status": status,
                "local_ssid": payload.get("ssid", ""),
                "local_bssid": payload.get("bssid", ""),
                "local_channel": payload.get("channel", ""),
                "local_signal": payload.get("rssi", ""),
                "local_ipv4_address": payload.get("ipv4_address", ""),
                "gateway": payload.get("gateway", ""),
                "probe_gateway": _probe_cell(probes, "gateway"),
                "probe_dns": _probe_cell(probes, "dns"),
                "probe_http": _probe_cell(probes, "http"),
                "event_type": payload.get("event_type", ""),
            }
        )
        self._writer.writerow(row)
        self._fh.flush()

    def close(self):
        self._fh.close()


def _probe_cell(probes: object, name: str) -> str:
    if not isinstance(probes, dict):
        return ""
    value = probes.get(name)
    if not isinstance(value, dict):
        return ""
    ok = "ok" if value.get("ok") else "failed"
    latency = value.get("latency_ms")
    return f"{ok} {latency}ms" if latency is not None else ok
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
pytest tests/test_probe_adapters.py tests/test_probe_csv_logger.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wifiops_probe/adapters.py wifiops_probe/csv_logger.py tests/test_probe_adapters.py tests/test_probe_csv_logger.py
git commit -m "Map Android probe records to wifiops state"
```

---

### Task 4: HTTP Receiver

**Files:**
- Create: `wifiops_probe/http_server.py`
- Test: `tests/test_probe_http_server.py`

- [ ] **Step 1: Write failing HTTP handler tests**

Create `tests/test_probe_http_server.py`:

```python
from __future__ import annotations

import json
import threading
from http.client import HTTPConnection

from wifiops_probe.http_server import ProbeHTTPServer, ProbeRequestHandler
from wifiops_probe.state import ReceiverSession


def sample_body(record_id: str = "r1") -> str:
    return json.dumps(
        {
            "records": [
                {
                    "schema_version": 1,
                    "session_id": "walk_1",
                    "device_id": "android_1",
                    "record_id": record_id,
                    "sequence_number": 1,
                    "record_type": "sample",
                    "client_timestamp": "2026-05-27T14:05:31-07:00",
                    "payload": {"ssid": "corp-wifi"},
                }
            ]
        }
    )


def start_server():
    session = ReceiverSession(session_id="walk_1", token="secret")
    server = ProbeHTTPServer(("127.0.0.1", 0), ProbeRequestHandler, session=session)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_health_endpoint_returns_ok():
    server, _thread = start_server()
    conn = HTTPConnection("127.0.0.1", server.server_port)

    conn.request("GET", "/health")
    response = conn.getresponse()
    body = json.loads(response.read())
    server.shutdown()

    assert response.status == 200
    assert body["ok"] is True


def test_records_endpoint_requires_bearer_token():
    server, _thread = start_server()
    conn = HTTPConnection("127.0.0.1", server.server_port)

    conn.request("POST", "/api/v1/sessions/walk_1/records", body=sample_body(), headers={"Content-Type": "application/json"})
    response = conn.getresponse()
    server.shutdown()

    assert response.status == 401


def test_records_endpoint_accepts_valid_record_and_deduplicates():
    server, _thread = start_server()
    conn = HTTPConnection("127.0.0.1", server.server_port)
    headers = {"Content-Type": "application/json", "Authorization": "Bearer secret"}

    conn.request("POST", "/api/v1/sessions/walk_1/records", body=sample_body("r1"), headers=headers)
    first = json.loads(conn.getresponse().read())
    conn.request("POST", "/api/v1/sessions/walk_1/records", body=sample_body("r1"), headers=headers)
    second = json.loads(conn.getresponse().read())
    server.shutdown()

    assert first["accepted"] == ["r1"]
    assert second["duplicate"] == ["r1"]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_probe_http_server.py -v
```

Expected: FAIL because `wifiops_probe.http_server` does not exist.

- [ ] **Step 3: Implement standard-library HTTP receiver**

Create `wifiops_probe/http_server.py`:

```python
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .models import MAX_BODY_BYTES, TelemetryValidationError, parse_record_batch
from .security import parse_bearer_token
from .state import ReceiverSession


class ProbeHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, session: ReceiverSession, csv_logger=None):
        super().__init__(server_address, RequestHandlerClass)
        self.session = session
        self.csv_logger = csv_logger


class ProbeRequestHandler(BaseHTTPRequestHandler):
    server: ProbeHTTPServer

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True, "session_id": self.server.session.session_id})
            return
        if self.path == f"/api/v1/sessions/{self.server.session.session_id}/latest":
            latest = self.server.session.latest_record
            self._json(200, {"record_id": latest.record_id if latest else "", "device_id": self.server.session.device_id})
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self):
        expected = f"/api/v1/sessions/{self.server.session.session_id}/records"
        if self.path != expected:
            self._json(404, {"error": "not_found"})
            return
        if parse_bearer_token(self.headers.get("Authorization", "")) != self.server.session.token:
            self._json(401, {"error": "unauthorized"})
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > MAX_BODY_BYTES:
            self._json(413, {"error": "body_too_large"})
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            records = parse_record_batch(body)
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid_json"})
            return
        except TelemetryValidationError as exc:
            self._json(400, {"error": exc.code, "message": exc.message})
            return
        response: dict[str, list[Any]] = {"accepted": [], "duplicate": [], "rejected": []}
        for record in records:
            status = self.server.session.ingest(record)
            if status == "accepted":
                response["accepted"].append(record.record_id)
                if self.server.csv_logger:
                    self.server.csv_logger.write_record(record, status)
            elif status == "duplicate":
                response["duplicate"].append(record.record_id)
            else:
                response["rejected"].append({"record_id": record.record_id, "error": status})
        self._json(200, response)

    def log_message(self, _format: str, *_args):
        return

    def _json(self, status: int, payload: dict[str, Any]):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
pytest tests/test_probe_http_server.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wifiops_probe/http_server.py tests/test_probe_http_server.py
git commit -m "Add Android probe HTTP receiver"
```

---

### Task 5: wifiops CLI Integration

**Files:**
- Create: `wifiops_probe/cli.py`
- Create: `wifiops_probe/display.py`
- Modify: `wifiops/cli.py`
- Modify: `pyproject.toml`
- Test: `tests/test_wifiops_cli.py`
- Test: `tests/test_probe_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_wifiops_cli.py`:

```python
def test_probe_receive_delegates_to_probe_cli():
    probe_main = Mock(return_value=0)

    with patch("wifiops_probe.cli.main", probe_main):
        exit_code = main(["probe", "receive", "--pair", "--host", "127.0.0.1", "--port", "8765"])

    assert exit_code == 0
    probe_main.assert_called_once_with(["--pair", "--host", "127.0.0.1", "--port", "8765"])
```

Create `tests/test_probe_cli.py`:

```python
from __future__ import annotations

from wifiops_probe.cli import build_parser


def test_probe_receive_parser_defaults_to_loopback():
    args = build_parser().parse_args(["--pair"])

    assert args.pair is True
    assert args.host == "127.0.0.1"
    assert args.port == 8765
    assert args.advertise_host == ""


def test_probe_receive_parser_accepts_log_and_advertise_host():
    args = build_parser().parse_args(
        ["--pair", "--host", "0.0.0.0", "--advertise-host", "192.0.2.10", "--log", "walk.csv"]
    )

    assert args.host == "0.0.0.0"
    assert args.advertise_host == "192.0.2.10"
    assert args.log == "walk.csv"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_wifiops_cli.py::test_probe_receive_delegates_to_probe_cli tests/test_probe_cli.py -v
```

Expected: FAIL because `probe` command and `wifiops_probe.cli` do not exist.

- [ ] **Step 3: Add probe receive CLI and router**

Create `wifiops_probe/display.py`:

```python
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
```

Create `wifiops_probe/cli.py`:

```python
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .csv_logger import AndroidCSVLogger
from .http_server import ProbeHTTPServer, ProbeRequestHandler
from .security import generate_token, redact_token
from .state import ReceiverSession


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Receive Android wifiops probe telemetry.")
    parser.add_argument("--pair", action="store_true", required=True, help="Create a QR/manual pairing session")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Use 0.0.0.0 or an interface IP for phone access.")
    parser.add_argument("--port", type=int, default=8765, help="Bind port")
    parser.add_argument("--advertise-host", default="", help="Host/IP encoded into the pairing URL")
    parser.add_argument("--log", help="Optional Android telemetry CSV log path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    token = generate_token()
    session = ReceiverSession(session_id="walk_1", token=token)
    logger = AndroidCSVLogger(args.log) if args.log else None
    advertised_host = args.advertise_host or args.host
    if args.host not in ("127.0.0.1", "localhost"):
        print(f"Warning: receiver is exposed on {args.host}:{args.port}. Use only on trusted LANs.")
    print(f"Receiver URL: http://{advertised_host}:{args.port}")
    print(f"Session: {session.session_id}")
    print(f"Token: {redact_token(token)}")
    server = ProbeHTTPServer((args.host, args.port), ProbeRequestHandler, session=session, csv_logger=logger)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        if logger:
            logger.close()
    return 0
```

Modify `wifiops/cli.py`:

```python
# Add near other top-level subcommands in build_parser()
probe = subcommands.add_parser("probe", help="Android probe telemetry receiver")
probe_subcommands = probe.add_subparsers(dest="probe_command", required=True)
receive = probe_subcommands.add_parser("receive", help="Receive Android probe telemetry")
receive.add_argument("--pair", action="store_true", required=True, help="Create a pairing session")
receive.add_argument("--host", default="127.0.0.1", help="Bind host")
receive.add_argument("--port", type=int, default=8765, help="Bind port")
receive.add_argument("--advertise-host", default="", help="Host/IP encoded into pairing URL")
receive.add_argument("--log", help="Optional Android telemetry CSV log path")
```

```python
# Add in main() before parser.error()
if args.command == "probe" and args.probe_command == "receive":
    from wifiops_probe.cli import main as probe_main

    return _exit_code(probe_main(_delegated_args(argv, "receive")))
```

Modify `pyproject.toml` package discovery:

```toml
[tool.setuptools.packages.find]
include = ["ap_radio_monitor*", "ap_port_audit*", "ap_filesystem_audit*", "client_tracker*", "wifiops*", "wifiops_probe*"]
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
pytest tests/test_wifiops_cli.py::test_probe_receive_delegates_to_probe_cli tests/test_probe_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Run full Python test suite**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add wifiops/cli.py pyproject.toml wifiops_probe/cli.py wifiops_probe/display.py tests/test_wifiops_cli.py tests/test_probe_cli.py
git commit -m "Add wifiops Android probe receiver command"
```

---

### Task 6: Android Project Scaffold

**Files:**
- Create: `android/wifiops-probe/settings.gradle.kts`
- Create: `android/wifiops-probe/build.gradle.kts`
- Create: `android/wifiops-probe/app/build.gradle.kts`
- Create: `android/wifiops-probe/app/src/main/AndroidManifest.xml`
- Create: `android/wifiops-probe/app/src/main/res/xml/network_security_config.xml`
- Create: `android/wifiops-probe/app/src/main/java/com/wifiops/probe/MainActivity.kt`

- [ ] **Step 1: Create Gradle Android project files**

Create `android/wifiops-probe/settings.gradle.kts`:

```kotlin
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "WifiOpsProbe"
include(":app")
```

Create `android/wifiops-probe/build.gradle.kts`:

```kotlin
plugins {
    id("com.android.application") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "2.0.21" apply false
    id("com.google.devtools.ksp") version "2.0.21-1.0.28" apply false
}
```

Create `android/wifiops-probe/app/build.gradle.kts`:

```kotlin
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
    id("com.google.devtools.ksp")
}

android {
    namespace = "com.wifiops.probe"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.wifiops.probe"
        minSdk = 29
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
}

dependencies {
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.compose.material3:material3:1.3.1")
    implementation("androidx.compose.ui:ui:1.7.5")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
    implementation("com.google.mlkit:barcode-scanning:17.3.0")
    ksp("androidx.room:room-compiler:2.6.1")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.9.0")
}
```

- [ ] **Step 2: Add manifest and network security config**

Create `android/wifiops-probe/app/src/main/AndroidManifest.xml`:

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
    <uses-permission
        android:name="android.permission.NEARBY_WIFI_DEVICES"
        android:usesPermissionFlags="neverForLocation" />
    <uses-permission
        android:name="android.permission.ACCESS_FINE_LOCATION"
        android:maxSdkVersion="32" />

    <application
        android:allowBackup="false"
        android:label="wifiops probe"
        android:networkSecurityConfig="@xml/network_security_config"
        android:theme="@style/AppTheme">
        <service
            android:name=".service.ProbeForegroundService"
            android:exported="false"
            android:foregroundServiceType="dataSync" />
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

Create `android/wifiops-probe/app/src/main/res/xml/network_security_config.xml`:

```xml
<network-security-config>
    <base-config cleartextTrafficPermitted="false" />
    <debug-overrides>
        <trust-anchors>
            <certificates src="user" />
            <certificates src="system" />
        </trust-anchors>
    </debug-overrides>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">localhost</domain>
        <domain includeSubdomains="false">127.0.0.1</domain>
    </domain-config>
</network-security-config>
```

- [ ] **Step 3: Add minimal activity**

Create `android/wifiops-probe/app/src/main/java/com/wifiops/probe/MainActivity.kt`:

```kotlin
package com.wifiops.probe

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface {
                    Text("wifiops probe")
                }
            }
        }
    }
}
```

- [ ] **Step 4: Build Android project**

Run:

```bash
cd android/wifiops-probe
./gradlew testDebugUnitTest
```

Expected: PASS. If the Gradle wrapper does not exist, generate or install it using the local Android Studio/Gradle workflow, then commit `gradlew`, `gradlew.bat`, and `gradle/wrapper/gradle-wrapper.properties`.

- [ ] **Step 5: Commit**

```bash
git add android/wifiops-probe
git commit -m "Scaffold Android wifiops probe app"
```

---

### Task 7: Android Data Contract And Room Store

**Files:**
- Create: `android/wifiops-probe/app/src/main/java/com/wifiops/probe/data/TelemetryModels.kt`
- Create: `android/wifiops-probe/app/src/main/java/com/wifiops/probe/data/ProbeDatabase.kt`
- Create: `android/wifiops-probe/app/src/main/java/com/wifiops/probe/data/ProbeRecordDao.kt`
- Test: `android/wifiops-probe/app/src/test/java/com/wifiops/probe/data/TelemetryModelsTest.kt`

- [ ] **Step 1: Write serialization test**

Create `android/wifiops-probe/app/src/test/java/com/wifiops/probe/data/TelemetryModelsTest.kt`:

```kotlin
package com.wifiops.probe.data

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Test

class TelemetryModelsTest {
    @Test
    fun sampleRecordSerializesWithSnakeCaseContract() {
        val record = TelemetryRecord(
            schemaVersion = 1,
            sessionId = "walk_1",
            deviceId = "android_1",
            recordId = "r1",
            sequenceNumber = 1,
            recordType = "sample",
            clientTimestamp = "2026-05-27T14:05:31-07:00",
            appVersion = "0.1.0",
            androidApiLevel = 35,
            payload = TelemetryPayload(ssid = "corp-wifi", rssi = -63)
        )

        val json = Json.encodeToString(TelemetryRecord.serializer(), record)

        assertEquals(true, json.contains("\"schema_version\":1"))
        assertEquals(true, json.contains("\"session_id\":\"walk_1\""))
        assertEquals(true, json.contains("\"rssi\":-63"))
    }
}
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd android/wifiops-probe
./gradlew testDebugUnitTest --tests com.wifiops.probe.data.TelemetryModelsTest
```

Expected: FAIL because data models do not exist.

- [ ] **Step 3: Add Kotlin telemetry models and Room entities**

Create `android/wifiops-probe/app/src/main/java/com/wifiops/probe/data/TelemetryModels.kt`:

```kotlin
package com.wifiops.probe.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class TelemetryRecord(
    @SerialName("schema_version") val schemaVersion: Int,
    @SerialName("session_id") val sessionId: String,
    @SerialName("device_id") val deviceId: String,
    @SerialName("record_id") val recordId: String,
    @SerialName("sequence_number") val sequenceNumber: Long,
    @SerialName("record_type") val recordType: String,
    @SerialName("client_timestamp") val clientTimestamp: String,
    @SerialName("app_version") val appVersion: String,
    @SerialName("android_api_level") val androidApiLevel: Int,
    val payload: TelemetryPayload
)

@Serializable
data class TelemetryPayload(
    val ssid: String? = null,
    val bssid: String? = null,
    val rssi: Int? = null,
    @SerialName("frequency_mhz") val frequencyMhz: Int? = null,
    val channel: String? = null,
    @SerialName("tx_link_mbps") val txLinkMbps: Int? = null,
    @SerialName("rx_link_mbps") val rxLinkMbps: Int? = null,
    @SerialName("ipv4_address") val ipv4Address: String? = null,
    val gateway: String? = null,
    val dns: List<String> = emptyList(),
    val availability: Map<String, String> = emptyMap()
)
```

Create `ProbeDatabase.kt`:

```kotlin
package com.wifiops.probe.data

import androidx.room.Database
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import androidx.room.RoomDatabase

@Entity(tableName = "sessions")
data class SessionEntity(
    @PrimaryKey val sessionId: String,
    val receiverUrl: String,
    val token: String,
    val deviceId: String,
    val createdAtMillis: Long,
    val stoppedAtMillis: Long? = null
)

@Entity(
    tableName = "records",
    indices = [
        Index(value = ["sessionId", "sequenceNumber"]),
        Index(value = ["syncStatus"]),
        Index(value = ["recordId"], unique = true)
    ]
)
data class RecordEntity(
    @PrimaryKey val recordId: String,
    val sessionId: String,
    val sequenceNumber: Long,
    val recordType: String,
    val payloadJson: String,
    val syncStatus: String,
    val retryCount: Int = 0,
    val lastError: String = "",
    val createdAtMillis: Long
)

@Database(entities = [SessionEntity::class, RecordEntity::class], version = 1)
abstract class ProbeDatabase : RoomDatabase() {
    abstract fun probeRecordDao(): ProbeRecordDao
}
```

Create `ProbeRecordDao.kt`:

```kotlin
package com.wifiops.probe.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface ProbeRecordDao {
    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertSession(session: SessionEntity)

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertRecord(record: RecordEntity)

    @Query("SELECT * FROM records WHERE sessionId = :sessionId AND syncStatus = 'pending' ORDER BY sequenceNumber LIMIT :limit")
    suspend fun pendingRecords(sessionId: String, limit: Int): List<RecordEntity>

    @Query("UPDATE records SET syncStatus = :status, lastError = :lastError WHERE recordId = :recordId")
    suspend fun updateRecordStatus(recordId: String, status: String, lastError: String = "")

    @Query("UPDATE records SET retryCount = retryCount + 1, lastError = :lastError WHERE recordId = :recordId")
    suspend fun markRetry(recordId: String, lastError: String)

    @Query("SELECT COUNT(*) FROM records WHERE sessionId = :sessionId AND syncStatus = :status")
    suspend fun countByStatus(sessionId: String, status: String): Int
}
```

- [ ] **Step 4: Run Android unit tests**

Run:

```bash
cd android/wifiops-probe
./gradlew testDebugUnitTest
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add android/wifiops-probe/app/src/main/java/com/wifiops/probe/data android/wifiops-probe/app/src/test/java/com/wifiops/probe/data
git commit -m "Add Android probe telemetry store"
```

---

### Task 8: Android Foreground Collection Service

**Files:**
- Create: `android/wifiops-probe/app/src/main/java/com/wifiops/probe/service/ProbeForegroundService.kt`
- Create: `android/wifiops-probe/app/src/main/java/com/wifiops/probe/telemetry/WifiTelemetryCollector.kt`
- Create: `android/wifiops-probe/app/src/main/java/com/wifiops/probe/telemetry/ActiveProbeRunner.kt`
- Test: `android/wifiops-probe/app/src/test/java/com/wifiops/probe/telemetry/WifiTelemetryCollectorTest.kt`

- [ ] **Step 1: Write collector unit tests for channel conversion and nullable fields**

Create `android/wifiops-probe/app/src/test/java/com/wifiops/probe/telemetry/WifiTelemetryCollectorTest.kt`:

```kotlin
package com.wifiops.probe.telemetry

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class WifiTelemetryCollectorTest {
    @Test
    fun channelFromFrequencyHandlesFiveGhz() {
        assertEquals("36", channelFromFrequency(5180))
    }

    @Test
    fun channelFromFrequencyReturnsNullForUnknownFrequency() {
        assertNull(channelFromFrequency(null))
        assertNull(channelFromFrequency(1234))
    }
}
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd android/wifiops-probe
./gradlew testDebugUnitTest --tests com.wifiops.probe.telemetry.WifiTelemetryCollectorTest
```

Expected: FAIL because telemetry collector does not exist.

- [ ] **Step 3: Implement collector helpers and service shell**

Create `WifiTelemetryCollector.kt`:

```kotlin
package com.wifiops.probe.telemetry

import android.net.ConnectivityManager
import android.net.LinkProperties
import android.net.wifi.WifiInfo
import android.net.wifi.WifiManager
import com.wifiops.probe.data.TelemetryPayload

fun channelFromFrequency(frequencyMhz: Int?): String? {
    if (frequencyMhz == null) return null
    return when (frequencyMhz) {
        in 2412..2472 -> ((frequencyMhz - 2407) / 5).toString()
        2484 -> "14"
        in 5000..5895 -> ((frequencyMhz - 5000) / 5).toString()
        in 5925..7125 -> ((frequencyMhz - 5950) / 5).toString()
        else -> null
    }
}

class WifiTelemetryCollector(
    private val wifiManager: WifiManager,
    private val connectivityManager: ConnectivityManager
) {
    fun collect(): TelemetryPayload {
        val info: WifiInfo? = wifiManager.connectionInfo
        val activeNetwork = connectivityManager.activeNetwork
        val linkProperties: LinkProperties? = activeNetwork?.let { connectivityManager.getLinkProperties(it) }
        val frequency = info?.frequency
        val availability = mutableMapOf<String, String>()
        val ssid = info?.ssid?.trim('"')?.takeUnless { it == "<unknown ssid>" }
        val bssid = info?.bssid?.takeUnless { it == "02:00:00:00:00:00" }
        if (ssid == null) availability["ssid"] = "unavailable_or_redacted"
        if (bssid == null) availability["bssid"] = "unavailable_or_redacted"
        return TelemetryPayload(
            ssid = ssid,
            bssid = bssid,
            rssi = info?.rssi,
            frequencyMhz = frequency,
            channel = channelFromFrequency(frequency),
            txLinkMbps = info?.txLinkSpeedMbps,
            rxLinkMbps = info?.rxLinkSpeedMbps,
            gateway = linkProperties?.routes?.firstOrNull { it.isDefaultRoute }?.gateway?.hostAddress,
            dns = linkProperties?.dnsServers?.mapNotNull { it.hostAddress } ?: emptyList(),
            availability = availability
        )
    }
}
```

Create `ActiveProbeRunner.kt`:

```kotlin
package com.wifiops.probe.telemetry

import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.net.URL
import kotlin.system.measureTimeMillis

data class ProbeResult(val ok: Boolean, val latencyMs: Long? = null, val detail: String = "")

class ActiveProbeRunner {
    suspend fun tcpConnect(host: String, port: Int, timeoutMs: Int = 1000): ProbeResult {
        var ok = false
        val elapsed = measureTimeMillis {
            Socket().use { socket ->
                socket.connect(InetSocketAddress(host, port), timeoutMs)
                ok = true
            }
        }
        return ProbeResult(ok = ok, latencyMs = elapsed)
    }

    suspend fun dnsLookup(hostname: String): ProbeResult {
        var addresses = 0
        val elapsed = measureTimeMillis {
            addresses = InetAddress.getAllByName(hostname).size
        }
        return ProbeResult(ok = addresses > 0, latencyMs = elapsed, detail = hostname)
    }

    suspend fun httpGet(url: String, timeoutMs: Int = 2000): ProbeResult {
        var status = 0
        val elapsed = measureTimeMillis {
            val connection = URL(url).openConnection() as HttpURLConnection
            connection.connectTimeout = timeoutMs
            connection.readTimeout = timeoutMs
            connection.requestMethod = "GET"
            status = connection.responseCode
            connection.disconnect()
        }
        return ProbeResult(ok = status in 200..399, latencyMs = elapsed, detail = status.toString())
    }
}
```

Create `ProbeForegroundService.kt`:

```kotlin
package com.wifiops.probe.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.wifiops.probe.R

class ProbeForegroundService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(1001, notification("wifiops walk test running"))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    override fun onDestroy() {
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel("probe", "wifiops probe", NotificationManager.IMPORTANCE_LOW)
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun notification(text: String): Notification =
        NotificationCompat.Builder(this, "probe")
            .setContentTitle("wifiops probe")
            .setContentText(text)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setOngoing(true)
            .build()
}
```

- [ ] **Step 4: Run Android unit tests**

Run:

```bash
cd android/wifiops-probe
./gradlew testDebugUnitTest
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add android/wifiops-probe/app/src/main/java/com/wifiops/probe/service android/wifiops-probe/app/src/main/java/com/wifiops/probe/telemetry android/wifiops-probe/app/src/test/java/com/wifiops/probe/telemetry
git commit -m "Add Android probe foreground collection"
```

---

### Task 9: Android Sync Engine

**Files:**
- Create: `android/wifiops-probe/app/src/main/java/com/wifiops/probe/sync/ProbeSyncClient.kt`
- Create: `android/wifiops-probe/app/src/main/java/com/wifiops/probe/sync/ProbeSyncWorker.kt`
- Test: `android/wifiops-probe/app/src/test/java/com/wifiops/probe/sync/ProbeSyncClientTest.kt`

- [ ] **Step 1: Write sync acknowledgement parsing tests**

Create `ProbeSyncClientTest.kt`:

```kotlin
package com.wifiops.probe.sync

import org.junit.Assert.assertEquals
import org.junit.Test

class ProbeSyncClientTest {
    @Test
    fun acknowledgementParsesAcceptedDuplicateAndRejectedRecords() {
        val ack = ProbeSyncClient.parseAcknowledgement(
            """
            {
              "accepted": ["r1"],
              "duplicate": ["r2"],
              "rejected": [{"record_id": "r3", "error": "missing_payload"}]
            }
            """.trimIndent()
        )

        assertEquals(listOf("r1"), ack.accepted)
        assertEquals(listOf("r2"), ack.duplicate)
        assertEquals("missing_payload", ack.rejected.first().error)
    }
}
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd android/wifiops-probe
./gradlew testDebugUnitTest --tests com.wifiops.probe.sync.ProbeSyncClientTest
```

Expected: FAIL because sync client does not exist.

- [ ] **Step 3: Implement sync client and worker**

Create `ProbeSyncClient.kt`:

```kotlin
package com.wifiops.probe.sync

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

@Serializable
data class RejectedRecord(@SerialName("record_id") val recordId: String, val error: String)

@Serializable
data class ProbeAcknowledgement(
    val accepted: List<String> = emptyList(),
    val duplicate: List<String> = emptyList(),
    val rejected: List<RejectedRecord> = emptyList()
)

class ProbeSyncClient(private val http: OkHttpClient = OkHttpClient()) {
    fun health(receiverUrl: String): Boolean {
        val request = Request.Builder().url("$receiverUrl/health").get().build()
        http.newCall(request).execute().use { response -> return response.isSuccessful }
    }

    fun upload(receiverUrl: String, sessionId: String, token: String, recordsJson: String): ProbeAcknowledgement {
        val body = recordsJson.toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("$receiverUrl/api/v1/sessions/$sessionId/records")
            .header("Authorization", "Bearer $token")
            .post(body)
            .build()
        http.newCall(request).execute().use { response ->
            if (!response.isSuccessful) error("upload failed with HTTP ${response.code}")
            return parseAcknowledgement(response.body?.string().orEmpty())
        }
    }

    companion object {
        fun parseAcknowledgement(raw: String): ProbeAcknowledgement =
            Json { ignoreUnknownKeys = true }.decodeFromString(ProbeAcknowledgement.serializer(), raw)
    }
}
```

Create `ProbeSyncWorker.kt`:

```kotlin
package com.wifiops.probe.sync

import com.wifiops.probe.data.ProbeRecordDao

class ProbeSyncWorker(
    private val dao: ProbeRecordDao,
    private val client: ProbeSyncClient
) {
    suspend fun syncOnce(sessionId: String, receiverUrl: String, token: String): Int {
        val records = dao.pendingRecords(sessionId, limit = 100)
        if (records.isEmpty()) return 0
        val recordsJson = records.joinToString(prefix = """{"records":[""", postfix = "]}", separator = ",") { it.payloadJson }
        return try {
            val ack = client.upload(receiverUrl, sessionId, token, recordsJson)
            (ack.accepted + ack.duplicate).forEach { dao.updateRecordStatus(it, "synced") }
            ack.rejected.forEach { dao.updateRecordStatus(it.recordId, "failed", it.error) }
            ack.accepted.size + ack.duplicate.size
        } catch (exc: Exception) {
            records.forEach { dao.markRetry(it.recordId, exc.message ?: "sync_failed") }
            0
        }
    }
}
```

- [ ] **Step 4: Run Android unit tests**

Run:

```bash
cd android/wifiops-probe
./gradlew testDebugUnitTest
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add android/wifiops-probe/app/src/main/java/com/wifiops/probe/sync android/wifiops-probe/app/src/test/java/com/wifiops/probe/sync
git commit -m "Add Android probe sync engine"
```

---

### Task 10: Android Pairing And Session UI

**Files:**
- Modify: `android/wifiops-probe/app/src/main/java/com/wifiops/probe/MainActivity.kt`
- Create: `android/wifiops-probe/app/src/main/java/com/wifiops/probe/ui/PairScreen.kt`
- Create: `android/wifiops-probe/app/src/main/java/com/wifiops/probe/ui/SessionScreen.kt`
- Create: `android/wifiops-probe/app/src/main/java/com/wifiops/probe/ui/SessionHistoryScreen.kt`
- Create: `android/wifiops-probe/app/src/main/java/com/wifiops/probe/pairing/PairingPayload.kt`
- Test: `android/wifiops-probe/app/src/test/java/com/wifiops/probe/pairing/PairingPayloadTest.kt`

- [ ] **Step 1: Write pairing payload parser test**

Create `PairingPayloadTest.kt`:

```kotlin
package com.wifiops.probe.pairing

import org.junit.Assert.assertEquals
import org.junit.Test

class PairingPayloadTest {
    @Test
    fun parsesPairingPayloadJson() {
        val payload = PairingPayload.parse(
            """{"receiver_url":"http://192.0.2.10:8765","session_id":"walk_1","token":"secret"}"""
        )

        assertEquals("http://192.0.2.10:8765", payload.receiverUrl)
        assertEquals("walk_1", payload.sessionId)
        assertEquals("secret", payload.token)
    }
}
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd android/wifiops-probe
./gradlew testDebugUnitTest --tests com.wifiops.probe.pairing.PairingPayloadTest
```

Expected: FAIL because pairing parser does not exist.

- [ ] **Step 3: Implement pairing parser and UI screens**

Create `PairingPayload.kt`:

```kotlin
package com.wifiops.probe.pairing

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

@Serializable
data class PairingPayload(
    @SerialName("receiver_url") val receiverUrl: String,
    @SerialName("session_id") val sessionId: String,
    val token: String
) {
    companion object {
        fun parse(raw: String): PairingPayload = Json.decodeFromString(serializer(), raw)
    }
}
```

Create `PairScreen.kt`:

```kotlin
package com.wifiops.probe.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember

@Composable
fun PairScreen(onPaired: (receiverUrl: String, sessionId: String, token: String) -> Unit) {
    val receiverUrl = remember { mutableStateOf("") }
    val sessionId = remember { mutableStateOf("") }
    val token = remember { mutableStateOf("") }
    Column {
        Text("Pair wifiops receiver")
        OutlinedTextField(value = receiverUrl.value, onValueChange = { receiverUrl.value = it }, label = { Text("Receiver URL") })
        OutlinedTextField(value = sessionId.value, onValueChange = { sessionId.value = it }, label = { Text("Session ID") })
        OutlinedTextField(value = token.value, onValueChange = { token.value = it }, label = { Text("Token") })
        Button(onClick = { onPaired(receiverUrl.value, sessionId.value, token.value) }) {
            Text("Use Receiver")
        }
    }
}
```

Create `SessionScreen.kt`:

```kotlin
package com.wifiops.probe.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable

data class SessionUiState(
    val ssid: String = "",
    val bssid: String = "",
    val rssi: String = "",
    val pending: Int = 0,
    val synced: Int = 0,
    val failed: Int = 0,
    val running: Boolean = false
)

@Composable
fun SessionScreen(state: SessionUiState, onStart: () -> Unit, onStop: () -> Unit) {
    Column {
        Text("SSID: ${state.ssid.ifBlank { "N/A" }}")
        Text("BSSID: ${state.bssid.ifBlank { "N/A" }}")
        Text("RSSI: ${state.rssi.ifBlank { "N/A" }}")
        Text("Synced: ${state.synced}  Pending: ${state.pending}  Failed: ${state.failed}")
        if (state.running) {
            Button(onClick = onStop) { Text("Stop Test") }
        } else {
            Button(onClick = onStart) { Text("Start Test") }
        }
    }
}
```

Create `SessionHistoryScreen.kt`:

```kotlin
package com.wifiops.probe.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable

data class SessionSummary(val sessionId: String, val pending: Int, val synced: Int, val failed: Int)

@Composable
fun SessionHistoryScreen(sessions: List<SessionSummary>, onDelete: (String) -> Unit, onExport: (String) -> Unit) {
    Column {
        sessions.forEach { session ->
            Text("${session.sessionId}: synced ${session.synced}, pending ${session.pending}, failed ${session.failed}")
            Button(onClick = { onExport(session.sessionId) }) { Text("Export") }
            Button(onClick = { onDelete(session.sessionId) }) { Text("Delete") }
        }
    }
}
```

Modify `MainActivity.kt` so it starts on `PairScreen`, stores the paired receiver values in activity state, and then shows `SessionScreen`. Add permission request handling for Nearby Wi-Fi Devices, Android 13 notification permission, and Android 10-12 fine location before starting `ProbeForegroundService`.

- [ ] **Step 4: Run Android unit tests**

Run:

```bash
cd android/wifiops-probe
./gradlew testDebugUnitTest
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add android/wifiops-probe/app/src/main/java/com/wifiops/probe android/wifiops-probe/app/src/test/java/com/wifiops/probe/pairing
git commit -m "Add Android probe pairing and session UI"
```

---

### Task 11: End-To-End Local Validation

**Files:**
- Create: `docs/android-probe-field-test.md`
- Modify: `README.md`

- [ ] **Step 1: Add field-test runbook**

Create `docs/android-probe-field-test.md`:

```markdown
# Android Probe Field Test

## Receiver

Start a receiver reachable from the phone:

```bash
wifiops probe receive --pair --host 0.0.0.0 --advertise-host <wifiops-machine-ip> --log walktest.csv
```

Use this only on trusted test networks. The receiver prints a LAN exposure warning when binding outside loopback.

## Phone

1. Install the debug APK.
2. Open wifiops probe.
3. Scan the pairing QR or enter receiver URL, session ID, and token manually.
4. Confirm the health check passes.
5. Tap Start Test.
6. Walk through the test area.
7. Roam, disable Wi-Fi briefly, or move out of coverage to verify local buffering.
8. Return to coverage and confirm pending records sync.
9. Tap Stop Test.

## Expected Results

- Receiver terminal shows Android local client state.
- BSSID changes appear as events.
- Upload failures do not stop local collection.
- Pending count falls to zero after connectivity returns.
- `walktest.csv` contains accepted records with sequence numbers.
```

- [ ] **Step 2: Update README with concise Android probe entry**

Add a short section to `README.md`:

```markdown
### Android Probe Receiver

`wifiops` can receive Android walk-test telemetry from the native wifiops probe app:

```bash
wifiops probe receive --pair --host 0.0.0.0 --advertise-host <wifiops-machine-ip> --log walktest.csv
```

The Android app runs an explicit foreground walk-test session, stores samples locally before upload, and retries pending records when the receiver becomes reachable again. See [Android Probe Field Test](docs/android-probe-field-test.md).
```

- [ ] **Step 3: Run Python and Android verification**

Run:

```bash
pytest -q
cd android/wifiops-probe
./gradlew testDebugUnitTest assembleDebug
```

Expected: Python tests PASS, Android unit tests PASS, debug APK builds.

- [ ] **Step 4: Manual smoke test**

Run:

```bash
wifiops probe receive --pair --host 127.0.0.1 --port 8765 --log /tmp/android-probe-smoke.csv
```

In a second terminal, POST one valid sample:

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token-from-dev-output-or-test-helper>' \
  http://127.0.0.1:8765/api/v1/sessions/walk_1/records \
  --data '{"records":[{"schema_version":1,"session_id":"walk_1","device_id":"android_1","record_id":"smoke_1","sequence_number":1,"record_type":"sample","client_timestamp":"2026-05-27T14:05:31-07:00","payload":{"ssid":"corp-wifi","bssid":"aa:bb:cc:dd:ee:ff","rssi":-63}}]}'
```

Expected: response includes `"accepted":["smoke_1"]`; CSV contains one row.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/android-probe-field-test.md
git commit -m "Document Android probe field validation"
```

---

## Plan Self-Review

- Spec coverage: the plan covers local receiver, cloud-ready JSON envelope, QR/manual pairing foundation, token validation, LAN exposure warning, nullable Android telemetry, offline Room storage, foreground service, active probes, sync retry, UI, CSV, and field validation.
- Scope check: this is a large feature spanning Python and Android. The first two implementation milestones should be treated as separate PRs if needed: Python receiver/API first, Android app second.
- Known execution risk: Android Gradle/plugin versions may need adjustment to match the local Android SDK. Keep that adjustment confined to `android/wifiops-probe` build files and record the final versions in the implementation commit.
