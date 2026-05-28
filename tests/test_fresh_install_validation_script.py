from __future__ import annotations

import os
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate-fresh-install.sh"


def test_fresh_install_validator_exists_and_is_executable():
    assert SCRIPT.exists()
    assert os.access(SCRIPT, os.X_OK)


def test_fresh_install_validator_builds_and_installs_wheel():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "python\" -m build --wheel" in text
    assert "pip install --no-cache-dir --force-reinstall \"$WHEEL_PATH\"" in text
    assert "find \"$DIST_DIR\" -maxdepth 1 -name 'wifiops-*.whl'" in text


def test_fresh_install_validator_avoids_source_checkout_imports():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "cd \"$RUN_DIR\"" in text
    assert "unset PYTHONPATH" in text
    assert "importlib.util.find_spec" in text
    assert "imported from source checkout instead of wheel" in text
    assert '"wifiops", "client_tracker", "ap_radio_monitor", "ap_port_audit"' in text
