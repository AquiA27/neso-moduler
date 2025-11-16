# 🧪 SaaS İyileştirmeleri Test Rehberi

Bu rehber, yapılan 3 kritik iyileştirmeyi adım adım test etmeniz için hazırlanmıştır.

## 📋 Test Öncesi Hazırlık

### 1. Backend'i Başlatın

```bash
cd C:\Users\alibu\NesoModuler\backend

# Virtual environment varsa aktif edin
# python -m venv venv
# venv\Scripts\activate  (Windows)

# Dependencies'i yükleyin (gerekirse)
pip install -r requirements.txt

# Backend'i başlatın
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Beklenen Çıktı:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
[STARTUP] Connecting to database...
[STARTUP] Database connected, creating tables...
[STARTUP] Tables created successfully
```

### 2. Database Migration'ı Çalıştırın

```bash
# Yeni terminal açın
cd C:\Users\alibu\NesoModuler\backend

# Migration'ı çalıştır
alembic upgrade head
```

**Beklenen Çıktı:**
```
INFO  [alembic.runtime.migration] Running upgrade -> 2025_01_02_0000, Add Row-Level Security policies
✅ Row-Level Security politikaları başarıyla eklendi!
```

### 3. Health Check

```bash
curl http://localhost:8000/health
```

**Beklenen:**
```json
{
  "status": "ok",
  "timestamp": "2025-01-11T..."
}
```

---

## 🔐 Test 1: Super Admin Token Alın

Önce test için super admin token'a ihtiyacınız var.

### Yöntem 1: Mevcut Super Admin ile Login

```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Token'ı kaydedin:**
```bash
# Windows PowerShell
$TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Linux/Mac
export TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Yöntem 2: Swagger UI Kullanın

1. Tarayıcıda açın: http://localhost:8000/docs
2. Sağ üstteki **Authorize** butonuna tıklayın
3. Username: `admin`, Password: `admin123`
4. **Authorize** tıklayın
5. Artık Swagger'dan direkt test edebilirsiniz

---

## 🧪 TEST SENARYOLARI

## Test 2: Tenant Status Middleware

### 2.1. Normal Tenant (Active) - ✅ Çalışmalı

```bash
# Önce bir test tenant'ı oluşturun (eğer yoksa)
curl -X POST http://localhost:8000/superadmin/quick-setup \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "isletme_ad": "Test Restaurant",
    "sube_ad": "Ana Şube",
    "admin_username": "testadmin",
    "admin_password": "test123",
    "trial_gun": 14
  }'
```

**Response'u not alın - sube_id'yi kullanacağız.**

```bash
# Test admin ile login olun
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testadmin&password=test123"

# Token'ı kaydedin
$TEST_TOKEN = "response'daki access_token"

# Menü listesini çekin (çalışmalı)
curl http://localhost:8000/menu/liste \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -H "X-Sube-Id: 1"
```

**Beklenen:** ✅ 200 OK, menü listesi gelir

---

### 2.2. Suspended Tenant - ❌ Engellenmeli

**PostgreSQL'de çalıştırın (pgAdmin veya psql):**

```sql
-- Test tenant'ının subscription'ını suspend edin
UPDATE subscriptions
SET status = 'suspended'
WHERE isletme_id = (
    SELECT isletme_id FROM subeler WHERE id = 1 LIMIT 1
);

-- Kontrol edin
SELECT s.isletme_id, s.status, i.ad as isletme_adi
FROM subscriptions s
JOIN isletmeler i ON i.id = s.isletme_id;
```

**API'de test edin:**

```bash
curl -v http://localhost:8000/menu/liste \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -H "X-Sube-Id: 1"
```

**Beklenen:** ❌ 403 Forbidden
```json
{
  "ok": false,
  "error_code": "SUBSCRIPTION_SUSPENDED",
  "detail": "Aboneliğiniz askıya alınmış. Lütfen ödeme yapın veya destek ile iletişime geçin."
}
```

**Geri alın:**
```sql
UPDATE subscriptions SET status = 'active' WHERE isletme_id = 1;
```

---

### 2.3. Trial Expired - ❌ Engellenmeli

```sql
-- Trial'ı expire edin
UPDATE subscriptions
SET
    status = 'trial',
    trial_baslangic = NOW() - INTERVAL '15 days',
    trial_bitis = NOW() - INTERVAL '1 day'
WHERE isletme_id = 1;
```

**Test:**
```bash
curl -v http://localhost:8000/menu/liste \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -H "X-Sube-Id: 1"
```

**Beklenen:** ❌ 403 Forbidden
```json
{
  "ok": false,
  "error_code": "TRIAL_EXPIRED",
  "detail": "Deneme süreniz sona ermiş. Lütfen bir plan seçin ve ödeme yapın."
}
```

**Geri alın:**
```sql
UPDATE subscriptions
SET
    status = 'active',
    trial_baslangic = NULL,
    trial_bitis = NULL
WHERE isletme_id = 1;
```

---

### 2.4. Super Admin Bypass - ✅ Çalışmalı

```bash
# Suspended tenant olsa bile super admin erişebilmeli
curl http://localhost:8000/menu/liste \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Sube-Id: 1"
```

