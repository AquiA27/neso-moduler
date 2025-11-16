# NESO MODÜLER - RESTORAN YÖNETİM SİSTEMİ
## Kapsamlı Proje Dokümantasyonu ve Yapay Zeka Prompt'u

---

## 📋 PROJE ÖZETİ

**Neso Modüler**, çok şubeli restoran/kafe işletmeleri için geliştirilmiş, modern bir yönetim sistemidir. Sistem, menü yönetimi, sipariş takibi, mutfak operasyonları, kasa yönetimi, stok kontrolü, raporlama ve AI destekli müşteri/işletme asistanları içeren kapsamlı bir çözümdür.

**Versiyon:** 0.2.0  
**Teknoloji Stack:** FastAPI (Backend) + React/TypeScript (Frontend) + PostgreSQL (Database)

---

## 🏗️ MİMARİ YAPI

### Backend (FastAPI)
- **Framework:** FastAPI 0.115.5
- **Python Versiyonu:** 3.13+
- **Veritabanı:** PostgreSQL (asyncpg driver)
- **ORM:** Databases (async database library)
- **Kimlik Doğrulama:** JWT (python-jose)
- **Şifreleme:** bcrypt
- **API Dokümantasyonu:** Swagger/OpenAPI (otomatik)

### Frontend (React)
- **Framework:** React 18.2.0
- **Dil:** TypeScript 5.2.2
- **Build Tool:** Vite 5.0.8
- **Routing:** React Router v6
- **State Management:** Zustand 4.4.7
- **HTTP Client:** Axios 1.6.2
- **Styling:** Tailwind CSS 3.3.6
- **Icons:** Lucide React 0.294.0
- **Charts:** Recharts 2.10.3

### Veritabanı
- **DBMS:** PostgreSQL
- **Migration Tool:** Alembic
- **Extension:** unaccent (Türkçe karakter desteği)

---

## 📁 PROJE YAPISI

```
NesoModuler/
├── backend/
│   ├── app/
│   │   ├── core/              # Çekirdek modüller
│   │   │   ├── config.py      # Ayarlar (Settings)
│   │   │   ├── deps.py        # Dependency injection (auth, roles, permissions)
│   │   │   ├── security.py    # JWT, şifreleme
│   │   │   ├── middleware.py  # Hata yakalama, logging
│   │   │   └── observability.py # Rate limiting, request ID
│   │   ├── db/
│   │   │   ├── database.py    # Database connection
│   │   │   └── schema.py      # Tablo oluşturma (CREATE TABLE)
│   │   ├── routers/           # API endpoint'leri
│   │   │   ├── auth.py        # /auth/* - Kimlik doğrulama
│   │   │   ├── menu.py        # /menu/* - Menü CRUD
│   │   │   ├── siparis.py     # /siparis/* - Sipariş yönetimi
│   │   │   ├── mutfak.py      # /mutfak/* - Mutfak kuyruğu
│   │   │   ├── kasa.py        # /kasa/* - Kasa işlemleri
│   │   │   ├── adisyon.py     # /adisyon/* - Adisyon (hesap) yönetimi
│   │   │   ├── stok.py        # /stok/* - Stok yönetimi
│   │   │   ├── recete.py      # /recete/* - Reçete (malzeme) yönetimi
│   │   │   ├── assistant.py   # /assistant/* - Müşteri AI asistanı
│   │   │   ├── bi_assistant.py # /bi-assistant/* - İşletme AI asistanı
│   │   │   ├── analytics.py   # /analytics/* - Analitik
│   │   │   ├── rapor.py       # /rapor/* - Raporlar
│   │   │   ├── giderler.py    # /giderler/* - Gider yönetimi
│   │   │   ├── masalar.py     # /masalar/* - Masa yönetimi
│   │   │   ├── superadmin.py  # /superadmin/* - Süper admin işlemleri
│   │   │   ├── admin.py       # /admin/* - Admin işlemleri
│   │   │   ├── public.py      # /public/* - Public API (müşteri)
│   │   │   └── websocket_router.py # /ws/* - WebSocket bağlantıları
│   │   ├── services/
│   │   │   └── tts.py         # Text-to-Speech servisi
│   │   ├── llm/
│   │   │   └── providers.py   # LLM provider'ları (OpenAI, vb.)
│   │   ├── websocket/
│   │   │   └── manager.py     # WebSocket yönetimi
│   │   └── main.py            # FastAPI uygulaması
│   ├── alembic/               # Database migrations
│   └── requirements.txt       # Python bağımlılıkları
│
├── frontend-modern/
│   ├── src/
│   │   ├── pages/             # Sayfa componentleri
│   │   │   ├── LoginPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── MenuPage.tsx
│   │   │   ├── MutfakPage.tsx
│   │   │   ├── KasaPage.tsx
│   │   │   ├── StokPage.tsx
│   │   │   ├── RecetePage.tsx
│   │   │   ├── RaporlarPage.tsx
│   │   │   ├── GiderlerPage.tsx
│   │   │   ├── MasalarPage.tsx
│   │   │   ├── PersonellerPage.tsx
│   │   │   ├── AssistantPage.tsx
│   │   │   ├── BIAssistantPage.tsx
│   │   │   ├── CustomerChatPage.tsx
│   │   │   ├── CustomerLandingPage.tsx
│   │   │   └── PersonelTerminalPage.tsx
│   │   ├── components/
│   │   │   └── Layout.tsx     # Ana layout (sidebar, header)
│   │   ├── lib/
│   │   │   └── api.ts         # API client (Axios)
│   │   ├── store/
│   │   │   └── authStore.ts   # Zustand auth store
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts # WebSocket hook
│   │   ├── App.tsx            # Ana component
│   │   └── main.tsx           # Entry point
│   └── package.json
```

