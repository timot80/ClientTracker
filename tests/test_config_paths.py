from __future__ import annotations

from pathlib import Path

from wifiops.config_paths import default_config_path


def test_default_config_path_uses_repo_relative_config_when_env_absent(monkeypatch, tmp_path):
    monkeypatch.delenv("WIFIOPS_CONFIG", raising=False)
    package_file = tmp_path / "pkg" / "wifiops" / "cli.py"
    package_file.parent.mkdir(parents=True)
    package_file.touch()

    assert default_config_path(package_file) == tmp_path / "pkg" / "config.yaml"


def test_default_config_path_uses_wifiops_config_env(monkeypatch, tmp_path):
    config_path = tmp_path / "WifiOps" / "config.yaml"
    monkeypatch.setenv("WIFIOPS_CONFIG", str(config_path))

    assert default_config_path("/tmp/pkg/wifiops/cli.py") == config_path
