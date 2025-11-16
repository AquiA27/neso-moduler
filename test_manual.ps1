# Manuel Test Script - SaaS Middleware Testleri
# PowerShell Script

param(
    [string]$Test = "all"
)

$BASE_URL = "http://localhost:8000"

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  SaaS Middleware Manuel Testler" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Token'ları buraya yapıştırın (quick_test.ps1'den alın)
Write-Host "Token'larınızı girin:" -ForegroundColor Yellow
$ADMIN_TOKEN = Read-Host "Super Admin Token"
$TEST_TOKEN = Read-Host "Test User Token"
$SUBE_ID = Read-Host "Şube ID (default: 1)"

if ($SUBE_ID -eq "") { $SUBE_ID = 1 }

Write-Host ""

# Test Menüsü
if ($Test -eq "all" -or $Test -eq "menu") {
    Write-Host "Hangi testi çalıştırmak istersiniz?" -ForegroundColor Cyan
    Write-Host "1. Suspended Tenant Test" -ForegroundColor White
    Write-Host "2. Menu Limit Test" -ForegroundColor White
    Write-Host "3. Trial Expired Test" -ForegroundColor White
    Write-Host "4. RLS Tenant Isolation Test" -ForegroundColor White
    Write-Host "5. Tüm Testler" -ForegroundColor White
    Write-Host ""
    $choice = Read-Host "Seçim (1-5)"
} else {
    $choice = "5"
}

# Test 1: Suspended Tenant
if ($choice -eq "1" -or $choice -eq "5") {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "TEST 1: Suspended Tenant" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow

    Write-Host ""
    Write-Host "Adım 1: Tenant'ı suspend etmek için SQL çalıştırın:" -ForegroundColor Cyan
    Write-Host @"
UPDATE subscriptions
SET status = 'suspended'
WHERE isletme_id = $SUBE_ID;
"@ -ForegroundColor Gray

    Read-Host "SQL çalıştırdıktan sonra ENTER'a basın"

    Write-Host ""
    Write-Host "Adım 2: Suspended tenant ile erişim denenecek..." -ForegroundColor Cyan

    try {
        $headers = @{
            "Authorization" = "Bearer $TEST_TOKEN"
            "X-Sube-Id" = $SUBE_ID
        }
        $response = Invoke-RestMethod -Uri "$BASE_URL/menu/liste" -Method Get -Headers $headers
        Write-Host "❌ TEST BAŞARISIZ: Suspended tenant erişebildi!" -ForegroundColor Red
    } catch {
        $errorResponse = $_.Exception.Response
        if ($errorResponse.StatusCode -eq 403) {
            Write-Host "✅ TEST BAŞARILI: Suspended tenant engellendi!" -ForegroundColor Green
            $errorBody = $_.ErrorDetails.Message | ConvertFrom-Json
            Write-Host "   Error Code: $($errorBody.error_code)" -ForegroundColor Gray
            Write-Host "   Detail: $($errorBody.detail)" -ForegroundColor Gray
        } else {
            Write-Host "❌ Beklenmeyen hata: $($errorResponse.StatusCode)" -ForegroundColor Red
        }
    }

    Write-Host ""
    Write-Host "Adım 3: Geri almak için SQL çalıştırın:" -ForegroundColor Cyan
    Write-Host @"
UPDATE subscriptions
SET status = 'active'
WHERE isletme_id = $SUBE_ID;
"@ -ForegroundColor Gray

    Read-Host "SQL çalıştırdıktan sonra ENTER'a basın"
}

# Test 2: Menu Limit
if ($choice -eq "2" -or $choice -eq "5") {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "TEST 2: Menu Limit" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow

    Write-Host ""
    Write-Host "Adım 1: Mevcut menu sayısını kontrol edin:" -ForegroundColor Cyan
    Write-Host @"
SELECT COUNT(*) as current_count
FROM menu m
JOIN subeler s ON m.sube_id = s.id
WHERE s.isletme_id = $SUBE_ID;
"@ -ForegroundColor Gray

    $currentCount = Read-Host "Mevcut menu sayısı"

    Write-Host ""
    Write-Host "Adım 2: Limiti mevcut sayıya eşitleyin:" -ForegroundColor Cyan
    Write-Host @"
UPDATE subscriptions
SET max_menu_items = $currentCount
WHERE isletme_id = $SUBE_ID;
"@ -ForegroundColor Gray

    Read-Host "SQL çalıştırdıktan sonra ENTER'a basın"

    Write-Host ""
    Write-Host "Adım 3: Yeni menü eklemeyi deneyin..." -ForegroundColor Cyan

    try {
        $headers = @{
            "Authorization" = "Bearer $TEST_TOKEN"
            "X-Sube-Id" = $SUBE_ID
            "Content-Type" = "application/json"
        }
        $body = @{
            ad = "Limit Test Ürün"
            fiyat = 99.90
            kategori = "Test"
        } | ConvertTo-Json

        $response = Invoke-RestMethod -Uri "$BASE_URL/menu/ekle" -Method Post -Headers $headers -Body $body
        Write-Host "❌ TEST BAŞARISIZ: Limit doluyken menü eklenebildi!" -ForegroundColor Red
    } catch {
        $errorResponse = $_.Exception.Response
        if ($errorResponse.StatusCode -eq 403) {
            Write-Host "✅ TEST BAŞARILI: Menu limit kontrolü çalışıyor!" -ForegroundColor Green
            try {
                $errorBody = $_.ErrorDetails.Message | ConvertFrom-Json
                Write-Host "   Error Code: $($errorBody.error_code)" -ForegroundColor Gray
                Write-Host "   Detail: $($errorBody.detail)" -ForegroundColor Gray
                Write-Host "   Current: $($errorBody.current)" -ForegroundColor Gray
                Write-Host "   Limit: $($errorBody.limit)" -ForegroundColor Gray
            } catch {}
        } else {
            Write-Host "❌ Beklenmeyen hata: $($errorResponse.StatusCode)" -ForegroundColor Red
        }
    }

    Write-Host ""
    Write-Host "Adım 4: Limiti geri yükseltin:" -ForegroundColor Cyan
    Write-Host @"
UPDATE subscriptions
SET max_menu_items = 100
WHERE isletme_id = $SUBE_ID;
"@ -ForegroundColor Gray

    Read-Host "SQL çalıştırdıktan sonra ENTER'a basın"
}