---

## 🗄️ VERİTABANI ŞEMASI

### Ana Tablolar

#### 1. **isletmeler** (İşletmeler)
- `id` (BIGSERIAL PRIMARY KEY)
- `ad` (TEXT) - İşletme adı
- `vergi_no` (TEXT)
- `telefon` (TEXT)
- `aktif` (BOOLEAN)
- `created_at` (TIMESTAMPTZ)

#### 2. **subeler** (Şubeler)
- `id` (BIGSERIAL PRIMARY KEY)
- `isletme_id` (BIGINT) - FK → isletmeler
- `ad` (TEXT) - Şube adı
- `adres` (TEXT)
- `telefon` (TEXT)
- `aktif` (BOOLEAN)
- `created_at` (TIMESTAMPTZ)

#### 3. **users** (Kullanıcılar)
- `id` (BIGSERIAL PRIMARY KEY)
- `username` (TEXT UNIQUE) - Kullanıcı adı
- `sifre_hash` (TEXT) - Bcrypt hash
- `role` (TEXT) - super_admin, admin, operator, barista, waiter
- `aktif` (BOOLEAN)
- `created_at` (TIMESTAMPTZ)

#### 4. **user_permissions** (Kullanıcı İzinleri)
- `username` (TEXT) - FK → users.username
- `permission_key` (TEXT) - İzin anahtarı
- `enabled` (BOOLEAN)
- PRIMARY KEY (username, permission_key)

#### 5. **menu** (Menü Ürünleri)
- `id` (BIGSERIAL PRIMARY KEY)
- `sube_id` (BIGINT) - FK → subeler
- `ad` (TEXT) - Ürün adı
- `fiyat` (NUMERIC(10,2))
- `kategori` (TEXT)
- `aktif` (BOOLEAN)
- `created_at` (TIMESTAMPTZ)
- UNIQUE (sube_id, unaccent(lower(ad)))

#### 6. **menu_varyasyonlar** (Menü Varyasyonları)
- `id` (BIGSERIAL PRIMARY KEY)
- `menu_id` (BIGINT) - FK → menu
- `ad` (TEXT) - Varyasyon adı (örn: "Orta", "Sade", "Şekerli")
- `ek_fiyat` (NUMERIC(10,2))
- `sira` (INT)
- `aktif` (BOOLEAN)
- UNIQUE (menu_id, ad)

#### 7. **siparisler** (Siparişler)
- `id` (BIGSERIAL PRIMARY KEY)
- `sube_id` (BIGINT)
- `masa` (TEXT) - Masa numarası/adı
- `adisyon_id` (BIGINT) - FK → adisyons (opsiyonel)
- `sepet` (JSONB) - Sipariş detayları
- `durum` (TEXT) - yeni, hazirlaniyor, hazir, iptal, odendi
- `tutar` (NUMERIC(10,2))
- `created_by_user_id` (BIGINT) - FK → users
- `created_at` (TIMESTAMPTZ)

