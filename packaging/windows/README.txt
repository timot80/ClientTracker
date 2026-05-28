WifiOps Windows install bundle
==============================

Install
-------

Unzip the bundle, open PowerShell in the extracted wifiops-windows folder, then run:

  Set-ExecutionPolicy -Scope Process Bypass
  .\install.ps1

The installer creates:

  %LOCALAPPDATA%\WifiOps

It installs WifiOps into a private virtual environment, copies launcher scripts
into %LOCALAPPDATA%\WifiOps\bin, and creates config.yaml from the bundled
template only if config.yaml does not already exist.

Run setup
---------

  %LOCALAPPDATA%\WifiOps\bin\wifiops-setup.cmd

Common commands
---------------

  %LOCALAPPDATA%\WifiOps\bin\wifiops-check.cmd
  %LOCALAPPDATA%\WifiOps\bin\wifiops-ap-radio.cmd
  %LOCALAPPDATA%\WifiOps\bin\wifiops-ap-ports.cmd
  %LOCALAPPDATA%\WifiOps\bin\wifiops-ap-filesystem.cmd
  %LOCALAPPDATA%\WifiOps\bin\wifiops-client-local.cmd

Uninstall
---------

Remove the install directory:

  rmdir /s /q "%LOCALAPPDATA%\WifiOps"
