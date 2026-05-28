Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }
$DistRoot = if ($env:WIFIOPS_BUNDLE_DIST_DIR) { $env:WIFIOPS_BUNDLE_DIST_DIR } else { Join-Path $RootDir "dist" }
$BuildRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("wifiops-windows-bundle-" + [System.Guid]::NewGuid().ToString("N"))

try {
    $PyProjectPath = Join-Path $RootDir "pyproject.toml"
    $Version = & $Python -c "import pathlib, sys, tomllib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))['project']['version'])" $PyProjectPath
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read project version"
    }

    $StageDir = Join-Path $BuildRoot "wifiops-windows"
    $Wheelhouse = Join-Path $StageDir "wheels"
    $BuildVenv = Join-Path $BuildRoot "venv"
    $WheelBuildDir = Join-Path $BuildRoot "wheel-build"
    $ZipPath = Join-Path $DistRoot "wifiops-windows-$Version.zip"

    New-Item -ItemType Directory -Force -Path $Wheelhouse, $WheelBuildDir, $DistRoot | Out-Null
    & $Python -m venv $BuildVenv
    $BuildPython = Join-Path $BuildVenv "Scripts\python.exe"
    & $BuildPython -m pip install --upgrade pip build

    Push-Location $RootDir
    try {
        & $BuildPython -m build --wheel --outdir $WheelBuildDir
    } finally {
        Pop-Location
    }

    $BuiltWheels = @(Get-ChildItem -Path $WheelBuildDir -Filter "wifiops-*.whl" -File)
    if ($BuiltWheels.Count -ne 1) {
        throw "Expected exactly one built wifiops wheel, found $($BuiltWheels.Count)."
    }

    & $BuildPython -m pip download --dest $Wheelhouse $BuiltWheels[0].FullName

    $BundleWheels = @(Get-ChildItem -Path $Wheelhouse -Filter "wifiops-*.whl" -File)
    if ($BundleWheels.Count -ne 1) {
        throw "Expected exactly one bundled wifiops wheel, found $($BundleWheels.Count)."
    }

    Copy-Item -Path (Join-Path $RootDir "packaging\windows\install.ps1") -Destination (Join-Path $StageDir "install.ps1") -Force
    Copy-Item -Path (Join-Path $RootDir "packaging\windows\README.txt") -Destination (Join-Path $StageDir "README.txt") -Force
    New-Item -ItemType Directory -Force -Path (Join-Path $StageDir "launchers"), (Join-Path $StageDir "templates") | Out-Null
    Copy-Item -Path (Join-Path $RootDir "packaging\windows\launchers\*.cmd") -Destination (Join-Path $StageDir "launchers") -Force
    Copy-Item -Path (Join-Path $RootDir "config.example.yaml") -Destination (Join-Path $StageDir "templates\config.example.yaml") -Force

    if (Test-Path $ZipPath) {
        Remove-Item $ZipPath -Force
    }
    Compress-Archive -Path $StageDir -DestinationPath $ZipPath -Force

    foreach ($Required in @(
        (Join-Path $StageDir "install.ps1"),
        (Join-Path $StageDir "README.txt"),
        (Join-Path $StageDir "templates\config.example.yaml"),
        (Join-Path $StageDir "launchers\wifiops.cmd"),
        (Join-Path $StageDir "launchers\wifiops-check.cmd")
    )) {
        if (-not (Test-Path $Required)) {
            throw "Missing required bundle file: $Required"
        }
    }

    Write-Host "Created $ZipPath"
} finally {
    if (Test-Path $BuildRoot) {
        Remove-Item -Recurse -Force $BuildRoot
    }
}
