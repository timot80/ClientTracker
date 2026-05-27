from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from wifiops.credentials import CredentialConfigError, ResolvedCredentials, resolve_credentials


@dataclass
class WLCConfig:
    host: str = ""
    username: str = ""
    password: str = ""
    enable: str = ""


@dataclass
class APConfig:
    username: str = ""
    password: str = ""
    enable: str = ""


@dataclass
class LocalConfig:
    ping_host: str = ""
    sound_alerts: bool = True
    identity_helper_path: str = ""


@dataclass
class AppConfig:
    wlc: WLCConfig
    ap: APConfig
    local: LocalConfig


ENV_OVERRIDES = {
    ("wlc", "host"): "CLIENT_TRACKER_WLC_HOST",
    ("wlc", "username"): "CLIENT_TRACKER_WLC_USERNAME",
    ("wlc", "password"): "CLIENT_TRACKER_WLC_PASSWORD",
    ("wlc", "enable"): "CLIENT_TRACKER_WLC_ENABLE",
    ("ap", "username"): "CLIENT_TRACKER_AP_USERNAME",
    ("ap", "password"): "CLIENT_TRACKER_AP_PASSWORD",
    ("ap", "enable"): "CLIENT_TRACKER_AP_ENABLE",
}

WLC_CREDENTIAL_ENV = {
    "username": "CLIENT_TRACKER_WLC_USERNAME",
    "password": "CLIENT_TRACKER_WLC_PASSWORD",
    "enable": "CLIENT_TRACKER_WLC_ENABLE",
}

AP_CREDENTIAL_ENV = {
    "username": "CLIENT_TRACKER_AP_USERNAME",
    "password": "CLIENT_TRACKER_AP_PASSWORD",
    "enable": "CLIENT_TRACKER_AP_ENABLE",
}


def load_config(path: str | Path, require_infra: bool) -> AppConfig:
    path = Path(path)
    data: dict[str, Any] = {}
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        if not isinstance(loaded, dict):
            sys.exit(f"Invalid config format in {path}")
        data = loaded
    elif require_infra:
        sys.exit(f"Config file not found: {path}")

    if "CLIENT_TRACKER_WLC_HOST" in os.environ:
        data.setdefault("wlc", {})["host"] = os.environ["CLIENT_TRACKER_WLC_HOST"]

    wlc_data = data.get("wlc", {}) or {}
    ap_data = data.get("ap", {}) or {}
    local_data = data.get("local", {}) or {}
    if require_infra:
        try:
            wlc_credentials = resolve_credentials(data, "wlc", os.environ, WLC_CREDENTIAL_ENV)
            ap_credentials = resolve_credentials(data, "ap", os.environ, AP_CREDENTIAL_ENV)
        except CredentialConfigError as exc:
            sys.exit(str(exc))
    else:
        wlc_credentials = ResolvedCredentials()
        ap_credentials = ResolvedCredentials()

    cfg = AppConfig(
        wlc=WLCConfig(
            host=str(wlc_data.get("host", "")),
            username=wlc_credentials.username,
            password=wlc_credentials.password,
            enable=wlc_credentials.enable,
        ),
        ap=APConfig(
            username=ap_credentials.username,
            password=ap_credentials.password,
            enable=ap_credentials.enable,
        ),
        local=LocalConfig(
            ping_host=str(local_data.get("ping_host", "")),
            sound_alerts=bool(local_data.get("sound_alerts", True)),
            identity_helper_path=str(local_data.get("identity_helper_path", "")),
        ),
    )
    if require_infra:
        missing = []
        if not cfg.wlc.host:
            missing.append("wlc.host")
        if not cfg.wlc.username:
            missing.append("wlc.username")
        if not cfg.wlc.password:
            missing.append("wlc.password")
        if not cfg.ap.username:
            missing.append("ap.username")
        if not cfg.ap.password:
            missing.append("ap.password")
        if missing:
            sys.exit("Missing required config values: " + ", ".join(missing))
    return cfg
