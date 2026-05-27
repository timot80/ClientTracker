from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from ap_radio_monitor.models import APBalanceConfig, AppConfig, WLCConfig
from wifiops.credentials import CredentialConfigError, resolve_credentials


WLC_CREDENTIAL_ENV = {
    "username": "CLIENT_TRACKER_WLC_USERNAME",
    "password": "CLIENT_TRACKER_WLC_PASSWORD",
    "enable": "CLIENT_TRACKER_WLC_ENABLE",
}


def load_config(path: str | Path) -> AppConfig:
    """Load WLC and AP radio distribution config from YAML."""
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise ValueError(f"Config file not found: {cfg_path}")

    with cfg_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError("Config file must contain a YAML mapping")

    wlc_raw = raw.get("wlc") or {}
    if not isinstance(wlc_raw, dict):
        raise ValueError("wlc must be a mapping")

    try:
        wlc_credentials = resolve_credentials(raw, "wlc", os.environ, WLC_CREDENTIAL_ENV)
    except CredentialConfigError as exc:
        raise ValueError(str(exc)) from exc

    host = (
        os.environ["CLIENT_TRACKER_WLC_HOST"]
        if "CLIENT_TRACKER_WLC_HOST" in os.environ
        else _required_str(wlc_raw, "wlc.host")
    )
    wlc = WLCConfig(
        host=_required_value(host, "wlc.host"),
        username=_required_value(wlc_credentials.username, "wlc.username"),
        password=_required_value(wlc_credentials.password, "wlc.password"),
        enable=wlc_credentials.enable,
        read_timeout=int(wlc_raw.get("read_timeout", 90)),
    )

    ap_raw = raw.get("ap_balance") or {}
    if not isinstance(ap_raw, dict):
        raise ValueError("ap_balance must be a mapping")
    imbalance = ap_raw.get("imbalance") or {}
    if not isinstance(imbalance, dict):
        raise ValueError("ap_balance.imbalance must be a mapping")

    ap_balance = APBalanceConfig(
        refresh_seconds=int(ap_raw.get("refresh_seconds", 30)),
        include=_str_tuple(ap_raw.get("include", ())),
        exclude=_str_tuple(ap_raw.get("exclude", ())),
        included_slots=_int_tuple(ap_raw.get("included_slots", ())),
        excluded_slots=_int_tuple(ap_raw.get("excluded_slots", ())),
        only_imbalanced=bool(ap_raw.get("only_imbalanced", False)),
        only_problem=bool(ap_raw.get("only_problem", False)),
        show_idle=bool(ap_raw.get("show_idle", False)),
        hide_idle=bool(ap_raw.get("hide_idle", False)),
        limit=int(ap_raw.get("limit", 75)),
        display_columns=int(ap_raw.get("display_columns", 1)),
        auto_exclude_admin_down_slots=bool(ap_raw.get("auto_exclude_admin_down_slots", False)),
        min_total_clients=int(ap_raw.get("min_total_clients", 1)),
        busy_idle_utilization=int(ap_raw.get("busy_idle_utilization", 20)),
        ratio_threshold=float(imbalance.get("ratio_threshold", 10)),
        min_difference=int(imbalance.get("min_difference", 20)),
        include_zero_client_slots=bool(imbalance.get("include_zero_client_slots", True)),
    )
    return AppConfig(wlc=wlc, ap_balance=ap_balance)


def _required_str(mapping: dict[str, Any], name: str) -> str:
    key = name.split(".")[-1]
    value = mapping.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"Missing required config value: {name}")
    return str(value)


def _required_value(value: str, name: str) -> str:
    if str(value).strip() == "":
        raise ValueError(f"Missing required config value: {name}")
    return str(value)


def _str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def _int_tuple(value: Any) -> tuple[int, ...]:
    if value is None:
        return ()
    if isinstance(value, int):
        return (value,)
    return tuple(int(item) for item in value)
