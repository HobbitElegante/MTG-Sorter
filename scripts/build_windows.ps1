# Build Windows onedir (MTG-Sorter.exe) with PyInstaller, then zip for distribution.
# Run on Windows (or in GitHub Actions windows-latest). Does not run on Linux.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> Syncing packaging extras"
uv sync --extra packaging --extra dev

Write-Host "==> Running PyInstaller"
if (Test-Path "dist\MTG-Sorter") {
    Remove-Item -Recurse -Force "dist\MTG-Sorter"
}
uv run pyinstaller --noconfirm --clean "packaging\mtg_sorter.spec"

$Exe = Join-Path $Root "dist\MTG-Sorter\MTG-Sorter.exe"
if (-not (Test-Path $Exe)) {
    throw "Expected executable at $Exe"
}

$Zip = Join-Path $Root "dist\MTG-Sorter-windows-x64.zip"
Write-Host "==> Creating $Zip"
if (Test-Path $Zip) {
    Remove-Item -Force $Zip
}
Compress-Archive -Path (Join-Path $Root "dist\MTG-Sorter") -DestinationPath $Zip

Write-Host "Built: $Exe"
Write-Host "Zip:   $Zip"
