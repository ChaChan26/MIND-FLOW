# MIND-FLOW Native Single-File Distribution Packager
# Compiles a self-contained, zero-dependency Windows desktop binary.
#
# Author: ChaChan26 <minhharry2006@gmail.com>
# Copyright (c) 2026 ChaChan26. All rights reserved.

param (
    [string]$Configuration = "Release",
    [string]$Runtime = "win-x64",
    [string]$OutputDir = "$PSScriptRoot\..\dist\MIND-FLOW-Native"
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  MIND-FLOW Native Single-File Packager (.NET 8 WPF)     " -ForegroundColor Cyan
Write-Host "  Target: $Runtime | Config: $Configuration              " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$dotnetPath = "C:\Program Files\dotnet\dotnet.exe"
if (-not (Test-Path $dotnetPath)) {
    $dotnetPath = "dotnet"
}

$projectPath = "$PSScriptRoot\src\MindFlow.Desktop\MindFlow.Desktop.csproj"

Write-Host "Running dotnet publish..." -ForegroundColor Yellow
& $dotnetPath publish $projectPath `
    -c $Configuration `
    -r $Runtime `
    --self-contained true `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:EnableCompressionInSingleFile=true `
    -o $OutputDir

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Build Successful!" -ForegroundColor Green
    Write-Host "Standalone binary located at: $OutputDir\MindFlow.Desktop.exe" -ForegroundColor Green
    
    # Rename to clean brand name MIND-FLOW.exe
    if (Test-Path "$OutputDir\MindFlow.Desktop.exe") {
        Copy-Item "$OutputDir\MindFlow.Desktop.exe" "$OutputDir\MIND-FLOW.exe" -Force
        Write-Host "Renamed to: $OutputDir\MIND-FLOW.exe" -ForegroundColor Green
    }
} else {
    Write-Host "`n❌ Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
}
