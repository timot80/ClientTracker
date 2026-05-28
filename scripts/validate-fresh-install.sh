#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/wifiops-install.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

PYTHON_BIN="${PYTHON:-python3}"
VENV_DIR="$TMP_DIR/venv"
DIST_DIR="$TMP_DIR/dist"
RUN_DIR="$TMP_DIR/run"
mkdir -p "$DIST_DIR" "$RUN_DIR"

"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip build

(
  cd "$ROOT_DIR"
  "$VENV_DIR/bin/python" -m build --wheel --outdir "$DIST_DIR"
)

WHEEL_PATH="$(find "$DIST_DIR" -maxdepth 1 -name 'wifiops-*.whl' -print -quit)"
if [[ -z "$WHEEL_PATH" ]]; then
  echo "No wifiops wheel was built" >&2
  exit 1
fi

"$VENV_DIR/bin/python" -m pip install --no-cache-dir --force-reinstall "$WHEEL_PATH"

(
  cd "$RUN_DIR"
  unset PYTHONPATH
  export HOME="$TMP_DIR/home"
  export XDG_CONFIG_HOME="$TMP_DIR/xdg"
  mkdir -p "$HOME" "$XDG_CONFIG_HOME"

  "$VENV_DIR/bin/python" -m pip show wifiops
  "$VENV_DIR/bin/wifiops" --help
  "$VENV_DIR/bin/wifiops" credentials show-profiles --config "$RUN_DIR/config.yaml"
  "$VENV_DIR/bin/wifiops" c9800 radio --help
  "$VENV_DIR/bin/wifiops" c9800 ap-ports --help
  "$VENV_DIR/bin/wifiops" ap filesystems --help
  "$VENV_DIR/bin/wifiops" client local --help
  "$VENV_DIR/bin/wifiops" check

  "$VENV_DIR/bin/python" - "$ROOT_DIR" <<'PY'
from __future__ import annotations

import importlib.util
import pathlib
import sys

repo = pathlib.Path(sys.argv[1]).resolve()
for name in ("wifiops", "client_tracker", "ap_radio_monitor", "ap_port_audit", "ap_filesystem_audit"):
    spec = importlib.util.find_spec(name)
    if spec is None or spec.origin is None:
        raise SystemExit(f"{name} is not importable from the installed wheel")
    origin = pathlib.Path(spec.origin).resolve()
    if repo in origin.parents or origin == repo:
        raise SystemExit(f"{name} imported from source checkout instead of wheel: {origin}")
    print(f"{name}: {origin}")
PY
)

echo "Fresh wifiops wheel install validation passed."
