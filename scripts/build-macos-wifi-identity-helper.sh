#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="client-tracker-wifi-identity"
SOURCE_DIR="${ROOT_DIR}/macos/WifiIdentityHelper"
APP_DIR="${HOME}/Applications/${APP_NAME}.app"
CONTENTS_DIR="${APP_DIR}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
EXECUTABLE="${MACOS_DIR}/${APP_NAME}"

mkdir -p "${MACOS_DIR}"

swiftc \
  "${SOURCE_DIR}/main.swift" \
  -framework AppKit \
  -framework CoreLocation \
  -framework CoreWLAN \
  -o "${EXECUTABLE}"

cp "${SOURCE_DIR}/Info.plist" "${CONTENTS_DIR}/Info.plist"
chmod 755 "${EXECUTABLE}"
codesign \
  --force \
  --deep \
  --sign - \
  --entitlements "${SOURCE_DIR}/Entitlements.plist" \
  "${APP_DIR}" >/dev/null

echo "${EXECUTABLE}"
