# SaaS Multi-Tenancy İyileştirmeleri

Bu dokümanda yapılan 3 kritik SaaS iyileştirmesi ve kullanım kılavuzu bulunmaktadır.

## 📋 Yapılan İyileştirmeler

### 1️⃣ Tenant Status Middleware
**Dosya:** `backend/app/core/tenant_middleware.py`

**Ne Yapar:**
- İşletme (tenant) abonelik durumunu kontrol eder
- Suspended, cancelled, expired tenant'ların erişimini engeller
- Trial süresi dolmuş tenant'ları bloklar
- Super admin'ler ve public endpoint'ler bypass edilir

**Kontroller:**
- ✅ Subscription aktif mi? (`status` kontrolü)
- ✅ Trial süresi dolmuş mu? (`trial_bitis` kontrolü)
- ✅ Abonelik süresi dolmuş mu? (`bitis_tarihi` kontrolü)
- ✅ İşletme aktif mi? (`isletmeler.aktif` kontrolü)

**Hata Kodları:**
- `TENANT_NOT_FOUND` - İşletme bulunamadı
- `TENANT_INACTIVE` - İşletme devre dışı
- `SUBSCRIPTION_SUSPENDED` - Abonelik askıya alınmış
- `SUBSCRIPTION_CANCELLED` - Abonelik iptal edilmiş
- `TRIAL_EXPIRED` - Deneme süresi dolmuş
- `SUBSCRIPTION_EXPIRED` - Abonelik süresi dolmuş

**Örnek Response:**
```json
{
  "ok": false,
  "error_code": "SUBSCRIPTION_SUSPENDED",
  "detail": "Aboneliğiniz askıya alınmış. Lütfen ödeme yapın veya destek ile iletişime geçin."
}
```

---

### 2️⃣ Subscription Limit Middleware
**Dosya:** `backend/app/core/tenant_middleware.py`

**Ne Yapar:**
- Subscription planı limitlerini otomatik kontrol eder
- Limit aşımlarını engelleyerek plan upgrade'ini zorunlu kılar
- Read-only (GET) işlemleri bypass edilir

**Kontrol Edilen Limitler:**

| Endpoint | Limit Tipi | Kontrol Edilen Alan |
|----------|-----------|-------------------|
| `/sube/ekle`, `/sube/create` | `max_subeler` | Toplam şube sayısı |
| `/admin/kullanici/ekle`, `/superadmin/user/create` | `max_kullanicilar` | Toplam kullanıcı sayısı |
| `/menu/ekle`, `/menu/create`, `/menu/yukle-csv` | `max_menu_items` | Toplam menü item sayısı |

**Hata Kodları:**
- `LIMIT_EXCEEDED_SUBELER` - Şube limiti aşıldı
- `LIMIT_EXCEEDED_KULLANICILAR` - Kullanıcı limiti aşıldı
- `LIMIT_EXCEEDED_MENU_ITEMS` - Menü item limiti aşıldı

**Örnek Response:**
```json
{
  "ok": false,
  "error_code": "LIMIT_EXCEEDED_MENU_ITEMS",
  "detail": "Menü item limiti aşıldı. Mevcut plan: 100 ürün. Daha fazla ürün eklemek için planınızı yükseltin.",
  "current": 100,
  "limit": 100
}
```

---

### 3️⃣ PostgreSQL Row-Level Security (RLS)
**Dosya:** `backend/alembic/versions/2025_01_02_0000-add_rls_policies.py`

**Ne Yapar:**
- Database seviyesinde tenant izolasyonunu garanti eder
- Uygulama hatası olsa bile tenant'lar birbirlerinin verilerine erişemez
- Super admin'ler tüm verilere erişebilir

**RLS Uygulanan Tablolar:**
1. ✅ `isletmeler` - İşletmeler
2. ✅ `subeler` - Şubeler
3. ✅ `menu` - Menü items
4. ✅ `siparisler` - Siparişler
5. ✅ `odemeler` - Ödemeler
6. ✅ `stok_kalemleri` - Stok
7. ✅ `giderler` - Giderler
8. ✅ `adisyons` - Adisyonlar
9. ✅ `subscriptions` - Abonelikler
10. ✅ `payments` - Ödemeler

