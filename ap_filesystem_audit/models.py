from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from wifiops.wlc_targets import WlcTarget


@dataclass(frozen=True)
class APCredentials:
    username: str
    password: str
    enable: str = ""


@dataclass(frozen=True)
class APFilesystemAuditConfig:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    ap_names: tuple[str, ...] = ()
    ap_hosts: tuple[str, ...] = ()
    min_used_percent: int = 95
    show_all: bool = False
    ap_concurrency: int = 20
    output: str = ""
    reload_full_tmp: bool = False
    confirm_reload_full_tmp: bool = False


@dataclass(frozen=True)
class APFilesystemConfig:
    wlc_targets: list[WlcTarget]
    ap_credentials: APCredentials
    audit: APFilesystemAuditConfig = field(default_factory=APFilesystemAuditConfig)
    wlc_concurrency: int = 3


@dataclass(frozen=True)
class APTarget:
    wlc_name: str
    wlc_host: str
    name: str
    host: str


@dataclass(frozen=True)
class APFilesystemRow:
    wlc_name: str = ""
    wlc_host: str = ""
    ap_name: str = ""
    ap_host: str = ""
    filesystem: str = ""
    mount: str = ""
    size: str = ""
    used: str = ""
    available: str = ""
    used_percent: int | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class APFilesystemFailure:
    wlc_name: str = ""
    wlc_host: str = ""
    ap_name: str = ""
    ap_host: str = ""
    message: str = ""


@dataclass(frozen=True)
class APReloadResult:
    wlc_name: str = ""
    wlc_host: str = ""
    ap_name: str = ""
    ap_host: str = ""
    action: str = ""
    output: str = ""


@dataclass(frozen=True)
class APFilesystemSnapshot:
    rows: list[APFilesystemRow] = field(default_factory=list)
    failures: list[APFilesystemFailure] = field(default_factory=list)
    parser_warnings: list[str] = field(default_factory=list)
    reload_results: list[APReloadResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
