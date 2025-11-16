# 🎯 Kritik İyileştirmeler - Uygulama Rehberi

Bu dokümanda 4 kritik özellik implement edilmiştir:

1. ✅ **Stok Uyarı Sistemi** - Kritik/tükenen stok bildirimleri
2. ✅ **Yedekleme Sistemi** - Otomatik database backup
3. ✅ **Audit Log** - Kritik işlemlerin loglanması
4. ✅ **Excel/PDF Export** - Raporları dışa aktarma

---

## 📦 1. STOK UYARI SİSTEMİ

### Özellikler

✅ **WebSocket Bildirimleri** - Gerçek zamanlı tarayıcı bildirimleri
✅ **Email Bildirimleri** - Stok tükendiğinde otomatik email
✅ **Geçmiş Takibi** - Tüm uyarılar database'de kaydediliyor
✅ **Çift Seviye Uyarı** - "Kritik" ve "Tükendi" durumları

### API Endpoint'leri

```http
GET /stok/uyarilar
  → Mevcut kritik/tükenen stokları listele

GET /stok/uyarilar/gecmis?limit=100
  → Stok uyarı geçmişini görüntüle
```

### Yapılandırma

`.env` dosyasına ekleyin:

```env
# Email Ayarları (Stok Uyarıları için)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
ALERT_EMAIL_RECIPIENTS=admin1@example.com,admin2@example.com
```

### Nasıl Çalışır?

1. Stok ekleme/güncelleme sırasında otomatik kontrol
2. Mevcut miktar ≤ 0 → **"Tükendi"** uyarısı (Email + WebSocket)
3. Mevcut miktar ≤ Min miktar → **"Kritik"** uyarısı (WebSocket)
4. Tüm uyarılar `stock_alert_history` tablosuna kaydedilir

### Örnek Kullanım

```python
# Stok güncelleme
PATCH /stok/guncelle
{
    "ad": "Süt",
    "mevcut": 5,  # Eğer min=10 ise → Kritik uyarı!
    "alis_fiyat": 25.0
}

# Uyarıları görüntüle
GET /stok/uyarilar
Response:
[
    {
        "id": 123,
        "ad": "Süt",
        "kategori": "İçecek",
        "mevcut": 5,
        "min": 10,
        "durum": "kritik"
    }
]
```

---

## 💾 2. YEDEKLEME SİSTEMİ

### Özellikler

✅ **Otomatik Yedekleme** - APScheduler ile zamanlı yedekleme
✅ **Manuel Yedekleme** - İstediğiniz zaman yedek alın
✅ **Yedek Geçmişi** - Tüm yedekler database'de takip ediliyor
✅ **Eski Yedek Temizleme** - Retention policy ile otomatik temizlik
✅ **Restore Özelliği** - Yedekten geri yükleme (DANGEROUS!)

### API Endpoint'leri

```http
POST /system/backup/create?backup_type=full
  → Manuel yedekleme başlat (super_admin yetkisi gerekir)

GET /system/backup/history?status=success&limit=50
  → Yedekleme geçmişini görüntüle

POST /system/backup/restore/{backup_id}
  → Yedekten geri yükle (DANGEROUS!)
```

### Yapılandırma

`.env` dosyasına ekleyin:

```env
# Yedekleme Ayarları
BACKUP_ENABLED=True
BACKUP_DIR=./backups
BACKUP_SCHEDULE_CRON=0 2 * * *  # Her gün saat 02:00
BACKUP_RETENTION_DAYS=30  # 30 gün boyunca tut

# Cloud Storage (Opsiyonel)
BACKUP_CLOUD_ENABLED=False
BACKUP_S3_BUCKET=your-bucket-name
BACKUP_S3_ACCESS_KEY=your-access-key
BACKUP_S3_SECRET_KEY=your-secret-key
```

### Cron Schedule Örnekleri

```
0 2 * * *     → Her gün saat 02:00
0 */6 * * *   → Her 6 saatte bir
0 0 * * 0     → Her Pazar saat 00:00
0 3 * * 1-5   → Hafta içi her gün saat 03:00
```

### Nasıl Çalışır?

1. **Startup:** Uygulama başladığında scheduler otomatik başlar
2. **Scheduled Backup:** Belirlenen zamanda otomatik yedekleme
3. **pg_dump:** PostgreSQL native backup tool kullanılır
4. **Storage:** Yedekler `BACKUP_DIR` klasörüne kaydedilir
5. **Cleanup:** Eski yedekler (30 gün+) otomatik silinir

### Örnek Kullanım