**Beklenen:** ✅ 200 OK (super admin bypass eder)

---

## Test 3: Subscription Limit Middleware

### 3.1. Mevcut Kullanımı Görüntüleyin

```bash
curl http://localhost:8000/subscription/1/limits \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "plan_type": "basic",
  "status": "active",
  "limits": {
    "max_subeler": 1,
    "max_kullanicilar": 5,
    "max_menu_items": 100
  },
  "usage": {
    "subeler": 1,
    "kullanicilar": 2,
    "menu_items": 5
  }
}
```

---

### 3.2. Menu Item Limiti Test Et

**Limiti mevcut kullanıma düşürün:**

```sql
-- Mevcut menu sayısını öğrenin
SELECT COUNT(*) as current_count
FROM menu m
JOIN subeler s ON m.sube_id = s.id
WHERE s.isletme_id = 1;

-- Limiti mevcut sayıya eşitleyin (örnek: 5)
UPDATE subscriptions
SET max_menu_items = 5
WHERE isletme_id = 1;
```

**Yeni menü eklemeyi deneyin:**

```bash
curl -X POST http://localhost:8000/menu/ekle \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -H "X-Sube-Id: 1" \
  -H "Content-Type: application/json" \
  -d '{
    "ad": "Limit Test Ürün",
    "fiyat": 99.90,
    "kategori": "Test"
  }'
```

**Beklenen:** ❌ 403 Forbidden
```json
{
  "ok": false,
  "error_code": "LIMIT_EXCEEDED_MENU_ITEMS",
  "detail": "Menü item limiti aşıldı. Mevcut plan: 5 ürün. Daha fazla ürün eklemek için planınızı yükseltin.",
  "current": 5,
  "limit": 5
}
```

**Geri alın:**
```sql
UPDATE subscriptions SET max_menu_items = 100 WHERE isletme_id = 1;
```

---

### 3.3. Şube Limiti Test Et

```sql
-- Şube limitini 1'e düşürün
UPDATE subscriptions
SET max_subeler = 1
WHERE isletme_id = 1;

-- Mevcut şube sayısını kontrol edin
SELECT COUNT(*) FROM subeler WHERE isletme_id = 1;
```

**Yeni şube eklemeyi deneyin:**

```bash
curl -X POST http://localhost:8000/sube/ekle \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "isletme_id": 1,
    "ad": "İkinci Şube Test",
    "adres": "Test Adresi"
  }'
```

**Beklenen:** ❌ 403 Forbidden
```json
{
  "ok": false,
  "error_code": "LIMIT_EXCEEDED_SUBELER",
  "detail": "Şube limiti aşıldı. Mevcut plan: 1 şube. Daha fazla şube eklemek için planınızı yükseltin.",
  "current": 1,
  "limit": 1
}
```

---

### 3.4. GET İşlemleri Bypass - ✅ Çalışmalı

```bash
# Limit dolmuş olsa bile GET istekleri çalışmalı
curl http://localhost:8000/menu/liste \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -H "X-Sube-Id: 1"
```

**Beklenen:** ✅ 200 OK (GET istekleri limit kontrolünden muaf)

---

## Test 4: Row-Level Security (RLS)

### 4.1. İkinci Bir Tenant Oluşturun

```bash
curl -X POST http://localhost:8000/superadmin/quick-setup \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "isletme_ad": "Rakip Restaurant",
    "sube_ad": "Rakip Şube",
    "admin_username": "rakipadmin",
    "admin_password": "rakip123",
    "trial_gun": 14
  }'
```

**Response'daki sube_id'yi not alın (örnek: sube_id = 2)**

---

### 4.2. Her İki Tenant'a Menü Ekleyin

**Tenant 1 (Test Restaurant):**
```bash
curl -X POST http://localhost:8000/menu/ekle \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -H "X-Sube-Id: 1" \
  -H "Content-Type: application/json" \
  -d '{
    "ad": "Tenant 1 Özel Pizza",
    "fiyat": 85.00,
    "kategori": "Pizza"
  }'
```

**Tenant 2 (Rakip Restaurant):**
```bash
# Önce rakip admin token'ını alın
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=rakipadmin&password=rakip123"

$RAKIP_TOKEN = "response'daki token"

curl -X POST http://localhost:8000/menu/ekle \
  -H "Authorization: Bearer $RAKIP_TOKEN" \
  -H "X-Sube-Id: 2" \
  -H "Content-Type: application/json" \
  -d '{
    "ad": "Tenant 2 Özel Burger",
    "fiyat": 95.00,
    "kategori": "Burger"
  }'
```

---

### 4.3. Tenant İzolasyonunu Test Edin

**Tenant 1, Tenant 2'nin menülerini görememeli:**

```bash
# Tenant 1 token'ı ile Tenant 2'nin şubesini sorgula
curl http://localhost:8000/menu/liste \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -H "X-Sube-Id: 2"
```

**Beklenen:** ❌ 403 Forbidden (şube izni yok)

---

### 4.4. Database Seviyesinde RLS Test

**PostgreSQL'de çalıştırın:**