# Test 3: Trial Expired
if ($choice -eq "3" -or $choice -eq "5") {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "TEST 3: Trial Expired" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow

    Write-Host ""
    Write-Host "Adım 1: Trial'ı expire edin:" -ForegroundColor Cyan
    Write-Host @"
UPDATE subscriptions
SET
    status = 'trial',
    trial_baslangic = NOW() - INTERVAL '15 days',
    trial_bitis = NOW() - INTERVAL '1 day'
WHERE isletme_id = $SUBE_ID;
"@ -ForegroundColor Gray

    Read-Host "SQL çalıştırdıktan sonra ENTER'a basın"

    Write-Host ""
    Write-Host "Adım 2: Expired trial ile erişim denenecek..." -ForegroundColor Cyan

    try {
        $headers = @{
            "Authorization" = "Bearer $TEST_TOKEN"
            "X-Sube-Id" = $SUBE_ID
        }
        $response = Invoke-RestMethod -Uri "$BASE_URL/menu/liste" -Method Get -Headers $headers
        Write-Host "❌ TEST BAŞARISIZ: Trial expired tenant erişebildi!" -ForegroundColor Red
    } catch {
        $errorResponse = $_.Exception.Response
        if ($errorResponse.StatusCode -eq 403) {
            Write-Host "✅ TEST BAŞARILI: Trial expired tenant engellendi!" -ForegroundColor Green
            try {
                $errorBody = $_.ErrorDetails.Message | ConvertFrom-Json
                Write-Host "   Error Code: $($errorBody.error_code)" -ForegroundColor Gray
                Write-Host "   Detail: $($errorBody.detail)" -ForegroundColor Gray
            } catch {}
        } else {
            Write-Host "❌ Beklenmeyen hata: $($errorResponse.StatusCode)" -ForegroundColor Red
        }
    }

    Write-Host ""
    Write-Host "Adım 3: Geri almak için SQL çalıştırın:" -ForegroundColor Cyan
    Write-Host @"
UPDATE subscriptions
SET
    status = 'active',
    trial_baslangic = NULL,
    trial_bitis = NULL
WHERE isletme_id = $SUBE_ID;
"@ -ForegroundColor Gray

    Read-Host "SQL çalıştırdıktan sonra ENTER'a basın"
}

# Test 4: RLS Check
if ($choice -eq "4" -or $choice -eq "5") {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "TEST 4: RLS Tenant Isolation" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow

    Write-Host ""
    Write-Host "Adım 1: PostgreSQL'de RLS kontrolü yapın:" -ForegroundColor Cyan
    Write-Host @"
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('menu', 'siparisler', 'subeler', 'odemeler');
"@ -ForegroundColor Gray

    Write-Host ""
    Write-Host "Tüm tablolarda 'rowsecurity = true' olmalı" -ForegroundColor Yellow

    Read-Host "Kontrol ettikten sonra ENTER'a basın"

    Write-Host ""
    Write-Host "Adım 2: Politikaları kontrol edin:" -ForegroundColor Cyan
    Write-Host @"
SELECT tablename, policyname, cmd
FROM pg_policies
WHERE schemaname = 'public'
AND tablename = 'menu';
"@ -ForegroundColor Gray

    Write-Host ""
    Write-Host "Beklenen politikalar:" -ForegroundColor Yellow
    Write-Host "- menu_superadmin_all" -ForegroundColor Gray
    Write-Host "- menu_tenant_isolation" -ForegroundColor Gray

    Read-Host "Kontrol ettikten sonra ENTER'a basın"

    Write-Host ""
    Write-Host "✅ RLS politikaları aktifse test başarılı!" -ForegroundColor Green
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  Testler Tamamlandı!" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Detaylı sonuçlar için TEST_GUIDE.md dosyasına bakın" -ForegroundColor Gray
Write-Host ""
