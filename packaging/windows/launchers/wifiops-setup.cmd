@echo off
set "WIFIOPS_BIN_DIR=%~dp0"
for %%I in ("%WIFIOPS_BIN_DIR%..") do set "WIFIOPS_APP_DIR=%%~fI"
set "WIFIOPS_CONFIG=%WIFIOPS_APP_DIR%\config.yaml"
echo Edit this config file:
echo   %WIFIOPS_CONFIG%
echo.
"%WIFIOPS_APP_DIR%\.venv\Scripts\wifiops.exe" credentials show-profiles --config "%WIFIOPS_CONFIG%" %*
