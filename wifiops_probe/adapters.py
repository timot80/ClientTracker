from __future__ import annotations

from datetime import datetime
from typing import Any

from client_tracker.models import LocalClientState, TrackerEvent
from wifiops_probe.models import AndroidTelemetryRecord


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
        ping_status=_probe_summary(payload.get("probes")),
        platform="android",
        timestamp=datetime.now(),
    )


def event_from_record(record: AndroidTelemetryRecord) -> TrackerEvent | None:
    if record.record_type != "event":
        return None

    payload = record.payload
    event_type = payload.get("event_type")
    now = datetime.now()

    if event_type == "bssid-change":
        previous_bssid = _string(payload.get("previous_bssid"))
        current_bssid = _string(payload.get("current_bssid"))
        return TrackerEvent(
            timestamp=now,
            source="local",
            type="bssid-change",
            message=f"Android BSSID changed from {previous_bssid} to {current_bssid}",
            previous_bssid=previous_bssid,
            current_bssid=current_bssid,
            rssi=_string(payload.get("rssi")),
            channel=_string(payload.get("channel")),
        )
    if event_type == "disassociated":
        previous_bssid = _string(payload.get("previous_bssid") or payload.get("bssid"))
        return TrackerEvent(
            timestamp=now,
            source="local",
            type="disassociated",
            message="Android client disassociated",
            previous_bssid=previous_bssid,
        )
    if event_type == "associated":
        current_bssid = _string(payload.get("current_bssid") or payload.get("bssid"))
        return TrackerEvent(
            timestamp=now,
            source="local",
            type="associated",
            message=f"Android client associated to {current_bssid}",
            current_bssid=current_bssid,
            rssi=_string(payload.get("rssi")),
            channel=_string(payload.get("channel")),
        )
    if event_type == "session-started":
        return TrackerEvent(
            timestamp=now,
            source="system",
            type="startup",
            message="Android probe session started",
        )
    if event_type == "session-stopped":
        return TrackerEvent(
            timestamp=now,
            source="system",
            type="shutdown",
            message="Android probe session stopped",
        )
    if event_type in ("probe-failed", "upload-failed"):
        error = _string(payload.get("error") or payload.get("message"))
        return TrackerEvent(
            timestamp=now,
            source="local",
            type="poll-error",
            message=error or _string(event_type),
            error=error,
        )
    if event_type in ("probe-recovered", "upload-recovered"):
        return TrackerEvent(
            timestamp=now,
            source="local",
            type="poll-recovered",
            message=_string(payload.get("message")) or _string(event_type),
        )
    return None


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _probe_summary(probes: Any) -> str:
    if not isinstance(probes, dict):
        return ""
    gateway = probes.get("gateway")
    if not isinstance(gateway, dict):
        return ""
    if gateway.get("ok"):
        latency = gateway.get("latency_ms")
        if latency is None:
            return "gateway ok"
        return f"gateway ok {latency}ms"
    return "gateway failed"
