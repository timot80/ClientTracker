from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class WLCConfig:
    host: str
    username: str
    password: str
    enable: str = ""


@dataclass(frozen=True)
class APBalanceConfig:
    refresh_seconds: int = 30
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    included_slots: tuple[int, ...] = ()
    excluded_slots: tuple[int, ...] = ()
    only_imbalanced: bool = False
    min_total_clients: int = 1
    ratio_threshold: float = 10.0
    min_difference: int = 20
    include_zero_client_slots: bool = True


@dataclass(frozen=True)
class AppConfig:
    wlc: WLCConfig
    ap_balance: APBalanceConfig = field(default_factory=APBalanceConfig)


@dataclass(frozen=True)
class RadioSlotLoad:
    slot: int
    clients: Optional[int]
    utilization: Optional[int]


@dataclass(frozen=True)
class APLoad:
    name: str
    radio_mac: str
    identity_label: str
    slots: int
    total_clients: int
    slot_loads: list[RadioSlotLoad]
    timestamp: datetime = field(default_factory=datetime.now)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LoadInfoSnapshot:
    ap_loads: list[APLoad] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    parser_warnings: list[str] = field(default_factory=list)
    poll_error: str = ""
    raw_command: str = "show ap summary load-info"


@dataclass(frozen=True)
class BalanceScore:
    status: str
    max_clients: int = 0
    min_clients: int = 0
    spread: int = 0
    ratio: Optional[float] = None
    reason: str = ""
