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
