@echo off
set "WIFIOPS_APP_DIR=%LOCALAPPDATA%\WifiOps"
set "WIFIOPS_CONFIG=%WIFIOPS_APP_DIR%\config.yaml"
echo Edit this config file:
echo   %WIFIOPS_CONFIG%
echo.
"%WIFIOPS_APP_DIR%\.venv\Scripts\wifiops.exe" credentials show-profiles --config "%WIFIOPS_CONFIG%" %*
