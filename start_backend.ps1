# Backend Başlatma Script
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  🚀 NESO BACKEND BAŞLATILIYOR..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location "C:\Users\alibu\NesoModuler\backend"

Write-Host "📦 Bağımlılıklar kontrol ediliyor..." -ForegroundColor Yellow
Write-Host ""

Write-Host "✅ Backend hazır!" -ForegroundColor Green
Write-Host "🌐 URL: http://localhost:8000" -ForegroundColor White
Write-Host "📚 Swagger: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Backend başlatılıyor..." -ForegroundColor Yellow
Write-Host ""

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
