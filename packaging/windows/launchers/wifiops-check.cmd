@echo off
set "WIFIOPS_APP_DIR=%LOCALAPPDATA%\WifiOps"
set "WIFIOPS_CONFIG=%WIFIOPS_APP_DIR%\config.yaml"
"%WIFIOPS_APP_DIR%\.venv\Scripts\wifiops.exe" check --config "%WIFIOPS_CONFIG%" %*
