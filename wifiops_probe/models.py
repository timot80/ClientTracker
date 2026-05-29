from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
    "app_version",
    "android_api_level",
    "payload",
)

REQUIRED_STRING_FIELDS = (
    "session_id",
    "device_id",
    "record_id",
    "client_timestamp",
    "app_version",
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
    app_version: str
    android_api_level: int


def parse_record_batch(body: Any) -> list[AndroidTelemetryRecord]:
    if not isinstance(body, dict):
        raise TelemetryValidationError("invalid_body", "request body must be a JSON object")
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
    if type(record["schema_version"]) is not int or record["schema_version"] != 1:
        raise TelemetryValidationError("unsupported_schema", "schema_version must be 1")
    if record["record_type"] not in ("sample", "event"):
        raise TelemetryValidationError("invalid_record_type", "record_type must be sample or event")
    for field in REQUIRED_STRING_FIELDS:
        if not isinstance(record[field], str) or not record[field]:
            raise TelemetryValidationError("invalid_string", f"{field} must be a non-empty string")
    if not isinstance(record["sequence_number"], int) or isinstance(record["sequence_number"], bool):
        raise TelemetryValidationError("invalid_sequence", "sequence_number must be an integer")
    if not isinstance(record["android_api_level"], int) or isinstance(record["android_api_level"], bool):
        raise TelemetryValidationError("invalid_android_api_level", "android_api_level must be an integer")
    if not isinstance(record["payload"], dict):
        raise TelemetryValidationError("invalid_payload", "payload must be an object")
    _validate_timestamp(record["client_timestamp"])
    return AndroidTelemetryRecord(
        schema_version=record["schema_version"],
        session_id=record["session_id"],
        device_id=record["device_id"],
        record_id=record["record_id"],
        sequence_number=record["sequence_number"],
        record_type=record["record_type"],
        client_timestamp=record["client_timestamp"],
        payload=record["payload"],
        app_version=record["app_version"],
        android_api_level=record["android_api_level"],
    )


def _validate_timestamp(timestamp: str):
    if timestamp.endswith("Z"):
        timestamp = f"{timestamp[:-1]}+00:00"
    try:
        datetime.fromisoformat(timestamp)
    except ValueError:
        raise TelemetryValidationError("invalid_timestamp", "client_timestamp must be an ISO 8601 timestamp") from None
