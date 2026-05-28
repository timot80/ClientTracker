WifiOps macOS install bundle
============================

Install
-------

Unzip the bundle, then double-click install.command.

If macOS blocks the unsigned script, right-click install.command, choose Open,
and confirm. You can also install from Terminal:

  cd /path/to/wifiops-macos
  ./install.command

The installer creates:

  ~/Applications/WifiOps

It installs WifiOps into a private virtual environment, copies launcher scripts
into ~/Applications/WifiOps/bin, and creates config.yaml from the bundled
template only if config.yaml does not already exist.

Run setup
---------

  ~/Applications/WifiOps/bin/wifiops-setup

Common commands
---------------

  ~/Applications/WifiOps/bin/wifiops-check
  ~/Applications/WifiOps/bin/wifiops-ap-radio
  ~/Applications/WifiOps/bin/wifiops-ap-ports
  ~/Applications/WifiOps/bin/wifiops-ap-filesystem
  ~/Applications/WifiOps/bin/wifiops-client-local

Uninstall
---------

Remove the install directory:

  rm -rf ~/Applications/WifiOps
