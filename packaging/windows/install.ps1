Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BundleDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = if ($env:WIFIOPS_INSTALL_DIR) { $env:WIFIOPS_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA "WifiOps" }
$VenvDir = Join-Path $InstallDir ".venv"
$BinDir = Join-Path $InstallDir "bin"
$ConfigPath = Join-Path $InstallDir "config.yaml"
$ExampleConfigPath = Join-Path $InstallDir "config.example.yaml"

function Fail($Message) {
    Write-Error "WifiOps install failed: $Message"
    exit 1
}

function Get-WifiOpsPython {
    $candidates = @(
        @("py", "-3"),
        @("python")
    )
    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        $args = @()
        if ($candidate.Count -gt 1) {
            $args = $candidate[1..($candidate.Count - 1)]
        }
        try {
            $versionOutput = & $exe @args -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return @{ Exe = $exe; Args = $args }
            }
        } catch {
            continue
        }
    }
    Fail "Python 3.10 or newer was not found. Install Python 3.10 or newer, then run this installer again."
}

$WheelsDir = Join-Path $BundleDir "wheels"
$WifiOpsWheels = @(Get-ChildItem -Path $WheelsDir -Filter "wifiops-*.whl" -File)
if ($WifiOpsWheels.Count -ne 1) {
    Fail "Expected exactly one wifiops wheel in $WheelsDir, found $($WifiOpsWheels.Count)."
}

$Python = Get-WifiOpsPython
New-Item -ItemType Directory -Force -Path $InstallDir, $BinDir | Out-Null

& $Python.Exe @($Python.Args + @("-m", "venv", $VenvDir))
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
& $VenvPython -m pip install `
    --no-index `
    --find-links $WheelsDir `
    --force-reinstall `
    $WifiOpsWheels[0].FullName

Copy-Item -Path (Join-Path $BundleDir "launchers\*.cmd") -Destination $BinDir -Force
Copy-Item -Path (Join-Path $BundleDir "templates\config.example.yaml") -Destination $ExampleConfigPath -Force
if (-not (Test-Path $ConfigPath)) {
    Copy-Item -Path $ExampleConfigPath -Destination $ConfigPath
}

& (Join-Path $BinDir "wifiops-check.cmd")

Write-Host ""
Write-Host "WifiOps installed at:"
Write-Host "  $InstallDir"
Write-Host ""
Write-Host "Run setup:"
Write-Host "  $BinDir\wifiops-setup.cmd"
