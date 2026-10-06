Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "  Distributed Cloud Compute Network (DCCN)" -ForegroundColor Green
Write-Host "  Mid-Evaluation Demo Launcher" -ForegroundColor Yellow
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host ""

$RootDir = $PSScriptRoot
Set-Location $RootDir

Write-Host "[1/4] Initializing Database Schema..." -ForegroundColor Cyan
python server\init_db.py

Write-Host ""
Write-Host "[2/4] Starting DCCN Backend Server in background..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootDir\server'; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

Write-Host ""
Write-Host "[3/4] Waiting for server and seeding cluster demo data..." -ForegroundColor Cyan
python agent\seed_demo.py

Write-Host ""
Write-Host "[4/4] Opening DCCN Portal in default browser..." -ForegroundColor Green
Start-Process "http://localhost:8000/login"

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "  DCCN Cluster is LIVE and READY!" -ForegroundColor Green
Write-Host "  - Portal Gateway:     http://localhost:8000/login" -ForegroundColor White
Write-Host "  - Client Portal:      http://localhost:8000/client" -ForegroundColor White
Write-Host "  - Provider Portal:    http://localhost:8000/provider" -ForegroundColor White
Write-Host "  - Admin Console:      http://localhost:8000/admin" -ForegroundColor White
Write-Host "  - Full Dashboard:     http://localhost:8000/dashboard" -ForegroundColor White
Write-Host "  - API Documentation:  http://localhost:8000/docs" -ForegroundColor White
Write-Host "=========================================================" -ForegroundColor Cyan
