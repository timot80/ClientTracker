from __future__ import annotations

import os
from pathlib import Path


CONFIG_ENV_VAR = "WIFIOPS_CONFIG"


def default_config_path(package_file: str | os.PathLike[str]) -> Path:
    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser()
    return Path(package_file).resolve().parent.parent / "config.yaml"


def default_config_arg() -> list[str]:
    env_path = os.environ.get(CONFIG_ENV_VAR)
    if not env_path:
        return []
    return ["--config", str(Path(env_path).expanduser())]
