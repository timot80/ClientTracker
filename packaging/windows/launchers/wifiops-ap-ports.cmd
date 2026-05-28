@echo off
set "WIFIOPS_APP_DIR=%LOCALAPPDATA%\WifiOps"
set "WIFIOPS_CONFIG=%WIFIOPS_APP_DIR%\config.yaml"
"%WIFIOPS_APP_DIR%\.venv\Scripts\wifiops.exe" c9800 ap-ports --config "%WIFIOPS_CONFIG%" %*