#### 8. **adisyons** (Adisyonlar/Hesaplar)
- `id` (BIGSERIAL PRIMARY KEY)
- `sube_id` (BIGINT) - FK → subeler
- `masa` (TEXT) - Masa numarası/adı
- `acilis_zamani` (TIMESTAMPTZ)
- `kapanis_zamani` (TIMESTAMPTZ)
- `durum` (TEXT) - acik, kapali
- `toplam_tutar` (NUMERIC(10,2)) - Sipariş toplamı
- `odeme_toplam` (NUMERIC(10,2)) - Ödeme toplamı
- `bakiye` (NUMERIC(10,2)) - Kalan bakiye
- `iskonto_orani` (NUMERIC(5,2)) - İskonto yüzdesi

#### 9. **odemeler** (Ödemeler)
- `id` (BIGSERIAL PRIMARY KEY)
- `sube_id` (BIGINT)
- `masa` (TEXT)
- `adisyon_id` (BIGINT) - FK → adisyons (opsiyonel)
- `tutar` (NUMERIC(10,2))
- `odeme_turu` (TEXT) - nakit, kredi_karti, havale
- `iptal` (BOOLEAN)
- `created_at` (TIMESTAMPTZ)

#### 10. **stok** (Stok Kalemleri)
- `id` (BIGSERIAL PRIMARY KEY)
- `sube_id` (BIGINT) - FK → subeler
- `ad` (TEXT) - Stok adı
- `kategori` (TEXT)
- `birim` (TEXT) - kg, lt, adet, vb.
- `mevcut` (NUMERIC(10,2)) - Mevcut miktar
- `min` (NUMERIC(10,2)) - Minimum seviye
- `alis_fiyat` (NUMERIC(10,2)) - Alış fiyatı
- `created_at` (TIMESTAMPTZ)

#### 11. **recete** (Reçeteler - Ürün Malzemeleri)
- `id` (BIGSERIAL PRIMARY KEY)
- `sube_id` (BIGINT) - FK → subeler
- `urun` (TEXT) - Menü ürün adı
- `stok` (TEXT) - Stok kalemi adı
- `miktar` (NUMERIC(10,2)) - Gerekli miktar
- `birim` (TEXT) - Birim

#### 12. **giderler** (Giderler)
- `id` (BIGSERIAL PRIMARY KEY)
- `sube_id` (BIGINT) - FK → subeler
- `kategori` (TEXT) - kira, personel, elektrik, vb.
- `tutar` (NUMERIC(10,2))
- `tarih` (DATE)
- `aciklama` (TEXT)
- `created_at` (TIMESTAMPTZ)

#### 13. **masalar** (Masalar)
- `id` (BIGSERIAL PRIMARY KEY)
- `sube_id` (BIGINT) - FK → subeler
- `masa_adi` (TEXT) - Masa adı
- `durum` (TEXT) - bos, dolu, rezerve
- `kapasite` (INT)

---

## 🔐 KİMLİK DOĞRULAMA VE YETKİLENDİRME

### Roller (Roles)
1. **super_admin** - Tüm yetkilere sahip, sistem yöneticisi
2. **admin** - Şube yöneticisi, menü/stok/sipariş yönetimi
3. **operator** - Operasyonel işlemler, sipariş/ödeme yönetimi
4. **barista** - Mutfak işlemleri, sipariş durumu güncelleme, ödeme ekleme
5. **waiter** - Garson, sipariş ekleme, masa yönetimi

### İzinler (Permissions)
Sistem, rol bazlı varsayılan izinler ve kullanıcı bazlı özel izinler destekler:

**İzin Anahtarları:**
- `menu_ekle`, `menu_guncelle`, `menu_sil`, `menu_varyasyon_yonet`
- `stok_ekle`, `stok_guncelle`, `stok_sil`, `stok_goruntule`
- `siparis_ekle`, `siparis_guncelle`, `siparis_sil`, `siparis_goruntule`
- `odeme_ekle`, `odeme_iptal`, `odeme_goruntule`, `hesap_kapat`
- `adisyon_yonet`, `mutfak_yonet`, `masa_yonet`
- `gider_ekle`, `gider_guncelle`, `gider_sil`, `gider_goruntule`
- `rapor_goruntule`, `rapor_export`
- `personel_yonet`, `personel_goruntule`
- `analytics_goruntule`, `bi_assistant`
- `ayarlar_yonet`

