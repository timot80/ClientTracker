from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "packaging" / "windows" / "install.ps1"
LAUNCHERS = ROOT / "packaging" / "windows" / "launchers"
README = ROOT / "packaging" / "windows" / "README.txt"
BUILDER = ROOT / "scripts" / "build-windows-install-bundle.ps1"


def test_windows_installer_script_has_safe_offline_install_contract():
    text = INSTALLER.read_text(encoding="utf-8")

    assert "Set-StrictMode -Version Latest" in text
    assert "$ErrorActionPreference = \"Stop\"" in text
    assert "$BundleDir" in text
    assert "$InstallDir" in text
    assert "$env:LOCALAPPDATA" in text
    assert "Get-WifiOpsPython" in text
    assert "Python 3.10 or newer" in text
    assert "Get-ChildItem" in text and "wifiops-*.whl" in text
    assert "Expected exactly one wifiops wheel" in text
    assert "--no-index" in text
    assert "--find-links" in text
    assert "--force-reinstall" in text
    assert "Copy-Item" in text
    assert "config.example.yaml" in text
    assert "if (-not (Test-Path $ConfigPath))" in text
    assert "wifiops-check.cmd" in text
    assert "pip install --upgrade pip" not in text
    assert "--upgrade pip" not in text


def test_windows_launchers_use_app_local_config_and_pass_args():
    for launcher in _launcher_paths():
        text = launcher.read_text(encoding="utf-8")
        assert "@echo off" in text
        assert "WIFIOPS_APP_DIR" in text
        assert "WIFIOPS_CONFIG" in text
        assert "%*" in text
        assert "%~dp0" in text
        assert "%LOCALAPPDATA%" not in text

    assert "c9800 radio --config \"%WIFIOPS_CONFIG%\"" in (
        LAUNCHERS / "wifiops-ap-radio.cmd"
    ).read_text(encoding="utf-8")
    assert "c9800 ap-ports --config \"%WIFIOPS_CONFIG%\"" in (
        LAUNCHERS / "wifiops-ap-ports.cmd"
    ).read_text(encoding="utf-8")
    assert "ap filesystems --config \"%WIFIOPS_CONFIG%\"" in (
        LAUNCHERS / "wifiops-ap-filesystem.cmd"
    ).read_text(encoding="utf-8")


def test_windows_bundle_readme_explains_powershell_install():
    text = README.read_text(encoding="utf-8")

    assert "PowerShell" in text
    assert "Set-ExecutionPolicy -Scope Process Bypass" in text
    assert ".\\install.ps1" in text
    assert "%LOCALAPPDATA%\\WifiOps" in text
    assert "wifiops-check.cmd" in text


def test_windows_bundle_builder_creates_self_contained_zip_layout():
    text = BUILDER.read_text(encoding="utf-8")

    assert "Set-StrictMode -Version Latest" in text
    assert "-m build --wheel" in text
    assert "pip download" in text
    assert "packaging\\windows\\install.ps1" in text
    assert "packaging\\windows\\launchers" in text
    assert "config.example.yaml" in text
    assert "Compress-Archive" in text
    assert "wifiops-windows-$Version.zip" in text
    assert "wifiops-check.cmd" in text
    assert "Join-Path $RootDir \"pyproject.toml\"" in text


def test_readme_documents_windows_bundle():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Build a Windows install bundle" in text
    assert "scripts/build-windows-install-bundle.ps1" in text
    assert "wifiops-windows-0.1.0.zip" in text
    assert "%LOCALAPPDATA%\\WifiOps" in text


def _launcher_paths() -> list[Path]:
    return sorted(path for path in LAUNCHERS.iterdir() if path.is_file())