**Güvenlik Katmanları:**
```
┌─────────────────────────────────────────────────┐
│  Katman 3: PostgreSQL RLS (Database Level)     │  ← YENİ!
├─────────────────────────────────────────────────┤
│  Katman 2: Middleware (Application Level)      │  ← YENİ!
├─────────────────────────────────────────────────┤
│  Katman 1: Authorization (RBAC + PBAC)         │  ← Mevcut
└─────────────────────────────────────────────────┘
```

---

## 🚀 Kurulum ve Aktivasyon

### 1. Middleware'leri Aktif Et
Middleware'ler zaten `main.py`'ye eklenmiştir ve otomatik çalışacaktır.

```python
# backend/app/main.py içinde:
app.add_middleware(TenantStatusMiddleware)
app.add_middleware(SubscriptionLimitMiddleware)
```

### 2. RLS Politikalarını Uygula

```bash
cd backend

# Migration'ı çalıştır
alembic upgrade head
```

**Kontrol için:**
```sql
-- PostgreSQL'de RLS aktif mi kontrol et
SELECT schemaname, tablename, rowsecurity
FROM pg_tables
WHERE tablename IN ('menu', 'siparisler', 'subeler');
```

---

## 🧪 Test Senaryoları

### Test 1: Suspended Tenant Erişimi
```bash
# 1. Bir tenant'ı suspend et
curl -X PATCH http://localhost:8000/subscription/1/status \
  -H "Authorization: Bearer SUPER_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "suspended"}'

# 2. O tenant'ın kullanıcısı ile API'ye erişmeyi dene
curl http://localhost:8000/menu/liste \
  -H "Authorization: Bearer TENANT_USER_TOKEN" \
  -H "X-Sube-Id: 1"

# Beklenen sonuç: 403 Forbidden
# {
#   "ok": false,
#   "error_code": "SUBSCRIPTION_SUSPENDED",
#   "detail": "Aboneliğiniz askıya alınmış..."
# }
```

### Test 2: Limit Aşımı Kontrolü
```bash
# 1. Basic plan (max 100 menu item) olan tenant ile 100 ürün ekle
# 2. 101. ürünü eklemeyi dene:

curl -X POST http://localhost:8000/menu/ekle \
  -H "Authorization: Bearer TOKEN" \
  -H "X-Sube-Id: 1" \
  -H "Content-Type: application/json" \
  -d '{
    "ad": "Test Ürün 101",
    "fiyat": 50.00,
    "kategori": "Test"
  }'

# Beklenen sonuç: 403 Forbidden
# {
#   "ok": false,
#   "error_code": "LIMIT_EXCEEDED_MENU_ITEMS",
#   "detail": "Menü item limiti aşıldı. Mevcut plan: 100 ürün...",
#   "current": 100,
#   "limit": 100
# }
```

### Test 3: Trial Süresi Dolmuş Tenant
```bash
# 1. Bir tenant'ın trial_bitis tarihini geçmişe çek
UPDATE subscriptions
SET status = 'trial', trial_bitis = NOW() - INTERVAL '1 day'
WHERE isletme_id = 1;

# 2. O tenant ile erişim dene
curl http://localhost:8000/menu/liste \
  -H "Authorization: Bearer TOKEN" \
  -H "X-Sube-Id: 1"

# Beklenen sonuç: 403 Forbidden
# {
#   "ok": false,
#   "error_code": "TRIAL_EXPIRED",
#   "detail": "Deneme süreniz sona ermiş..."
# }
```

### Test 4: RLS Tenant İzolasyonu
```sql
-- PostgreSQL'de direkt sorgu ile test et

-- Tenant A kullanıcısı olarak bağlan
SET SESSION AUTHORIZATION 'tenant_a_user';

-- Tenant B'nin menülerini görmeye çalış (sube_id = 2)
SELECT * FROM menu WHERE sube_id = 2;

-- Beklenen sonuç: 0 rows (RLS engeller)

-- Kendi tenant'ının menülerini görebilir (sube_id = 1)
SELECT * FROM menu WHERE sube_id = 1;

-- Beklenen sonuç: Kendi menüleri gelir
```

### Test 5: Super Admin Bypass
```bash
# Super admin token ile suspended tenant'a erişim
curl http://localhost:8000/menu/liste \
  -H "Authorization: Bearer SUPER_ADMIN_TOKEN" \
  -H "X-Sube-Id: 1"

# Beklenen sonuç: 200 OK (bypass edilir)
```

---

## 📊 Subscription Planları ve Limitler

### Varsayılan Plan Limitleri

