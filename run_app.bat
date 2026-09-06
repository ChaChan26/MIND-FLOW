@echo off
title MIND-FLOW Launcher
cd /d "%~dp0"
echo =======================================================
echo          Starting MIND-FLOW Desktop Companion
echo =======================================================
echo.
.\.venv\Scripts\python.exe app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with error code %ERRORLEVEL%.
    pause
)
