@echo off
title Distributed Cloud Compute Network (DCCN)
echo =========================================================
echo   Distributed Cloud Compute Network (DCCN)
echo   Mid-Evaluation Demo Launcher
echo =========================================================
echo.

cd /d "%~dp0"

echo [1/4] Initializing Database Schema...
python server\init_db.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Database initialization failed. Check your Python environment.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/4] Starting DCCN Backend Server in background...
start "DCCN Server" cmd /k "cd /d \"%~dp0server\" && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo.
echo [3/4] Waiting for server and seeding cluster demo data...
python agent\seed_demo.py

echo.
echo [4/4] Opening DCCN Portal in your default browser...
start "" http://localhost:8000/login

echo.
echo =========================================================
echo   DCCN Cluster is LIVE and READY!
echo =========================================================
echo   - Portal Gateway:     http://localhost:8000/login
echo   - Client Portal:      http://localhost:8000/client
echo   - Provider Portal:    http://localhost:8000/provider
echo   - Admin Console:      http://localhost:8000/admin
echo   - Full Dashboard:     http://localhost:8000/dashboard
echo   - API Documentation:  http://localhost:8000/docs
echo =========================================================
echo.
pause