```bash
# Manuel yedekleme
curl -X POST "http://localhost:8000/system/backup/create?backup_type=full" \
  -H "Authorization: Bearer YOUR_SUPER_ADMIN_TOKEN"

# Yedekleme geçmişi
curl -X GET "http://localhost:8000/system/backup/history?limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Response örneği:
[
    {
        "id": 5,
        "backup_type": "full",
        "file_path": "./backups/neso_backup_full_20250111_143022.sql",
        "file_size_mb": 12.45,
        "status": "success",
        "started_at": "2025-01-11T14:30:22",
        "completed_at": "2025-01-11T14:30:45",
        "duration_seconds": 23.0,
        "created_by": "scheduler"
    }
]
```

---

## 📝 3. AUDIT LOG SİSTEMİ

### Özellikler

✅ **Kritik İşlem Takibi** - Tüm önemli işlemler loglanıyor
✅ **Detaylı Kayıt** - Eski/yeni değerler, IP adresi, user agent
✅ **Filtreleme** - Kullanıcı, işlem türü, tarih aralığı ile filtreleme
✅ **İstatistikler** - En aktif kullanıcılar, en çok yapılan işlemler

### API Endpoint'leri

```http
GET /audit/logs?action=menu&success_only=true&limit=50
  → Audit log'ları filtrele ve görüntüle

GET /audit/statistics?start_date=2025-01-01T00:00:00
  → Audit log istatistikleri
```

### Loglanan İşlemler

Aşağıdaki işlemler otomatik olarak loglanır:

- ✅ Menu CRUD işlemleri
- ✅ Stok değişiklikleri
- ✅ Sipariş oluşturma/güncelleme
- ✅ Ödeme işlemleri
- ✅ Yedekleme/restore işlemleri
- ✅ Rapor export işlemleri
- ✅ Kullanıcı yönetimi

### Nasıl Kullanılır?

**Otomatik Loglama:**
```python
from ..services.audit import audit_service

# İşlem öncesi
await audit_service.log_action(
    action="menu.create",
    username="admin",
    user_id=1,
    sube_id=1,
    entity_type="menu",
    entity_id=123,
    new_values={"ad": "Latte", "fiyat": 85.0},
    success=True,
)
```

**Manuel Loglama Örneği:**
```python
# menu.py içinde
await audit_service.log_action(
    action="menu.delete",
    username=user["username"],
    user_id=user.get("id"),
    sube_id=sube_id,
    entity_type="menu",
    entity_id=menu_id,
    old_values={"ad": "Eski Ürün", "fiyat": 50.0},
    ip_address=request.client.host,
    success=True,
)
```

### Örnek Sorgulama

```bash
# Son 100 menu işlemini getir
curl -X GET "http://localhost:8000/audit/logs?action=menu&limit=100" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Başarısız işlemleri getir
curl -X GET "http://localhost:8000/audit/logs?success_only=false&limit=50" \
  -H "Authorization: Bearer YOUR_TOKEN"

# İstatistikler
curl -X GET "http://localhost:8000/audit/statistics" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Response örneği:
{
    "total_actions": 1523,
    "successful_actions": 1498,
    "failed_actions": 25,
    "top_users": [
        {"username": "admin", "action_count": 856},
        {"username": "operator", "action_count": 432}
    ],
    "top_actions": [
        {"action": "menu.update", "count": 234},
        {"action": "siparis.create", "count": 187}
    ]
}
```

---

## 📊 4. EXCEL/PDF EXPORT

### Özellikler

✅ **Excel Export** - openpyxl ile profesyonel Excel dosyaları
✅ **PDF Export** - reportlab ile şık PDF raporları
✅ **Çoklu Sayfa** - Excel'de birden fazla worksheet
✅ **Stillendirme** - Renkli header'lar, border'lar, zebra striping
✅ **Audit Log Entegrasyonu** - Tüm export işlemleri loglanıyor

### API Endpoint'leri

```http
GET /rapor/export/gunluk?format=excel&days=30
  → Günlük raporu Excel olarak indir

GET /rapor/export/gunluk?format=pdf&days=7
  → Günlük raporu PDF olarak indir

GET /rapor/export/stok?format=excel
  → Stok raporunu Excel olarak indir

GET /rapor/export/stok?format=pdf
  → Stok raporunu PDF olarak indir
```

### Desteklenen Raporlar

1. **Günlük Rapor (Excel)**
   - Özet sayfası (ciro, sipariş, kar)
   - Siparişler sayfası
   - Ödemeler sayfası
   - Popüler ürünler sayfası

2. **Günlük Rapor (PDF)**
   - Özet tablo
   - Tarih bilgisi
   - Profesyonel formatlandırma