```sql
-- RLS aktif mi kontrol edin
SELECT
    tablename,
    rowsecurity as rls_enabled
FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('menu', 'siparisler', 'subeler', 'odemeler');

-- Beklenen: Tümünde rls_enabled = true

-- Politikaları listeleyin
SELECT
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd
FROM pg_policies
WHERE schemaname = 'public'
AND tablename = 'menu';

-- Beklenen:
-- menu_superadmin_all
-- menu_tenant_isolation
```

---

### 4.5. Super Admin Tüm Verileri Görebilmeli

```bash
# Super admin token'ı ile tüm menüleri çek
curl http://localhost:8000/menu/liste \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Sube-Id: 1"

# Farklı şubeyi de çekebilir
curl http://localhost:8000/menu/liste \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Sube-Id: 2"
```

**Beklenen:** ✅ 200 OK (super admin bypass)

---

## 📊 Test 5: Kombine Senaryo

### Gerçek Dünya Senaryosu

```sql
-- 1. Tenant'ı suspend edin + limiti doldurun
UPDATE subscriptions
SET status = 'suspended',
    max_menu_items = 5
WHERE isletme_id = 1;
```

**Test 1: Suspended tenant menü ekleyemez**
```bash
curl -X POST http://localhost:8000/menu/ekle \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -H "X-Sube-Id: 1" \
  -H "Content-Type: application/json" \
  -d '{"ad": "Test", "fiyat": 50}'
```

**Beklenen:** ❌ 403 SUBSCRIPTION_SUSPENDED (status kontrolü önce çalışır)

```sql
-- 2. Suspend'i kaldırın, sadece limit dolsun
UPDATE subscriptions SET status = 'active' WHERE isletme_id = 1;
```

**Test 2: Limit dolunca engeller**
```bash
curl -X POST http://localhost:8000/menu/ekle \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -H "X-Sube-Id: 1" \
  -H "Content-Type: application/json" \
  -d '{"ad": "Test", "fiyat": 50}'
```

**Beklenen:** ❌ 403 LIMIT_EXCEEDED_MENU_ITEMS

```sql
-- 3. Limiti artırın
UPDATE subscriptions SET max_menu_items = 100 WHERE isletme_id = 1;
```

**Test 3: Artık ekleyebilir**
```bash
curl -X POST http://localhost:8000/menu/ekle \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -H "X-Sube-Id: 1" \
  -H "Content-Type: application/json" \
  -d '{"ad": "Başarılı Test Ürünü", "fiyat": 75.50, "kategori": "Test"}'
```

**Beklenen:** ✅ 201 Created

---

## 🎯 Test Sonuçları Checklist

İşaretleyin:

### Tenant Status Middleware
- [ ] Active tenant erişebiliyor
- [ ] Suspended tenant engellenmiş
- [ ] Cancelled tenant engellenmiş
- [ ] Trial expired tenant engellenmiş
- [ ] Super admin bypass çalışıyor
- [ ] Public endpoint'ler bypass

### Subscription Limit Middleware
- [ ] Menu item limiti çalışıyor
- [ ] Şube limiti çalışıyor
- [ ] Kullanıcı limiti çalışıyor
- [ ] GET istekleri bypass ediliyor
- [ ] Super admin bypass çalışıyor
- [ ] Limit mesajları doğru

### Row-Level Security
- [ ] Tenant izolasyonu çalışıyor
- [ ] RLS politikaları aktif
- [ ] Super admin tüm verileri görebiliyor
- [ ] Tenant A, Tenant B verilerini göremiyor

---

## 🔧 Troubleshooting

### Hata: "Invalid token"
```bash
# Token'ı yeniden alın
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

### Hata: "Database connection failed"
```bash
# .env dosyasındaki DATABASE_URL'i kontrol edin
# PostgreSQL çalışıyor mu?
```

### Hata: "Tablo bulunamadı"
```bash
# Migration'ı çalıştırın
cd backend
alembic upgrade head
```

### RLS çalışmıyor gibi görünüyor
```sql
-- RLS'i manuel kontrol edin
SELECT tablename, rowsecurity
FROM pg_tables
WHERE tablename = 'menu';

-- Eğer false ise:
ALTER TABLE menu ENABLE ROW LEVEL SECURITY;
```

---

## 📝 Test Sonuçlarını Kaydedin

Test sonuçlarınızı kaydetmek için:

```bash
# Test log'u oluşturun
echo "Test Tarihi: $(date)" > test_results.txt
echo "Backend URL: http://localhost:8000" >> test_results.txt
echo "" >> test_results.txt
echo "=== Test Sonuçları ===" >> test_results.txt
```

---

## 🎉 Tüm Testler Başarılı mı?

Evet ise tebrikler! Sisteminiz production-ready! 🚀

Hayır ise:
1. Hata mesajını kopyalayın
2. Hangi test başarısız oldu not alın
3. Troubleshooting bölümüne bakın
4. Hala çözülmediyse loglara bakın: `backend/logs/` veya konsol çıktısı

---

**Test Rehberi Sürümü:** 1.0
**Hazırlanma Tarihi:** 2025-01-11
