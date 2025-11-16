# Quick Test Script - SaaS İyileştirmeleri
# PowerShell Script

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  SaaS İyileştirmeleri Test" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

$BASE_URL = "http://localhost:8000"

# Test 1: Health Check
Write-Host "[1/5] Health Check..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/health" -Method Get
    Write-Host "✅ Backend çalışıyor!" -ForegroundColor Green
    Write-Host "   Status: $($response.status)" -ForegroundColor Gray
} catch {
    Write-Host "❌ Backend çalışmıyor! Önce backend'i başlatın:" -ForegroundColor Red
    Write-Host "   cd backend" -ForegroundColor Gray
    Write-Host "   python -m uvicorn app.main:app --reload" -ForegroundColor Gray
    exit
}

Write-Host ""

# Test 2: Super Admin Login
Write-Host "[2/5] Super Admin Login..." -ForegroundColor Yellow
try {
    $body = @{
        username = "admin"
        password = "admin123"
    }
    $response = Invoke-RestMethod -Uri "$BASE_URL/auth/token" -Method Post -Body $body -ContentType "application/x-www-form-urlencoded"
    $ADMIN_TOKEN = $response.access_token
    Write-Host "✅ Super Admin token alındı!" -ForegroundColor Green
    Write-Host "   Token: $($ADMIN_TOKEN.Substring(0,30))..." -ForegroundColor Gray
} catch {
    Write-Host "❌ Login başarısız! Default admin var mı kontrol edin." -ForegroundColor Red
    exit
}

Write-Host ""

# Test 3: Test Tenant Kontrol Et / Oluştur
Write-Host "[3/5] Test Tenant Kontrol Ediliyor..." -ForegroundColor Yellow

# Önce mevcut tenant'ları listele
try {
    $headers = @{
        "Authorization" = "Bearer $ADMIN_TOKEN"
    }
    $response = Invoke-RestMethod -Uri "$BASE_URL/isletme/liste" -Method Get -Headers $headers

    if ($response -and $response.Count -gt 0) {
        Write-Host "✅ Mevcut tenant bulundu!" -ForegroundColor Green
        $ISLETME_ID = $response[0].id

        # Şube bilgisini al
        $subeResponse = Invoke-RestMethod -Uri "$BASE_URL/sube/liste?isletme_id=$ISLETME_ID" -Method Get -Headers $headers
        $SUBE_ID = $subeResponse[0].id

        Write-Host "   İşletme: $($response[0].ad) (ID: $ISLETME_ID)" -ForegroundColor Gray
        Write-Host "   Şube: $($subeResponse[0].ad) (ID: $SUBE_ID)" -ForegroundColor Gray
        Write-Host "   Mevcut tenant ile devam ediliyor..." -ForegroundColor Gray
    }
} catch {
    Write-Host "⚠️  Tenant bulunamadı, yeni oluşturuluyor..." -ForegroundColor Yellow

    # Yeni tenant oluştur
    try {
        $headers = @{
            "Authorization" = "Bearer $ADMIN_TOKEN"
            "Content-Type" = "application/json"
        }
        $body = @{
            isletme_ad = "Test SaaS Restaurant"
            sube_ad = "Test Şube"
            admin_username = "saastest"
            admin_password = "test12345"
            trial_gun = 14
        } | ConvertTo-Json

        $response = Invoke-RestMethod -Uri "$BASE_URL/superadmin/quick-setup" -Method Post -Headers $headers -Body $body
        $SUBE_ID = $response.sube_id
        $ISLETME_ID = $response.isletme_id

        Write-Host "✅ Yeni tenant oluşturuldu!" -ForegroundColor Green
        Write-Host "   İşletme ID: $ISLETME_ID" -ForegroundColor Gray
        Write-Host "   Şube ID: $SUBE_ID" -ForegroundColor Gray
        Write-Host "   Username: saastest" -ForegroundColor Gray
        Write-Host "   Password: test12345" -ForegroundColor Gray
    } catch {
        Write-Host "⚠️  Varsayılan tenant kullanılıyor..." -ForegroundColor Yellow
        $SUBE_ID = 1
        $ISLETME_ID = 1
    }
}

Write-Host ""

# Test 4: Test User Token Al (veya admin token kullan)
Write-Host "[4/5] Test User Login..." -ForegroundColor Yellow
try {
    $body = @{
        username = "saastest"
        password = "test12345"
    }
    $response = Invoke-RestMethod -Uri "$BASE_URL/auth/token" -Method Post -Body $body -ContentType "application/x-www-form-urlencoded"
    $TEST_TOKEN = $response.access_token
    Write-Host "✅ Test user token alındı!" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Test user bulunamadı, admin token kullanılıyor..." -ForegroundColor Yellow
    $TEST_TOKEN = $ADMIN_TOKEN
}

Write-Host ""

# Test 5: Subscription Limits Kontrol
Write-Host "[5/5] Subscription Limits Kontrolü..." -ForegroundColor Yellow
try {
    $headers = @{
        "Authorization" = "Bearer $ADMIN_TOKEN"
    }
    $response = Invoke-RestMethod -Uri "$BASE_URL/subscription/$ISLETME_ID/limits" -Method Get -Headers $headers

    Write-Host "✅ Subscription bilgileri alındı!" -ForegroundColor Green
    Write-Host "   Plan: $($response.plan_type)" -ForegroundColor Gray
    Write-Host "   Status: $($response.status)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   Limitler:" -ForegroundColor Cyan
    Write-Host "   - Şubeler: $($response.usage.subeler) / $($response.limits.max_subeler)" -ForegroundColor Gray
    Write-Host "   - Kullanıcılar: $($response.usage.kullanicilar) / $($response.limits.max_kullanicilar)" -ForegroundColor Gray
    Write-Host "   - Menü Items: $($response.usage.menu_items) / $($response.limits.max_menu_items)" -ForegroundColor Gray
} catch {
    Write-Host "⚠️  Subscription bilgisi alınamadı" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  Temel Testler Tamamlandı!" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Detaylı testler için:" -ForegroundColor White
Write-Host "1. Swagger UI: $BASE_URL/docs" -ForegroundColor Gray
Write-Host "2. Test Guide: TEST_GUIDE.md" -ForegroundColor Gray
Write-Host "3. Manuel testler: test_manual.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "Token'larınızı kaydedin:" -ForegroundColor White
Write-Host "`$ADMIN_TOKEN = '$ADMIN_TOKEN'" -ForegroundColor Gray
Write-Host "`$TEST_TOKEN = '$TEST_TOKEN'" -ForegroundColor Gray
Write-Host "`$SUBE_ID = $SUBE_ID" -ForegroundColor Gray
Write-Host ""