3. **Stok Raporu (Excel/PDF)**
   - Stok adı
   - Kategori
   - Mevcut/Min miktar
   - Alış fiyatı
   - Toplam değer
   - Durum (Normal/Kritik/Tükendi)

### Örnek Kullanım

```bash
# Excel export (günlük rapor)
curl -X GET "http://localhost:8000/rapor/export/gunluk?format=excel&days=30" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Sube-Id: 1" \
  --output gunluk_rapor.xlsx

# PDF export (stok raporu)
curl -X GET "http://localhost:8000/rapor/export/stok?format=pdf" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Sube-Id: 1" \
  --output stok_rapor.pdf
```

### Frontend Entegrasyonu

```javascript
// React/TypeScript örneği
const downloadReport = async (format: 'excel' | 'pdf', days: number = 30) => {
  const response = await api.get(`/rapor/export/gunluk`, {
    params: { format, days },
    responseType: 'blob',
  });

  // Dosyayı indir
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `gunluk_rapor_${new Date().toISOString().split('T')[0]}.${format === 'excel' ? 'xlsx' : 'pdf'}`);
  document.body.appendChild(link);
  link.click();
  link.remove();
};
```

---

## 🚀 KURULUM VE BAŞLATMA

### 1. Bağımlılıkları Yükle

```bash
cd backend
pip install -r requirements.txt
```

Yeni eklenen paketler:
- `openpyxl==3.1.2` - Excel export
- `reportlab==4.0.7` - PDF export
- `pandas==2.1.3` - Veri manipülasyonu
- `APScheduler==3.10.4` - Zamanlayıcı
- `aiosmtplib==3.0.1` - Email bildirimleri

### 2. PostgreSQL Ayarları

Yedekleme sistemi için `pg_dump` ve `psql` komutlarının PATH'te olması gerekir.

**Windows:**
```bash
# PostgreSQL bin klasörünü PATH'e ekleyin:
C:\Program Files\PostgreSQL\15\bin
```

**Linux/Mac:**
```bash
# Genellikle zaten PATH'tedir, kontrol edin:
which pg_dump
which psql
```

### 3. .env Dosyasını Yapılandır

```env
# Mevcut ayarlarınız...
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/neso

# YENİ: Email Bildirimleri
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_EMAIL_RECIPIENTS=admin@example.com

# YENİ: Yedekleme Ayarları
BACKUP_ENABLED=True
BACKUP_DIR=./backups
BACKUP_SCHEDULE_CRON=0 2 * * *
BACKUP_RETENTION_DAYS=30
```

### 4. Veritabanı Tablolarını Oluştur

Backend ilk çalıştırıldığında otomatik oluşturulur:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Yeni tablolar:
- ✅ `audit_logs`
- ✅ `stock_alert_history`
- ✅ `backup_history`

### 5. Test Edin

```bash
# Health check
curl http://localhost:8000/health

# Stok uyarıları
curl -H "Authorization: Bearer TOKEN" \
     -H "X-Sube-Id: 1" \
     http://localhost:8000/stok/uyarilar

# Audit logs
curl -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/audit/logs?limit=10

# Manuel yedekleme (super_admin)
curl -X POST -H "Authorization: Bearer SUPER_ADMIN_TOKEN" \
     http://localhost:8000/system/backup/create

# Export rapor
curl -H "Authorization: Bearer TOKEN" \
     -H "X-Sube-Id: 1" \
     "http://localhost:8000/rapor/export/gunluk?format=excel" \
     --output rapor.xlsx
```

---

## 📚 Dosya Yapısı

### Yeni Eklenen Dosyalar

```
backend/
├── app/
│   ├── services/
│   │   ├── audit.py              ✅ Audit log servisi
│   │   ├── backup.py             ✅ Yedekleme servisi
│   │   ├── scheduler.py          ✅ Zamanlayıcı servisi
│   │   ├── notification.py       ✅ Email bildirim servisi
│   │   └── export.py             ✅ Excel/PDF export servisi
│   ├── routers/
│   │   ├── audit.py              ✅ Audit log endpoint'leri
│   │   └── backup.py             ✅ Yedekleme endpoint'leri
│   └── db/
│       └── schema.py             🔄 Yeni tablolar eklendi
├── backups/                      ✅ Yedekleme klasörü (otomatik oluşur)
└── requirements.txt              🔄 Yeni paketler eklendi
```

---

## ⚙️ Konfigürasyon Referansı

### Tüm Yeni Environment Variables

