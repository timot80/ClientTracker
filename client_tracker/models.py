from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


Mode = Literal["infra", "local", "combined"]
EventSource = Literal["infra", "ap", "local", "system"]
EventType = Literal[
    "roam",
    "bssid-change",
    "disassociated",
    "associated",
    "poll-error",
    "poll-recovered",
    "startup",
    "shutdown",
]


@dataclass
class WLCClientState:
    mac: str = ""
    ap_name: str = ""
    ap_ip: str = ""
    ssid: str = ""
    protocol: str = ""
    state: str = ""
    rssi: str = ""
    snr: str = ""
    timestamp: datetime | None = None


@dataclass
class APClientState:
    mac: str = ""
    ap_name: str = ""
    rssi: str = ""
    channel: str = ""
    slot_id: str = ""
    ssid: str = ""
    mcs_rate: str = ""
    timestamp: datetime | None = None


@dataclass
class LocalClientState:
    interface_name: str = ""
    ssid: str = ""
    bssid: str = ""
    channel: str = ""
    tx_rate: str = ""
    rx_rate: str = ""
    signal: str = ""
    noise: str = ""
    cca: str = ""
    security: str = ""
    phy_mode: str = ""
    mcs_index: str = ""
    guard_interval: str = ""
    nss: str = ""
    country_code: str = ""
    ipv4_address: str = ""
    ipv4_router: str = ""
    ping_status: str = ""
    platform: str = ""
    timestamp: datetime | None = None


@dataclass
class TrackerEvent:
    timestamp: datetime
    source: EventSource
    type: EventType
    message: str
    previous_ap: str = ""
    current_ap: str = ""
    previous_bssid: str = ""
    current_bssid: str = ""
    rssi: str = ""
    channel: str = ""
    error: str = ""
