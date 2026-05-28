from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from ap_port_audit.models import APPortAuditConfig, APPortConfig
from wifiops.wlc_targets import WlcTargetConfigError, resolve_wlc_targets


def load_config(path: str | Path) -> APPortConfig:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise ValueError(f"Config file not found: {cfg_path}")
    with cfg_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("Config file must contain a YAML mapping")

    try:
        wlc_targets = resolve_wlc_targets(raw, os.environ)
    except WlcTargetConfigError as exc:
        raise ValueError(str(exc)) from exc

    wifiops_raw = _mapping(raw.get("wifiops") or {}, "wifiops")
    ap_raw = _mapping(raw.get("ap_ports") or {}, "ap_ports")
    return APPortConfig(
        wlc_targets=wlc_targets,
        ap_ports=APPortAuditConfig(
            include=_str_tuple(ap_raw.get("include", ())),
            exclude=_str_tuple(ap_raw.get("exclude", ())),
            show_all=bool(ap_raw.get("show_all", False)),
            speed_threshold=int(ap_raw.get("speed_threshold", 1000)),
        ),
        wlc_concurrency=int(wifiops_raw.get("wlc_concurrency", 3)),
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