### JWT Token Yapısı
- **Access Token:** Kısa süreli (varsayılan: 24 saat)
- **Refresh Token:** Uzun süreli (yenileme için)
- **Token İçeriği:** `username`, `role`, `sube_id` (opsiyonel)

### API Güvenliği
- Tüm endpoint'ler (public hariç) JWT token gerektirir
- `X-Sube-Id` header'ı ile şube seçimi
- Rate limiting (opsiyonel)
- CORS yapılandırması

---

## 🔌 API ENDPOINT'LERİ

### Kimlik Doğrulama (`/auth/*`)
- `POST /auth/token` - Kullanıcı girişi (username, password)
- `POST /auth/refresh` - Token yenileme
- `GET /auth/me` - Mevcut kullanıcı bilgileri

### Menü Yönetimi (`/menu/*`)
- `GET /menu/liste` - Menü listesi
- `POST /menu/ekle` - Yeni ürün ekle
- `PATCH /menu/guncelle` - Ürün güncelle (id veya ad ile)
- `DELETE /menu/sil` - Ürün sil (id veya ad ile)
- `POST /menu/yukle-csv` - CSV'den toplu yükleme

### Menü Varyasyonları (`/menu-varyasyonlar/*`)
- `GET /menu-varyasyonlar/{menu_id}` - Ürün varyasyonları
- `POST /menu-varyasyonlar/ekle` - Varyasyon ekle
- `PATCH /menu-varyasyonlar/guncelle` - Varyasyon güncelle
- `DELETE /menu-varyasyonlar/sil/{id}` - Varyasyon sil

### Sipariş Yönetimi (`/siparis/*`)
- `POST /siparis/ekle` - Yeni sipariş oluştur
- `GET /siparis/liste` - Sipariş listesi
- `GET /siparis/{id}` - Sipariş detayı
- `PATCH /siparis/{id}/durum` - Sipariş durumu güncelle

### Mutfak (`/mutfak/*`)
- `GET /mutfak/kuyruk` - Mutfak kuyruğu (yeni, hazirlaniyor)
- `GET /mutfak/poll` - Polling için sipariş listesi
- `PATCH /mutfak/durum/{id}` - Sipariş durumu güncelle (yeni → hazirlaniyor → hazir)

### Kasa (`/kasa/*`)
- `GET /kasa/masalar` - Ödeme bekleyen masalar
- `GET /kasa/hesap/ozet/{masa}` - Masa hesap özeti
- `POST /kasa/odeme/ekle` - Ödeme ekle
- `POST /kasa/hesap/kapat` - Hesap kapat

### Adisyon Yönetimi (`/adisyon/*`)
- `POST /adisyon/olustur` - Yeni adisyon oluştur
- `GET /adisyon/acik` - Açık/kapalı adisyonlar (durum filtresi ile)
- `GET /adisyon/masa/{masa}` - Masa adisyonu
- `GET /adisyon/{id}` - Adisyon detayı
- `POST /adisyon/{id}/kapat` - Adisyon kapat
- `PATCH /adisyon/{id}/iskonto` - İskonto uygula

### Stok Yönetimi (`/stok/*`)
- `GET /stok/liste` - Stok listesi
- `POST /stok/ekle` - Stok ekle
- `PATCH /stok/guncelle` - Stok güncelle
- `DELETE /stok/sil` - Stok sil
- `GET /stok/uyarilar` - Stok uyarıları (kritik/tükendi)

### Reçete Yönetimi (`/recete/*`)
- `GET /recete/liste` - Reçete listesi
- `POST /recete/ekle` - Reçete ekle
- `DELETE /recete/sil/{id}` - Reçete sil

### Giderler (`/giderler/*`)
- `GET /giderler/liste` - Gider listesi
- `POST /giderler/ekle` - Gider ekle
- `PATCH /giderler/guncelle` - Gider güncelle
- `DELETE /giderler/sil/{id}` - Gider sil

### Masalar (`/masalar/*`)
- `GET /masalar/liste` - Masa listesi
- `POST /masalar/ekle` - Masa ekle
- `PATCH /masalar/guncelle` - Masa güncelle
- `DELETE /masalar/sil/{id}` - Masa sil

### Raporlar (`/rapor/*`)
- `GET /rapor/gunluk` - Günlük rapor
- `GET /rapor/haftalik` - Haftalık rapor
- `GET /rapor/aylik` - Aylık rapor

