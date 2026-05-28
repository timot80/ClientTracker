from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ap_radio_monitor.models import WLCConfig
from wifiops.credentials import CredentialConfigError, resolve_credentials


WLC_CREDENTIAL_ENV = {
    "username": "CLIENT_TRACKER_WLC_USERNAME",
    "password": "CLIENT_TRACKER_WLC_PASSWORD",
    "enable": "CLIENT_TRACKER_WLC_ENABLE",
}


class WlcTargetConfigError(ValueError):
    pass


@dataclass(frozen=True)
class WlcTarget:
    name: str
    config: WLCConfig


def resolve_wlc_targets(
    raw: dict[str, Any],
    env: Mapping[str, str] | None = None,
) -> list[WlcTarget]:
    env = os.environ if env is None else env
    if "wlcs" in raw and raw.get("wlcs") is not None:
        wlcs = raw["wlcs"]
        if not isinstance(wlcs, list):
            raise WlcTargetConfigError("wlcs must be a list")
        targets = [
            _target_from_section(raw, f"wlcs[{index}]", item, env)
            for index, item in enumerate(wlcs)
        ]
        _validate_unique_names(targets)
        return targets

    wlc = raw.get("wlc") or {}
    if not isinstance(wlc, dict):
        raise WlcTargetConfigError("wlc must be a mapping")
    return [_target_from_section(raw, "wlc", wlc, env, default_name="default")]


def select_wlc_targets(targets: list[WlcTarget], names: tuple[str, ...]) -> list[WlcTarget]:
    if not names:
        return targets
    by_name = {target.name: target for target in targets}
    selected = []
    for name in names:
        target = by_name.get(name)
        if target is None:
            available = ", ".join(sorted(by_name))
            raise WlcTargetConfigError(f"Unknown WLC '{name}'. Available WLCs: {available}")
        selected.append(target)
    return selected


def _target_from_section(
    raw: dict[str, Any],
    section: str,
    section_data: Any,
    env: Mapping[str, str],
    default_name: str | None = None,
) -> WlcTarget:
    if not isinstance(section_data, dict):
        raise WlcTargetConfigError(f"{section} must be a mapping")
    name = str(section_data.get("name") or default_name or "").strip()
    if not name:
        raise WlcTargetConfigError(f"Missing required config value: {section}.name")
    try:
        credentials = resolve_credentials({**raw, section: section_data}, section, env, WLC_CREDENTIAL_ENV)
    except CredentialConfigError as exc:
        raise WlcTargetConfigError(str(exc)) from exc
    host = env.get("CLIENT_TRACKER_WLC_HOST", str(section_data.get("host", ""))).strip()
    if not host:
        raise WlcTargetConfigError(f"Missing required config value: {section}.host")
    if not credentials.username.strip():
        raise WlcTargetConfigError(f"Missing required config value: {section}.username")
    if not credentials.password.strip():
        raise WlcTargetConfigError(f"Missing required config value: {section}.password")
    return WlcTarget(
        name=name,
        config=WLCConfig(
            host=host,
            username=credentials.username,
            password=credentials.password,
            enable=credentials.enable,
            read_timeout=int(section_data.get("read_timeout", 90)),
        ),
    )


def _validate_unique_names(targets: list[WlcTarget]) -> None:
    seen: set[str] = set()
    for target in targets:
        if target.name in seen:
            raise WlcTargetConfigError(f"Duplicate WLC name '{target.name}'")
        seen.add(target.name)
