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
template only if config.yaml does not already exist. Package installation uses
the bundled wheels only and does not download from the internet.

Custom install directory
------------------------

Set WIFIOPS_INSTALL_DIR before running install.ps1:

  $env:WIFIOPS_INSTALL_DIR = "C:\WifiOps"
  .\install.ps1

The launchers resolve the WifiOps app directory relative to their own bin
folder, so they continue to use the matching local config.yaml when installed
outside %LOCALAPPDATA%\WifiOps.

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

If you used WIFIOPS_INSTALL_DIR, replace %LOCALAPPDATA%\WifiOps with that path.

Validation
----------

Smoke-test each new Windows bundle on a Windows host before sharing it with
operators:

  %LOCALAPPDATA%\WifiOps\bin\wifiops-check.cmd

Uninstall
---------

Remove the install directory:

  rmdir /s /q "%LOCALAPPDATA%\WifiOps"