### Analitik (`/analytics/*`)
- `GET /analytics/saatlik-yogunluk` - Saatlik yoğunluk
- `GET /analytics/en-cok-tercih-edilen-urunler` - Popüler ürünler
- `GET /analytics/gunluk-ozet` - Günlük özet

### Müşteri Asistanı (`/assistant/*`)
- `POST /assistant/chat` - AI chat (müşteri için)
- `POST /assistant/voice-command` - Sesli komut

### İşletme Asistanı (`/bi-assistant/*`)
- `POST /bi-assistant/chat` - AI chat (işletme sahibi için)

### Public API (`/public/*`)
- `GET /public/menu/{sube_id}` - Public menü (müşteri görünümü)
- `POST /public/siparis` - Public sipariş oluşturma

### WebSocket (`/ws/*`)
- `GET /ws/connect` - WebSocket bağlantı (topics: kitchen, cashier, tables, orders, admin, waiter, stock)
- `GET /ws/connect/auth` - Authenticated WebSocket bağlantı

### Süper Admin (`/superadmin/*`)
- `GET /superadmin/users` - Kullanıcı listesi
- `POST /superadmin/users/upsert` - Kullanıcı ekle/güncelle
- `GET /superadmin/users/{username}/permissions` - Kullanıcı izinleri
- `PUT /superadmin/users/{username}/permissions` - İzinleri güncelle
- `GET /superadmin/permissions/available` - Mevcut izinler
- `GET /superadmin/permissions/role-defaults/{role}` - Rol varsayılan izinleri

---

## 🤖 AI ASİSTANLARI

### 1. Müşteri Asistanı (`/assistant/chat`)
**Amaç:** Müşterilere sipariş verme konusunda yardımcı olmak

**Özellikler:**
- Doğal dil işleme (Türkçe, İngilizce, Fransızca, Almanca, Arapça, İspanyolca)
- Menü ürünlerini anlama ve önerme
- Sipariş parse etme ("2 çay 2 menengiç kahvesi")
- Ürün özelliklerine göre akıllı öneriler:
  - Boğaz ağrısı → Adaçayı, Nane Limon
  - Sütsüz kahve → Türk Kahvesi, Espresso, Americano (Menengiç değil)
  - Kafeinli → Türk Kahvesi, Espresso, Latte
  - Soğuk içecek → Limonata, Soğuk Kahve
- Konuşma geçmişi takibi
- Proaktif öneriler (pasif sorular sormaz)
- Varyasyon yönetimi (Orta, Sade, Şekerli)

**LLM Provider:** OpenAI (gpt-4o-mini) veya diğer provider'lar

### 2. İşletme Asistanı (`/bi-assistant/chat`)
**Amaç:** İşletme sahiplerine finansal, operasyonel ve stratejik analizler sunmak

**Özellikler:**
- Finansal analiz (ciro, gider, kar, marj)
- Stok yönetimi analizi
- Menü performans analizi
- Personel performans değerlendirmesi
- Stratejik öneriler
- Veriye dayalı kararlar

**Veri Kaynakları:**
- Satış verileri
- Stok verileri
- Gider verileri
- Personel performans metrikleri
- Menü fiyatları ve maliyetleri

---

## 🔄 İŞ AKIŞLARI

### Sipariş Akışı
1. **Sipariş Oluşturma:**
   - Müşteri asistanı veya personel terminali üzerinden sipariş oluşturulur
   - Sipariş `durum='yeni'` olarak kaydedilir
   - Adisyon sistemi kullanılıyorsa, otomatik adisyon oluşturulur veya mevcut adisyona eklenir
   - WebSocket ile mutfak ve kasa bilgilendirilir

2. **Mutfak İşleme:**
   - Mutfak sayfasında `durum='yeni'` siparişler görünür
   - Mutfak `durum='hazirlaniyor'` yapar
   - Hazır olduğunda `durum='hazir'` yapar
   - WebSocket ile güncellemeler broadcast edilir

3. **Ödeme ve Kapanış:**
   - Kasa sayfasında ödeme bekleyen masalar görünür
   - Ödeme eklenir (`POST /kasa/odeme/ekle`)
   - Adisyon toplamları güncellenir
   - Bakiye 0 olduğunda adisyon kapatılabilir
   - Sipariş `durum='odendi'` olur

