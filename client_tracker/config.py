from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from wifiops.credentials import CredentialConfigError, ResolvedCredentials, resolve_credentials
from wifiops.wlc_targets import WlcTargetConfigError, resolve_wlc_targets, select_wlc_targets


@dataclass
class WLCConfig:
    host: str = ""
    username: str = ""
    password: str = ""
    enable: str = ""


@dataclass
class WlcClientTarget:
    name: str
    config: WLCConfig


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
    wlc_targets: list[WlcClientTarget]
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


def load_config(
    path: str | Path,
    require_infra: bool,
    wlc_names: tuple[str, ...] = (),
) -> AppConfig:
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

    ap_data = data.get("ap", {}) or {}
    local_data = data.get("local", {}) or {}
    if require_infra:
        try:
            ap_credentials = resolve_credentials(data, "ap", os.environ, AP_CREDENTIAL_ENV)
            resolved_targets = select_wlc_targets(resolve_wlc_targets(data), wlc_names)
        except CredentialConfigError as exc:
            sys.exit(str(exc))
        except WlcTargetConfigError as exc:
            sys.exit(str(exc))
    else:
        ap_credentials = ResolvedCredentials()
        resolved_targets = []

    wlc_targets = [
        WlcClientTarget(
            name=target.name,
            config=WLCConfig(
                host=target.config.host,
                username=target.config.username,
                password=target.config.password,
                enable=target.config.enable,
            ),
        )
        for target in resolved_targets
    ]
    if wlc_targets:
        wlc = wlc_targets[0].config
    else:
        wlc_data = data.get("wlc", {}) or {}
        wlc = WLCConfig(host=str(wlc_data.get("host", "")))

    cfg = AppConfig(
        wlc=wlc,
        wlc_targets=wlc_targets,
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
        for target in cfg.wlc_targets:
            prefix = f"wlcs[{target.name}]" if len(cfg.wlc_targets) > 1 else "wlc"
            if not target.config.host:
                missing.append(f"{prefix}.host")
            if not target.config.username:
                missing.append(f"{prefix}.username")
            if not target.config.password:
                missing.append(f"{prefix}.password")
        if not cfg.ap.username:
            missing.append("ap.username")
        if not cfg.ap.password:
            missing.append("ap.password")
        if missing:
            sys.exit("Missing required config values: " + ", ".join(missing))
    return cfg