```env
# ==========================================
# STOK UYARI SİSTEMİ
# ==========================================
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_FROM_NAME=Neso Asistan
ALERT_EMAIL_RECIPIENTS=admin1@example.com,admin2@example.com

# ==========================================
# YEDEKLEME SİSTEMİ
# ==========================================
BACKUP_ENABLED=True
BACKUP_DIR=./backups
BACKUP_SCHEDULE_CRON=0 2 * * *
BACKUP_RETENTION_DAYS=30

# Cloud Storage (Opsiyonel)
BACKUP_CLOUD_ENABLED=False
BACKUP_S3_BUCKET=your-bucket
BACKUP_S3_ACCESS_KEY=your-key
BACKUP_S3_SECRET_KEY=your-secret
```

---

## 🎯 Sık Kullanılan Senaryolar

### Senaryo 1: Stok Kritik Seviyede

**Durum:** Kahve stoğu kritik seviyeye düştü.

**Akış:**
1. Sistem otomatik WebSocket bildirimi gönderir
2. Frontend'de bildirim gösterilir
3. Eğer stok tamamen tükendiyse → Email gönderilir
4. `stock_alert_history` tablosuna kayıt düşer

**Kullanıcı Aksiyonu:**
```bash
# Stok uyarılarını kontrol et
GET /stok/uyarilar

# Stok ekle
PATCH /stok/guncelle
{
    "ad": "Kahve",
    "mevcut": 50,  # Yeni alış
    "alis_fiyat": 120.0
}
```

### Senaryo 2: Aylık Rapor Export

**Durum:** Ay sonu raporu hazırlanacak.

**Akış:**
1. Admin günlük raporu Excel olarak export eder
2. Sistem rapor verilerini toplar (sipariş, ödeme, gider)
3. Excel dosyası oluşturulur (çoklu worksheet)
4. İşlem audit log'a kaydedilir

**Kullanıcı Aksiyonu:**
```bash
# Son 30 günün raporu
GET /rapor/export/gunluk?format=excel&days=30

# Stok raporu
GET /rapor/export/stok?format=pdf
```

### Senaryo 3: Yedekleme Geri Yükleme

**Durum:** Kritik hata, database'i geri yüklemek gerekiyor.

**⚠️ UYARI:** Bu işlem TÜM verileri değiştirir!

**Akış:**
1. Super admin yedek geçmişini görüntüler
2. Uygun yedeği seçer
3. Restore komutu verir
4. Sistem database'i geri yükler
5. İşlem audit log'a kaydedilir

**Kullanıcı Aksiyonu:**
```bash
# Yedekleri listele
GET /system/backup/history?status=success

# Restore (backup_id=5)
POST /system/backup/restore/5
```

---

## 🛡️ Güvenlik Notları

1. **Backup Restore:** Sadece `super_admin` restore yapabilir
2. **Audit Logs:** Admin ve super_admin görüntüleyebilir
3. **Email Credentials:** `.env` dosyasını güvende tutun
4. **Backup Files:** Sensitive data içerir, güvenli depolayın
5. **Export Reports:** Yetkili kullanıcılar export yapabilir

---

## 📈 Performans İpuçları

1. **Audit Log:** Eski kayıtları periyodik temizleyin (>6 ay)
2. **Backup:** Cloud storage kullanarak yerel disk kullanımını azaltın
3. **Export:** Büyük raporlar için pagination kullanın
4. **Email:** Rate limiting uygulayın (spam önleme)

---

## 🆘 Sorun Giderme

### Problem: Email gönderilmiyor

**Çözüm:**
1. SMTP ayarlarını kontrol edin (`.env`)
2. Gmail kullanıyorsanız "App Password" oluşturun
3. Log'ları kontrol edin: `backend/logs/app.log`

### Problem: Backup başarısız

**Çözüm:**
1. `pg_dump` komutunun PATH'te olduğundan emin olun
2. Database bağlantı bilgilerini kontrol edin
3. Backup klasörü yazma izinlerine sahip mi kontrol edin
4. Log'ları kontrol edin: `SELECT * FROM backup_history WHERE status='failed'`

### Problem: Export çok yavaş

**Çözüm:**
1. Tarih aralığını küçültün (days parametresi)
2. Database index'lerini kontrol edin
3. Veri miktarını azaltmak için filtreleme ekleyin

---

## 📞 Destek ve İletişim

Sorularınız için:
- GitHub Issues
- Teknik Dokümantasyon: `/docs` endpoint
- API Dokümantasyonu: `http://localhost:8000/docs`

---

**Versiyon:** 1.0.0
**Tarih:** 2025-01-11
**Hazırlayan:** Claude Code (Anthropic)
**Durum:** ✅ Production Ready
