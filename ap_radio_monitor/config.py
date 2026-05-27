from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ap_radio_monitor.models import APBalanceConfig, AppConfig, WLCConfig


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

    wlc = WLCConfig(
        host=_required_str(wlc_raw, "wlc.host"),
        username=_required_str(wlc_raw, "wlc.username"),
        password=_required_str(wlc_raw, "wlc.password"),
        enable=str(wlc_raw.get("enable", "") or ""),
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
        min_total_clients=int(ap_raw.get("min_total_clients", 1)),
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
