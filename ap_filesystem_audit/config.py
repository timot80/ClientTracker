from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from ap_filesystem_audit.models import APCredentials, APFilesystemAuditConfig, APFilesystemConfig
from wifiops.credentials import CredentialConfigError, resolve_credentials
from wifiops.wlc_targets import WlcTargetConfigError, resolve_wlc_targets


AP_CREDENTIAL_ENV = {
    "username": "CLIENT_TRACKER_AP_USERNAME",
    "password": "CLIENT_TRACKER_AP_PASSWORD",
    "enable": "CLIENT_TRACKER_AP_ENABLE",
}


def load_config(path: str | Path) -> APFilesystemConfig:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise ValueError(f"Config file not found: {cfg_path}")
    with cfg_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("Config file must contain a YAML mapping")

    try:
        wlc_targets = resolve_wlc_targets(raw, os.environ)
        ap_resolved = resolve_credentials(raw, "ap", os.environ, AP_CREDENTIAL_ENV)
    except (CredentialConfigError, WlcTargetConfigError) as exc:
        raise ValueError(str(exc)) from exc

    if not ap_resolved.username.strip():
        raise ValueError("Missing required config value: ap.username")
    if not ap_resolved.password.strip():
        raise ValueError("Missing required config value: ap.password")

    wifiops_raw = _mapping(raw.get("wifiops") or {}, "wifiops")
    ap_filesystems_raw = _mapping(raw.get("ap_filesystems") or {}, "ap_filesystems")
    return APFilesystemConfig(
        wlc_targets=wlc_targets,
        ap_credentials=APCredentials(
            username=ap_resolved.username,
            password=ap_resolved.password,
            enable=ap_resolved.enable,
        ),
        audit=APFilesystemAuditConfig(
            include=_str_tuple(ap_filesystems_raw.get("include", ())),
            exclude=_str_tuple(ap_filesystems_raw.get("exclude", ())),
            min_used_percent=int(ap_filesystems_raw.get("min_used_percent", 95)),
            show_all=bool(ap_filesystems_raw.get("show_all", False)),
            ap_concurrency=int(ap_filesystems_raw.get("ap_concurrency", 20)),
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