| Plan | Şube | Kullanıcı | Menü Item | Aylık Fiyat |
|------|------|----------|-----------|-------------|
| **Trial** | 1 | 3 | 50 | ₺0 (14 gün) |
| **Basic** | 1 | 5 | 100 | ₺299 |
| **Pro** | 5 | 20 | 500 | ₺999 |
| **Enterprise** | Unlimited | Unlimited | Unlimited | ₺2999 |

### Limit Değiştirme

```bash
# Subscription limitlerini güncelle
curl -X PATCH http://localhost:8000/subscription/1 \
  -H "Authorization: Bearer SUPER_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plan_type": "pro",
    "max_subeler": 5,
    "max_kullanicilar": 20,
    "max_menu_items": 500,
    "ayllik_fiyat": 999.00
  }'
```

---

## 🔧 Middleware Özelleştirme

### Yeni Endpoint'e Limit Eklemek

`backend/app/core/tenant_middleware.py` içinde:

```python
# SubscriptionLimitMiddleware class'ında
LIMIT_CHECKS = {
    "/sube/ekle": "subeler",
    "/menu/ekle": "menu_items",
    "/yeni-endpoint/ekle": "yeni_limit_tipi",  # YENİ EKLE
}
```

### Bypass Path Eklemek

```python
# TenantStatusMiddleware class'ında
BYPASS_PATHS = {
    "/health",
    "/auth/token",
    "/yeni-public-endpoint",  # YENİ EKLE
}
```

---

## 🎯 Önemli Notlar

### ⚠️ Dikkat Edilmesi Gerekenler

1. **Super Admin Bypass:** Super admin'ler tüm kontrolleri bypass eder. Super admin yetkisini dikkatli verin.

2. **Backward Compatibility:** Subscription olmayan eski tenant'lar için güvenli mod aktif (izin verir). Ancak tüm tenant'lara subscription atamanız önerilir.

3. **RLS ve Application User:** PostgreSQL RLS, `current_user` değişkenini kullanır. Database connection string'inizde kullanıcı adını doğru set edin.

4. **Performance:** RLS politikaları her sorguya eklenir. Index'lerinizi optimize edin:
   ```sql
   CREATE INDEX idx_user_sube_izinleri_username
   ON user_sube_izinleri(username);
   ```

5. **Monitoring:** Limit aşımları için monitoring ekleyin:
   ```python
   # Log middleware hatalarını
   logger.warning(f"Limit exceeded for tenant {isletme_id}: {limit_type}")
   ```

### 🔒 Güvenlik Best Practices

1. **JWT Token Güvenliği:** Token'ları güvenli saklayın ve düzenli refresh edin
2. **HTTPS Zorunluluğu:** Production'da sadece HTTPS kullanın
3. **Rate Limiting:** API rate limiting ekleyin (mevcut: 120/dakika)
4. **Audit Logging:** Kritik işlemleri logla (subscription değişiklikleri, limit aşımları)
5. **GDPR Compliance:** Tenant data export/delete fonksiyonları ekleyin

---

## 📈 Gelecek İyileştirmeler

### Orta Öncelik
- [ ] Stripe/İyzico ödeme gateway entegrasyonu
- [ ] Otomatik fatura oluşturma
- [ ] Subdomain otomasyonu (tenant1.neso.com)
- [ ] Usage metering (API call tracking)
- [ ] Email notifications (trial ending, payment failed)

### Düşük Öncelik
- [ ] Super admin analytics dashboard
- [ ] Churn analysis
- [ ] Tenant backup/export tools
- [ ] Webhook support
- [ ] Multi-currency support

---

## 📚 İlgili Dosyalar

### Yeni Dosyalar
- `backend/app/core/tenant_middleware.py` - Middleware'ler
- `backend/alembic/versions/2025_01_02_0000-add_rls_policies.py` - RLS migration
- `SAAS_IMPROVEMENTS.md` - Bu dokümantasyon

### Değiştirilen Dosyalar
- `backend/app/main.py` - Middleware entegrasyonu

### İlgili Mevcut Dosyalar
- `backend/app/core/deps.py` - Authorization helpers
- `backend/app/routers/subscription.py` - Subscription management
- `backend/app/db/schema.py` - Database schema

---

## 🤝 Destek

Sorularınız için:
- GitHub Issues
- Teknik Dokümantasyon: `/docs` endpoint
- Super Admin Panel: `http://localhost:8000/superadmin`

---

**Son Güncelleme:** 2025-01-11
**Versiyon:** 1.0.0
**Hazırlayan:** Claude Code (Anthropic)