### Adisyon Sistemi
- Her masa için bir veya daha fazla adisyon olabilir
- Adisyon `durum='acik'` iken siparişler eklenebilir
- Adisyon toplamları otomatik hesaplanır:
  - `toplam_tutar`: Sipariş toplamı
  - `odeme_toplam`: Ödeme toplamı (sadece adisyon açılış tarihinden sonraki ödemeler)
  - `bakiye`: `toplam_tutar - odeme_toplam`
- Eski ödemeler yeni adisyonlara karışmaz (temporal filtering)
- Adisyon kapatıldığında `durum='kapali'` olur

### Stok Yönetimi
- Stok kalemleri minimum seviye ile takip edilir
- Stok seviyesi minimumun altına düştüğünde uyarı oluşturulur
- WebSocket ile gerçek zamanlı stok uyarıları
- Reçete sistemi ile ürün maliyetleri hesaplanabilir

---

## 🌐 WEBSOCKET SİSTEMİ

### Topics (Konular)
- `kitchen` - Mutfak güncellemeleri
- `cashier` - Kasa güncellemeleri
- `tables` - Masa durumu güncellemeleri
- `orders` - Sipariş güncellemeleri
- `admin` - Admin bildirimleri
- `waiter` - Garson bildirimleri
- `stock` - Stok uyarıları

### Mesaj Tipleri
- `status_change` - Sipariş durumu değişikliği
- `order_added` - Yeni sipariş
- `stock_alert` - Stok uyarısı
- `payment_added` - Ödeme eklendi
- `adisyon_closed` - Adisyon kapatıldı

---

## 🎨 FRONTEND SAYFALARI

### Yönetim Paneli Sayfaları
1. **LoginPage** - Giriş sayfası
2. **DashboardPage** - Genel bakış, istatistikler
3. **MenuPage** - Menü yönetimi (CRUD, kategori seçimi, varyasyonlar)
4. **MutfakPage** - Mutfak kuyruğu, sipariş durumu güncelleme
5. **KasaPage** - Kasa yönetimi (masalar, adisyonlar, ödeme)
6. **StokPage** - Stok yönetimi (CRUD, uyarılar)
7. **RecetePage** - Reçete yönetimi (ürün-malzeme ilişkileri)
8. **RaporlarPage** - Raporlar ve grafikler
9. **GiderlerPage** - Gider yönetimi
10. **MasalarPage** - Masa yönetimi
11. **PersonellerPage** - Personel yönetimi ve izin yönetimi
12. **AssistantPage** - Müşteri asistanı test sayfası
13. **BIAssistantPage** - İşletme asistanı sayfası

### Müşteri Sayfaları
1. **CustomerLandingPage** - Müşteri giriş sayfası
2. **PublicMenuPage** - Public menü görünümü
3. **CustomerChatPage** - Müşteri chat sayfası (AI asistan)

### Personel Sayfaları
1. **PersonelTerminalPage** - Personel terminali (sipariş ekleme, masa seçimi)

---

## 🔧 KONFİGÜRASYON

### Backend Ayarları (`.env`)
```env
# Uygulama
APP_NAME=Neso Asistan API
VERSION=0.2.0
ENV=dev

# Veritabanı
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/neso

# JWT
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# OpenAI (AI Asistanlar için)
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4o-mini

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
```

### Frontend Ayarları (`.env`)
```env
VITE_API_URL=http://localhost:8000
```

---

