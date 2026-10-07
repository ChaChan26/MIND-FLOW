@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo       Starting MIND-FLOW (.NET 8 WPF)
echo ========================================

if exist "dist\MIND-FLOW-Native\MIND-FLOW.exe" (
    start "" "dist\MIND-FLOW-Native\MIND-FLOW.exe"
    exit /b 0
)

if exist "build_native\MindFlow.Desktop.exe" (
    start "" "build_native\MindFlow.Desktop.exe"
    exit /b 0
)

if exist "native\src\MindFlow.Desktop\bin\Release\net8.0-windows\MindFlow.Desktop.exe" (
    start "" "native\src\MindFlow.Desktop\bin\Release\net8.0-windows\MindFlow.Desktop.exe"
    exit /b 0
)

echo [Info] Running with dotnet...
dotnet run --project "native\src\MindFlow.Desktop\MindFlow.Desktop.csproj" -c Release
