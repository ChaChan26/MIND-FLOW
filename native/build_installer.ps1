# MIND-FLOW Release Installer & Portable Packager
# Builds Inno Setup installer executable and portable .zip package.
#
# Author: ChaChan26 <minhharry2006@gmail.com>
# Copyright (c) 2026 ChaChan26. All rights reserved.

param (
    [string]$Version = "2.0.0"
)

$distDir = "$PSScriptRoot\..\dist\MIND-FLOW-Native"
$installerDir = "$PSScriptRoot\..\dist\Installer"
$exePath = "$distDir\MIND-FLOW.exe"

if (-not (Test-Path $exePath)) {
    Write-Host "MIND-FLOW.exe not found. Running package_native.ps1 first..." -ForegroundColor Yellow
    & "$PSScriptRoot\package_native.ps1"
}

if (-not (Test-Path $exePath)) {
    Write-Error "Cannot build installer: $exePath does not exist."
    exit 1
}

New-Item -ItemType Directory -Force -Path $installerDir | Out-Null

# 1. Create Portable Distribution ZIP
$zipPath = "$installerDir\MIND-FLOW-Portable-v$Version-win-x64.zip"
Write-Host "Creating portable distribution archive: $zipPath..." -ForegroundColor Cyan
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path $exePath -DestinationPath $zipPath -Force
Write-Host "Portable archive created successfully: $zipPath" -ForegroundColor Green

# 2. Look for Inno Setup Compiler (ISCC.exe)
$isccCandidates = @(
    "iscc.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
)

$isccPath = $null
foreach ($candidate in $isccCandidates) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        $isccPath = (Get-Command $candidate).Source
        break
    }
    if (Test-Path $candidate) {
        $isccPath = $candidate
        break
    }
}

if ($isccPath) {
    Write-Host "Found Inno Setup Compiler at: $isccPath" -ForegroundColor Cyan
    Write-Host "Compiling setup installer..." -ForegroundColor Yellow
    $issFile = "$PSScriptRoot\installer\mindflow_setup.iss"
    & $isccPath $issFile
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Installer compiled successfully in: $installerDir" -ForegroundColor Green
    } else {
        Write-Warning "Inno Setup compilation exited with code $LASTEXITCODE"
    }
} else {
    Write-Host ""
    Write-Host "[INFO] Inno Setup 6 (ISCC.exe) not found on build machine." -ForegroundColor Gray
    Write-Host "The portable package is ready at: $zipPath" -ForegroundColor Green
    Write-Host "To compile the full Windows Setup installer wizard, install Inno Setup 6 and re-run this script." -ForegroundColor Gray
}
