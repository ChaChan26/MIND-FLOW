@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo       Starting MIND-FLOW Companion
echo ========================================

if not exist ".venv\Scripts\python.exe" (
    echo [Setup] Virtual environment not found. Initializing .venv...
    where python >nul 2>nul
    if %errorlevel% neq 0 (
        echo [Error] Python is not installed or not in PATH. Please install Python 3.10+ from python.org.
        pause
        exit /b 1
    )
    python -m venv .venv
    echo [Setup] Installing production dependencies...
    .\.venv\Scripts\pip.exe install -r requirements.txt
)

echo [Launch] Starting core application...
.\.venv\Scripts\python.exe app.py
if %errorlevel% neq 0 (
    echo.
    echo [Error] Application exited with code %errorlevel%.
    pause
)

