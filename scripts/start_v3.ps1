$ErrorActionPreference = "Stop"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
Write-Host "QuarantineIQ V3" -ForegroundColor Cyan
Write-Host "Hindsight must already be running at http://localhost:8888" -ForegroundColor Yellow
Write-Host "Backend will run at http://127.0.0.1:8001" -ForegroundColor Green
Write-Host ""
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
