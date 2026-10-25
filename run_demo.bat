@echo off
title Distributed Cloud Compute Network (DCCN)
cd /d "%~dp0"
python run.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Encountered an issue running python run.py.
    pause
)
