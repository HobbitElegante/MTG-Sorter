# Build Windows onedir (MTG-Rebuilder.exe) with PyInstaller, then zip for distribution.
# Run on Windows (or in GitHub Actions windows-latest). Does not run on Linux.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> Syncing packaging extras"
uv sync --extra packaging --extra dev

Write-Host "==> Running PyInstaller"
if (Test-Path "dist\MTG-Rebuilder") {
    Remove-Item -Recurse -Force "dist\MTG-Rebuilder"
}
uv run pyinstaller --noconfirm --clean "packaging\mtg_rebuilder.spec"

$Exe = Join-Path $Root "dist\MTG-Rebuilder\MTG-Rebuilder.exe"
if (-not (Test-Path $Exe)) {
    throw "Expected executable at $Exe"
}

$Zip = Join-Path $Root "dist\MTG-Rebuilder-windows-x64.zip"
Write-Host "==> Creating $Zip"
if (Test-Path $Zip) {
    Remove-Item -Force $Zip
}
Compress-Archive -Path (Join-Path $Root "dist\MTG-Rebuilder") -DestinationPath $Zip

Write-Host "Built: $Exe"
Write-Host "Zip:   $Zip"
