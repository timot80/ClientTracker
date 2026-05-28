#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
PYTHON_BIN="${PYTHON:-python3}"
DIST_ROOT="${WIFIOPS_BUNDLE_DIST_DIR:-$ROOT_DIR/dist}"
BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/wifiops-bundle.XXXXXX")"
trap 'rm -rf "$BUILD_ROOT"' EXIT

VERSION="$("$PYTHON_BIN" - <<'PY'
from pathlib import Path
import tomllib

data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(data["project"]["version"])
PY
)"

STAGE_DIR="$BUILD_ROOT/wifiops-macos"
WHEELHOUSE="$STAGE_DIR/wheels"
BUILD_VENV="$BUILD_ROOT/venv"
WHEEL_BUILD_DIR="$BUILD_ROOT/wheel-build"
ZIP_PATH="$DIST_ROOT/wifiops-macos-${VERSION}.zip"

mkdir -p "$WHEELHOUSE" "$WHEEL_BUILD_DIR" "$DIST_ROOT"
"$PYTHON_BIN" -m venv "$BUILD_VENV"
"$BUILD_VENV/bin/python" -m pip install --upgrade pip build

(
  cd "$ROOT_DIR"
  "$BUILD_VENV/bin/python" -m build --wheel --outdir "$WHEEL_BUILD_DIR"
)

BUILT_WHEELS=()
while IFS= read -r wheel; do
  BUILT_WHEELS+=("$wheel")
done < <(find "$WHEEL_BUILD_DIR" -maxdepth 1 -name 'wifiops-*.whl' -print)
if [[ "${#BUILT_WHEELS[@]}" -ne 1 ]]; then
  echo "Expected exactly one built wifiops wheel, found ${#BUILT_WHEELS[@]}." >&2
  exit 1
fi

"$BUILD_VENV/bin/python" -m pip download --dest "$WHEELHOUSE" "${BUILT_WHEELS[0]}"

BUNDLE_WHEELS=()
while IFS= read -r wheel; do
  BUNDLE_WHEELS+=("$wheel")
done < <(find "$WHEELHOUSE" -maxdepth 1 -name 'wifiops-*.whl' -print)
if [[ "${#BUNDLE_WHEELS[@]}" -ne 1 ]]; then
  echo "Expected exactly one bundled wifiops wheel, found ${#BUNDLE_WHEELS[@]}." >&2
  exit 1
fi

cp "$ROOT_DIR/packaging/macos/install.command" "$STAGE_DIR/install.command"
cp "$ROOT_DIR/packaging/macos/README.txt" "$STAGE_DIR/README.txt"
mkdir -p "$STAGE_DIR/launchers" "$STAGE_DIR/templates"
cp -R "$ROOT_DIR/packaging/macos/launchers/." "$STAGE_DIR/launchers/"
cp "$ROOT_DIR/config.example.yaml" "$STAGE_DIR/templates/config.example.yaml"
chmod +x "$STAGE_DIR/install.command" "$STAGE_DIR/launchers/"*

rm -f "$ZIP_PATH"
(
  cd "$BUILD_ROOT"
  zip -qr "$ZIP_PATH" wifiops-macos
)

for required in \
  "$STAGE_DIR/install.command" \
  "$STAGE_DIR/README.txt" \
  "$STAGE_DIR/templates/config.example.yaml" \
  "$STAGE_DIR/launchers/wifiops" \
  "$STAGE_DIR/launchers/wifiops-check"
do
  [[ -e "$required" ]] || {
    echo "Missing required bundle file: $required" >&2
    exit 1
  }
done

echo "Created $ZIP_PATH"
