from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "packaging" / "macos" / "install.command"
LAUNCHERS = ROOT / "packaging" / "macos" / "launchers"
README = ROOT / "packaging" / "macos" / "README.txt"
BUILDER = ROOT / "scripts" / "build-macos-install-bundle.sh"


def test_macos_installer_script_has_safe_offline_install_contract():
    text = INSTALLER.read_text(encoding="utf-8")

    assert text.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
    assert "BUNDLE_DIR=" in text
    assert "INSTALL_DIR=" in text
    assert "python3" in text
    assert "sys.version_info < (3, 10)" in text
    assert "find \"$BUNDLE_DIR/wheels\" -maxdepth 1 -name 'wifiops-*.whl'" in text
    assert "Expected exactly one wifiops wheel" in text
    assert "--no-index" in text
    assert "--find-links" in text
    assert "--force-reinstall" in text
    assert "cp -R \"$BUNDLE_DIR/launchers/.\" \"$INSTALL_DIR/bin/\"" in text
    assert "if [[ ! -f \"$INSTALL_DIR/config.yaml\" ]]" in text
    assert "\"$INSTALL_DIR/bin/wifiops-check\"" in text


def test_macos_installer_and_launchers_are_executable():
    assert os.access(INSTALLER, os.X_OK)
    for launcher in _launcher_paths():
        assert os.access(launcher, os.X_OK), launcher


def test_launcher_scripts_use_app_local_config_and_pass_args():
    for launcher in _launcher_paths():
        text = launcher.read_text(encoding="utf-8")
        assert "APP_DIR=" in text
        assert "WIFIOPS_CONFIG" in text
        assert '"$@"' in text
        assert "eval" not in text

    assert "c9800 radio --config \"$WIFIOPS_CONFIG\"" in (LAUNCHERS / "wifiops-ap-radio").read_text(
        encoding="utf-8"
    )
    assert "c9800 ap-ports --config \"$WIFIOPS_CONFIG\"" in (
        LAUNCHERS / "wifiops-ap-ports"
    ).read_text(encoding="utf-8")
    assert "ap filesystems --config \"$WIFIOPS_CONFIG\"" in (
        LAUNCHERS / "wifiops-ap-filesystem"
    ).read_text(encoding="utf-8")


def test_bundle_readme_explains_install_and_unsigned_macos_fallback():
    text = README.read_text(encoding="utf-8")

    assert "double-click install.command" in text
    assert "~/Applications/WifiOps" in text
    assert "right-click" in text
    assert "./install.command" in text


def _launcher_paths() -> list[Path]:
    return sorted(path for path in LAUNCHERS.iterdir() if path.is_file())
