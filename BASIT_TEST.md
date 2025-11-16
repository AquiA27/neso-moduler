# 🚀 Basit Test Rehberi (RLS Manuel Yükleme)

## Adım 1: RLS'i PostgreSQL'de Uygula

**pgAdmin veya psql ile:**

1. PostgreSQL'e bağlanın (database: `neso`)
2. `apply_rls_manual.sql` dosyasını açın
3. Tüm SQL'i çalıştırın (Execute/F5)
4. Son satırda şu mesajı görmelisiniz:
   ```
   ✅ Row-Level Security politikaları başarıyla uygulandı!
   ```

**VEYA komut satırından:**

```powershell
# PostgreSQL bin klasörüne gidin (örnek)
cd "C:\Program Files\PostgreSQL\15\bin"

# SQL dosyasını çalıştırın
.\psql -U neso -d neso -f C:\Users\alibu\NesoModuler\apply_rls_manual.sql
```

---

## Adım 2: Backend'i Başlatın

```powershell
cd C:\Users\alibu\NesoModuler\backend
python -m uvicorn app.main:app --reload
```

**Konsol'da görmeli:**
```
[STARTUP] Connecting to database...
[STARTUP] Database connected, creating tables...
[STARTUP] Tables created successfully
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Adım 3: Hızlı Test

**Yeni PowerShell penceresi açın:**

```powershell
cd C:\Users\alibu\NesoModuler
.\quick_test.ps1
```

**5 dakikada:**
- ✅ Backend health check
- ✅ Admin login
- ✅ Test tenant oluşturma
- ✅ Subscription limits kontrolü
- ✅ Token'ları size verecek

---

## Adım 4: Swagger UI ile Test (En Kolay!)

1. **Tarayıcıda açın:** http://localhost:8000/docs

2. **Sağ üstte "Authorize" tıklayın:**
   - Username: `admin`
   - Password: `admin123`
   - **Authorize** butonuna bas

3. **Test endpoint'leri deneyin:**

### Test 1: Subscription Limits Görüntüle
- `/subscription/{isletme_id}/limits` GET
- `isletme_id`: 1 girin
- **Execute**

**Beklenen:**
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

### Test 2: Yeni Test Tenant Oluştur
- `/superadmin/quick-setup` POST
- Request body:
```json
{
  "isletme_ad": "Test Lokanta",
  "sube_ad": "Ana Şube",
  "admin_username": "testuser",
  "admin_password": "test123",
  "trial_gun": 14
}
```
- **Execute**

**Response'da `sube_id` ve `isletme_id` not alın!**

---

## Adım 5: Middleware Testleri

### Test A: Suspended Tenant (PostgreSQL'de)

**pgAdmin'de çalıştırın:**
```sql
-- Tenant'ı suspend et
UPDATE subscriptions
SET status = 'suspended'
WHERE isletme_id = 1;
```

**Swagger'da test edin:**
- `/menu/liste` GET
- Headers: `X-Sube-Id: 1`
- Test user token kullan
- **Execute**

**Beklenen:** 403 Forbidden
```json
{
  "ok": false,
  "error_code": "SUBSCRIPTION_SUSPENDED",
  "detail": "Aboneliğiniz askıya alınmış..."
}
```

**Geri al:**
```sql
UPDATE subscriptions SET status = 'active' WHERE isletme_id = 1;
```

---

### Test B: Menu Limit

**pgAdmin'de:**
```sql
-- Limiti düşür
UPDATE subscriptions
SET max_menu_items = 5
WHERE isletme_id = 1;

-- Mevcut menu sayısını kontrol et
SELECT COUNT(*) FROM menu m
JOIN subeler s ON m.sube_id = s.id
WHERE s.isletme_id = 1;
```

**Swagger'da:**
- `/menu/ekle` POST
- Request body:
```json
{
  "ad": "Limit Test Pizza",
  "fiyat": 85.50,
  "kategori": "Pizza"
}
```
- **Execute**

**Eğer 5+ menü varsa:**
**Beklenen:** 403 Forbidden
```json
{
  "ok": false,
  "error_code": "LIMIT_EXCEEDED_MENU_ITEMS",
  "detail": "Menü item limiti aşıldı...",
  "current": 5,
  "limit": 5
}
```

**Geri al:**
```sql
UPDATE subscriptions SET max_menu_items = 100 WHERE isletme_id = 1;
```

---

## Adım 6: RLS Kontrolü

**PostgreSQL'de:**
```sql
-- RLS aktif mi?
SELECT tablename, rowsecurity
FROM pg_tables
WHERE tablename IN ('menu', 'siparisler', 'subeler');

-- Beklenen: Hepsinde rowsecurity = true
```

```sql
-- Politikaları listele
SELECT tablename, policyname, cmd
FROM pg_policies
WHERE schemaname = 'public'
AND tablename = 'menu';

-- Beklenen:
-- menu_superadmin_all (ALL)
-- menu_tenant_isolation (ALL)
```

---

## ✅ Test Checklist

Tamamladıkça işaretleyin:

- [ ] RLS SQL dosyası çalıştırıldı
- [ ] Backend başlatıldı
- [ ] Swagger UI'da admin login yapıldı
- [ ] Subscription limits görüntülendi
- [ ] Test tenant oluşturuldu
- [ ] Suspended tenant testi yapıldı (403 aldı)
- [ ] Menu limit testi yapıldı (403 aldı)
- [ ] RLS politikaları kontrol edildi (aktif)

---

## 🎉 Tüm Testler Başarılı!

Eğer tüm testler geçtiyse, sisteminiz hazır!

**Sonraki adımlar:**
1. Production'a deploy
2. Gerçek tenant'ları ekle
3. Ödeme gateway entegrasyonu
4. Monitoring setup

---

## 🆘 Sorun mu Var?

### Backend başlamıyor
```powershell
# Port kullanımda olabilir
netstat -ano | findstr :8000
# PID'yi not alın
taskkill /PID <PID> /F
```

### PostgreSQL'e bağlanamıyor
- PostgreSQL çalışıyor mu? (Services'te kontrol edin)
- .env dosyasındaki DATABASE_URL doğru mu?
  ```
  DATABASE_URL=postgresql+asyncpg://neso:neso123@localhost:5432/neso
  ```

### RLS hata veriyor
- Tablolar var mı kontrol edin:
  ```sql
  SELECT tablename FROM pg_tables
  WHERE schemaname = 'public'
  AND tablename IN ('menu', 'subeler', 'siparisler');
  ```

### Token geçersiz
- Swagger'da yeniden Authorize yapın
- Token 24 saat geçerli (config'de değiştirilebilir)

---

**Test Sürümü:** 1.0
**Hazırlanma:** 2025-01-11
