from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from ap_port_audit.models import APPortAuditConfig, APPortConfig
from ap_radio_monitor.models import WLCConfig
from wifiops.credentials import CredentialConfigError, resolve_credentials


WLC_CREDENTIAL_ENV = {
    "username": "CLIENT_TRACKER_WLC_USERNAME",
    "password": "CLIENT_TRACKER_WLC_PASSWORD",
    "enable": "CLIENT_TRACKER_WLC_ENABLE",
}


def load_config(path: str | Path) -> APPortConfig:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise ValueError(f"Config file not found: {cfg_path}")
    with cfg_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("Config file must contain a YAML mapping")

    wlc_raw = _mapping(raw.get("wlc") or {}, "wlc")
    try:
        credentials = resolve_credentials(raw, "wlc", os.environ, WLC_CREDENTIAL_ENV)
    except CredentialConfigError as exc:
        raise ValueError(str(exc)) from exc

    host = os.environ.get("CLIENT_TRACKER_WLC_HOST", str(wlc_raw.get("host", "")))
    if not host.strip():
        raise ValueError("Missing required config value: wlc.host")
    if not credentials.username.strip():
        raise ValueError("Missing required config value: wlc.username")
    if not credentials.password.strip():
        raise ValueError("Missing required config value: wlc.password")

    ap_raw = _mapping(raw.get("ap_ports") or {}, "ap_ports")
    return APPortConfig(
        wlc=WLCConfig(
            host=host,
            username=credentials.username,
            password=credentials.password,
            enable=credentials.enable,
            read_timeout=int(wlc_raw.get("read_timeout", 90)),
        ),
        ap_ports=APPortAuditConfig(
            include=_str_tuple(ap_raw.get("include", ())),
            exclude=_str_tuple(ap_raw.get("exclude", ())),
            show_all=bool(ap_raw.get("show_all", False)),
            speed_threshold=int(ap_raw.get("speed_threshold", 1000)),
        ),
    )


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def _str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)
