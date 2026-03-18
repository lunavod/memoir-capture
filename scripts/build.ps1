# Memoir build script
# Prerequisites: Visual Studio 2022, Python 3.x, NVIDIA GPU with NVENC
#
# First-time setup:
#   git clone https://github.com/microsoft/vcpkg.git vcpkg --depth 1
#   .\vcpkg\bootstrap-vcpkg.bat -disableMetrics
#
# Then run this script:
#   .\scripts\build.ps1

param(
    [string]$Preset = "default",
    [string]$BuildPreset = "release"
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root

try {
    # Check vcpkg
    if (-not (Test-Path "vcpkg/vcpkg.exe")) {
        Write-Host "vcpkg not found. Run:" -ForegroundColor Red
        Write-Host "  git clone https://github.com/microsoft/vcpkg.git vcpkg --depth 1"
        Write-Host "  .\vcpkg\bootstrap-vcpkg.bat -disableMetrics"
        exit 1
    }

    Write-Host "=== Configuring ($Preset) ===" -ForegroundColor Cyan
    cmake --preset $Preset
    if ($LASTEXITCODE -ne 0) { throw "Configure failed" }

    Write-Host "=== Building ($BuildPreset) ===" -ForegroundColor Cyan
    cmake --build build --preset $BuildPreset
    if ($LASTEXITCODE -ne 0) { throw "Build failed" }

    Write-Host "=== Build complete ===" -ForegroundColor Green
    Write-Host "Run: python tests/python/test_import.py"
} finally {
    Pop-Location
}
