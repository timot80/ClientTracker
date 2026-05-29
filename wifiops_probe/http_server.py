from __future__ import annotations

import json
import socket
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from typing import Any

from .models import AndroidTelemetryRecord, MAX_BODY_BYTES, TelemetryValidationError, parse_record_batch
from .security import parse_bearer_token
from .state import ReceiverSession


class ProbeHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address,
        RequestHandlerClass,
        session: ReceiverSession,
        csv_logger=None,
        on_probe_connected: Callable[[AndroidTelemetryRecord], None] | None = None,
    ):
        super().__init__(server_address, RequestHandlerClass)
        self.session = session
        self.csv_logger = csv_logger
        self.on_probe_connected = on_probe_connected
        self._probe_connected_reported = False
        self._probe_connected_lock = Lock()

    def report_probe_connected(self, record: AndroidTelemetryRecord):
        if not self.on_probe_connected:
            return
        with self._probe_connected_lock:
            if self._probe_connected_reported:
                return
            self._probe_connected_reported = True
        self.on_probe_connected(record)


class ProbeIPv6HTTPServer(ProbeHTTPServer):
    address_family = socket.AF_INET6


class ProbeRequestHandler(BaseHTTPRequestHandler):
    server: ProbeHTTPServer

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True, "session_id": self.server.session.session_id})
            return
        if self.path == f"/api/v1/sessions/{self.server.session.session_id}/latest":
            latest = self.server.session.latest_record
            self._json(
                200,
                {
                    "record_id": latest.record_id if latest else "",
                    "device_id": latest.device_id if latest else self.server.session.device_id,
                },
            )
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self):
        expected_path = f"/api/v1/sessions/{self.server.session.session_id}/records"
        if self.path != expected_path:
            self._json(404, {"error": "not_found"})
            return
        if parse_bearer_token(self.headers.get("Authorization", "")) != self.server.session.token:
            self._json(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            self._json(400, {"error": "invalid_content_length"})
            return
        if length < 0:
            self._json(400, {"error": "invalid_content_length"})
            return
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
                self.server.report_probe_connected(record)
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
