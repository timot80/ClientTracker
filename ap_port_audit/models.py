from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ap_radio_monitor.models import WLCConfig


@dataclass(frozen=True)
class APPortAuditConfig:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    show_all: bool = False
    speed_threshold: int = 1000


@dataclass(frozen=True)
class APPortConfig:
    wlc: WLCConfig
    ap_ports: APPortAuditConfig = field(default_factory=APPortAuditConfig)


@dataclass(frozen=True)
class APPortRow:
    ap_name: str
    interface: str
    link_status: str
    speed_text: str
    speed_mbps: int | None
    duplex: str
    rx_packets: int | None = None
    tx_packets: int | None = None
    discarded_packets: int | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class APPortSnapshot:
    rows: list[APPortRow] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    parser_warnings: list[str] = field(default_factory=list)
    poll_error: str = ""
    error_excerpt: str = ""
    raw_command: str = "show ap ethernet statistics"