## 🚀 KURULUM VE ÇALIŞTIRMA

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend-modern
npm install
npm run dev
```

### Veritabanı
```bash
# PostgreSQL kurulumu ve veritabanı oluşturma
createdb neso
# Tablolar otomatik oluşturulur (startup event)
```

---

## 📊 ÖNEMLİ ÖZELLİKLER

### 1. Çok Şubeli Yapı
- Her şube kendi menüsü, stoku, siparişleri
- `X-Sube-Id` header'ı ile şube seçimi
- Şube bazlı raporlama

### 2. Adisyon Sistemi
- Masa bazlı hesap yönetimi
- Otomatik toplam hesaplama
- Eski ödemelerin yeni adisyonlara karışmaması
- İskonto desteği

### 3. İzin Yönetimi
- Rol bazlı varsayılan izinler
- Kullanıcı bazlı özel izinler
- Super admin tarafından yönetilebilir

### 4. Gerçek Zamanlı Güncellemeler
- WebSocket ile anlık bildirimler
- Mutfak, kasa, stok güncellemeleri
- Tarayıcı push notification desteği

### 5. AI Asistanlar
- Müşteri asistanı: Doğal dil sipariş alma
- İşletme asistanı: Veri analizi ve öneriler
- Çok dilli destek

### 6. Stok Yönetimi
- Minimum seviye takibi
- Otomatik uyarılar
- Reçete bazlı maliyet hesaplama

---

## 🐛 HATA YÖNETİMİ

### Backend Hata Yakalama
- `ErrorMiddleware` tüm hataları yakalar
- Detaylı loglama (structlog)
- Kullanıcı dostu hata mesajları
- Request ID tracking

### Frontend Hata Yönetimi
- Axios interceptor ile otomatik token refresh
- Hata mesajları kullanıcıya gösterilir
- Console logging (development)

---

## 🔒 GÜVENLİK

### Backend
- JWT token authentication
- Bcrypt password hashing
- Role-based access control (RBAC)
- Permission-based access control
- Rate limiting (opsiyonel)
- CORS yapılandırması
- SQL injection koruması (parametreli sorgular)

### Frontend
- Protected routes
- Token storage (localStorage)
- Automatic token refresh
- API error handling

---

## 📝 ÖNEMLİ NOTLAR

### Database Record Erişimi
- `databases` kütüphanesi `Record` objesi döndürür
- `Record` objesi dictionary değildir, `.get()` metodu yoktur
- Erişim: `row["key"]` veya `try-except` ile güvenli erişim

### Menü Ürün Eşleştirme
- `unaccent` extension ile Türkçe karakter desteği
- Normalize edilmiş ürün adları ile eşleştirme
- Case-insensitive arama

### Adisyon Toplam Hesaplama
- Sadece adisyon açılış tarihinden sonraki ödemeler sayılır
- Eski ödemeler otomatik olarak ayrılır (adisyon_id = NULL)
- Toplamlar otomatik güncellenir

### AI Asistan Özellikleri
- Menü sadakati: Sadece menüdeki ürünleri önerir
- Proaktiflik: Pasif sorular sormaz, direkt önerir
- Bağlam yönetimi: Konuşma geçmişini kullanır
- Ürün özellikleri: Boğaz ağrısı, sütsüz kahve gibi özel durumları anlar

---

## 🎯 GELİŞTİRME NOTLARI

### Yeni Özellik Ekleme
1. Backend: Yeni router oluştur veya mevcut router'a endpoint ekle
2. Frontend: Yeni sayfa component'i oluştur veya mevcut sayfaya özellik ekle
3. API Client: `frontend-modern/src/lib/api.ts` dosyasına yeni endpoint ekle
4. Routing: `App.tsx` dosyasına yeni route ekle

### Database Migration
- Alembic kullanılarak migration'lar yönetilir
- Yeni tablo/kolon eklerken migration oluştur

### WebSocket Event Ekleme
1. `backend/app/websocket/manager.py` dosyasına yeni topic ekle
2. `backend/app/routers/websocket_router.py` dosyasına topic'i ekle
3. Frontend'de `useWebSocket` hook'unu kullan

---

## 📚 BAĞIMLILIKLAR

### Backend
- FastAPI 0.115.5
- PostgreSQL (asyncpg)
- JWT (python-jose)
- Bcrypt
- OpenAI (AI asistanlar için)
- WebSocket (FastAPI native)

### Frontend
- React 18.2.0
- TypeScript 5.2.2
- Vite 5.0.8
- React Router v6
- Zustand 4.4.7
- Axios 1.6.2
- Tailwind CSS 3.3.6
- Recharts 2.10.3

---

## 🎓 ÖĞRENME KAYNAKLARI

### FastAPI
- https://fastapi.tiangolo.com/

### React
- https://react.dev/

### PostgreSQL
- https://www.postgresql.org/docs/

### WebSocket
- https://fastapi.tiangolo.com/advanced/websockets/

---

## 📞 DESTEK VE KATKIDA BULUNMA

Bu proje, çok şubeli restoran/kafe işletmeleri için geliştirilmiş açık kaynaklı bir yönetim sistemidir. Geliştirme sürecinde:
- Modüler yapı korunmalı
- Kod kalitesi ve okunabilirlik ön planda tutulmalı
- Güvenlik best practice'leri uygulanmalı
- Kullanıcı deneyimi optimize edilmeli

---

**Son Güncelleme:** 2025-11-06  
**Versiyon:** 0.2.0  
**Lisans:** Özel (Proprietary)

