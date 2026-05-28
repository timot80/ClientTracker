from __future__ import annotations

import json
import threading
from http.client import HTTPConnection

from wifiops_probe.http_server import ProbeHTTPServer, ProbeRequestHandler
from wifiops_probe.models import MAX_BODY_BYTES
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
                    "app_version": "0.1.0",
                    "android_api_level": 35,
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


def stop_server(server: ProbeHTTPServer):
    server.shutdown()
    server.server_close()


def test_health_endpoint_returns_ok():
    server, _thread = start_server()
    conn = HTTPConnection("127.0.0.1", server.server_port)

    try:
        conn.request("GET", "/health")
        response = conn.getresponse()
        body = json.loads(response.read())
    finally:
        conn.close()
        stop_server(server)

    assert response.status == 200
    assert body["ok"] is True
    assert body["session_id"] == "walk_1"


def test_records_endpoint_requires_bearer_token():
    server, _thread = start_server()
    conn = HTTPConnection("127.0.0.1", server.server_port)

    try:
        conn.request(
            "POST",
            "/api/v1/sessions/walk_1/records",
            body=sample_body(),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        response.read()
    finally:
        conn.close()
        stop_server(server)

    assert response.status == 401


def test_records_endpoint_accepts_valid_record_and_deduplicates():
    server, _thread = start_server()
    conn = HTTPConnection("127.0.0.1", server.server_port)
    headers = {"Content-Type": "application/json", "Authorization": "Bearer secret"}

    try:
        conn.request("POST", "/api/v1/sessions/walk_1/records", body=sample_body("r1"), headers=headers)
        first_response = conn.getresponse()
        first = json.loads(first_response.read())
        conn.request("POST", "/api/v1/sessions/walk_1/records", body=sample_body("r1"), headers=headers)
        second_response = conn.getresponse()
        second = json.loads(second_response.read())
    finally:
        conn.close()
        stop_server(server)

    assert first_response.status == 200
    assert first["accepted"] == ["r1"]
    assert first["duplicate"] == []
    assert first["rejected"] == []
    assert second_response.status == 200
    assert second["accepted"] == []
    assert second["duplicate"] == ["r1"]
    assert second["rejected"] == []


def test_records_endpoint_rejects_invalid_json():
    server, _thread = start_server()
    conn = HTTPConnection("127.0.0.1", server.server_port)

    try:
        conn.request(
            "POST",
            "/api/v1/sessions/walk_1/records",
            body="{",
            headers={"Content-Type": "application/json", "Authorization": "Bearer secret"},
        )
        response = conn.getresponse()
        body = json.loads(response.read())
    finally:
        conn.close()
        stop_server(server)

    assert response.status == 400
    assert body["error"] == "invalid_json"


def test_records_endpoint_rejects_body_larger_than_limit():
    server, _thread = start_server()
    conn = HTTPConnection("127.0.0.1", server.server_port)

    try:
        conn.request(
            "POST",
            "/api/v1/sessions/walk_1/records",
            body=b"{}",
            headers={
                "Authorization": "Bearer secret",
                "Content-Length": str(MAX_BODY_BYTES + 1),
                "Content-Type": "application/json",
            },
        )
        response = conn.getresponse()
        body = json.loads(response.read())
    finally:
        conn.close()
        stop_server(server)

    assert response.status == 413
    assert body["error"] == "body_too_large"
