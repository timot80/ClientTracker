#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
INSTALL_DIR="${WIFIOPS_INSTALL_DIR:-$HOME/Applications/WifiOps}"
VENV_DIR="$INSTALL_DIR/.venv"

fail() {
  echo "WifiOps install failed: $*" >&2
  exit 1
}

if ! command -v python3 >/dev/null 2>&1; then
  fail "python3 was not found. Install Python 3.10 or newer, then run this installer again."
fi

python3 - <<'PY' || fail "Python 3.10 or newer is required."
import sys
raise SystemExit(1 if sys.version_info < (3, 10) else 0)
PY

WHEELS=()
while IFS= read -r wheel; do
  WHEELS+=("$wheel")
done < <(find "$BUNDLE_DIR/wheels" -maxdepth 1 -name 'wifiops-*.whl' -print)
if [[ "${#WHEELS[@]}" -ne 1 ]]; then
  fail "Expected exactly one wifiops wheel in $BUNDLE_DIR/wheels, found ${#WHEELS[@]}."
fi

mkdir -p "$INSTALL_DIR/bin"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install \
  --no-index \
  --find-links "$BUNDLE_DIR/wheels" \
  --force-reinstall \
  "${WHEELS[0]}"

cp -R "$BUNDLE_DIR/launchers/." "$INSTALL_DIR/bin/"
chmod +x "$INSTALL_DIR/bin/"*

cp "$BUNDLE_DIR/templates/config.example.yaml" "$INSTALL_DIR/config.example.yaml"
if [[ ! -f "$INSTALL_DIR/config.yaml" ]]; then
  cp "$INSTALL_DIR/config.example.yaml" "$INSTALL_DIR/config.yaml"
fi

"$INSTALL_DIR/bin/wifiops-check"

cat <<EOF

WifiOps installed at:
  $INSTALL_DIR

Run setup:
  $INSTALL_DIR/bin/wifiops-setup

Optional macOS Wi-Fi identity helper:
  scripts/build-macos-wifi-identity-helper.sh
EOF
