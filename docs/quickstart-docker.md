# Hızlı Kurulum (Docker)

Bu rehber, Neso modüler sistemini Docker Desktop üzerinde 3–4 gün içinde müşteri demosuna hazır hale getirmek isteyen ekipler içindir. Amaç; backend, frontend, veritabanı ve medya servislerini tek komutla ayağa kaldırmak, ardından müşteri verilerini (menü, stok, personel, reçete) içeri aktarıp markaya özel konfigürasyonları tamamlamaktır.

---

## 1. Önkoşullar

- **Docker Desktop** (Windows 10/11 veya macOS). Linux kullanıyorsanız Docker Engine ve Docker Compose v2 yeterlidir.
- En az 8 GB RAM (PostgreSQL, FastAPI ve Nginx aynı anda çalışacağı için).
- Bu depo ( `NesoModuler` ) çalışma dizinine klonlanmış olmalı.

> İlk kurulum sırasında Docker, Node ve Python imajlarını indireceği için ~3 GB ağ kullanımı bekleyin.

---

## 2. Proje Yapısı (Docker İlgili Dosyalar)

| Yol | Açıklama |
| --- | --- |
| `docker-compose.yml` | Backend, frontend ve PostgreSQL servislerini tanımlar. |
| `backend/Dockerfile` | FastAPI uygulamasını (uvicorn) derleyip çalıştırır. |
| `backend/env.docker` | Docker ortamı için varsayılan API ayarları. Gerektiğinde kopyalayıp özelleştirin. |
| `frontend-modern/Dockerfile` | Vite tabanlı React arayüzünü derleyip Nginx ile sunar. |
| `frontend-modern/docker/nginx.conf` | SPA yönlendirmeleri ve medya proxy ayarları. |

---

## 3. Ortam Değişkenlerini Hazırlama

Varsayılan değerler `backend/env.docker` dosyasında bulunur. Bu dosya Docker Compose tarafından doğrudan kullanılır. Kendi müşteri ortamınız için kopyalayıp düzenleyebilirsiniz:

```powershell
Copy-Item backend/env.docker backend/env.prod
```

Ardından `docker-compose.yml` içindeki `env_file` bölümünü (`./backend/env.docker`) yeni dosya adınızla güncelleyin. Önemli değişkenler:

- `DATABASE_URL`: `postgresql+asyncpg://<user>:<pass>@db:5432/<db>` formatında kalmalı.
- `CORS_ORIGINS`: Frontend erişim URL’lerini ekleyin (`https://<müşteri-domaini>`).
- `DEFAULT_ADMIN_USERNAME`, `DEFAULT_ADMIN_PASSWORD`: İlk giriş bilgileri.
- `SECRET_KEY`: Üretim ortamında mutlaka değiştirin.

TTS/LLM entegrasyonları için gerekli API anahtarlarını aynı dosyaya ekleyebilirsiniz (`GOOGLE_TTS_API_KEY`, `OPENAI_API_KEY`, vb.).

---

## 4. Docker Servislerini Başlatma

Komutu depo kök dizininde çalıştırın:

```powershell
docker compose up --build -d
```

Bu adım aşağıdakileri yapar:

1. PostgreSQL 15 konteynerini oluşturur (`neso-db`).
2. FastAPI backend'ini derleyip ayağa kaldırır (`neso-backend`). Başlangıçta `alembic upgrade head` çalıştırarak tüm migrasyonları uygular.
3. Frontend’i (React + Nginx) derler ve `http://localhost:5173` üzerinde yayınlar (`neso-frontend`).

İlk çalıştırma birkaç dakika sürebilir. Durumu izlemek için:

```powershell
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f db
```

Servisleri durdurmak için:

```powershell
docker compose down
```

Veritabanı ve medya dosyaları named volume’larda (`postgres_data`, `media_data`) saklandığı için `down` komutu verileri silmez. Tüm verileri temizlemek için:

```powershell
docker compose down -v
```

---

## 5. İlk Giriş ve Kontrol Listesi

1. Tarayıcıdan `http://localhost:5173/login` adresine gidin.
2. `backend/env.docker` dosyasında tanımlı admin hesabı ile giriş yapın.
3. Aşağıdaki sayfaları ziyaret ederek ortamı doğrulayın:
   - `Dashboard`: Grafikleri ve metrikleri görüntüleyin.
   - `Menu`: Varsayılan menü boş gelecektir, import adımından sonra kontrol edin.
   - `Kasa`: Masalar ve adisyonlar bölümü giriş sonrası güncellenecek.
   - `System`: Domain/tema ayarları (kurumsal kimlik için).
   - `Superadmin`: Abonelik ve müşteri takibi paneli.

---

## 6. Müşteri Verilerini İçeri Alma (1 Gün)

### 6.1. Menü & Varyasyon

- `Menu` sayfasındaki import butonu (varsa) veya API aracılığıyla CSV/Excel yükleyin.
- Varyasyonlar artık ürün eklenirken tanımlanabildiği için aynı formdan girilebilir.

### 6.2. Personel

- `Personeller` sayfası üzerinden kullanıcı açın veya `backend/scripts/create_users_all.py` script'i ile batch oluşturun.
- Her personele rol (garson, kasiyer, şef) ve şube atayın.

### 6.3. Stok & Reçete

- `Stok` modülünde ürün stoklarını girin.
- `Reçete` sayfasında her menü ürünü için reçete tanımlayın; stok düşümü doğruluğu için kritiktir.

### 6.4. Domain & Marka Kimliği

- `System` sayfasından işletme adı, logo, renk paleti gibi bilgileri girin.
- Üretim ortamında Nginx/Cloudflare üzerinden müşterinin özel domainine reverse proxy ayarlayın. (Örn: `app.musteriadi.com` → Nginx → `neso-frontend` konteyneri)

---

## 7. Super Admin Takibi (Abonelik Kontrolü)

`/superadmin` sayfası üzerinden:

- Aktif müşterilerin abonelik planı, kalan gün, domain doğrulama durumu ve TTS/LLM konfigürasyonları gözlemlenir.
- Yeni müşteri kurulumu için sihirbaz:
  1. Müşteri adı + domain + marka bilgileri.
  2. Admin kullanıcı daveti.
  3. Data import kontrol listesi (menü, stok, reçete).
- Raporlar sekmesinden hangi işletmenin ne kadar süre kaldığı, hangi modülleri aktif kullandığı izlenir.

> Super admin paneli, backend API üzerinden `subscription` ve `isletme` endpoint’lerini kullanır. Eğer daha fazla metrik istenirse bu endpoint’leri genişletin.

---

## 8. Müşteri Asistanı ve BI Asistanı Ayarları

- `Asistan` sayfasından TTS provider, ses tonu ve konuşma hızını seçin.
- `İşletme Asistanı` (BI) sayfasından veri kaynaklarının güncel olduğundan emin olun. Örneğin stok takip hatası varsa raporlar yanlış çıkacaktır.
- Log ve hata incelemesi için backend konteyner loglarına bakın (`docker compose logs -f backend`).

---

## 9. Sık Kullanılan Komutlar

| Komut | Açıklama |
| --- | --- |
| `docker compose up --build -d` | Tüm servileri derleyip çalıştırır. |
| `docker compose restart backend` | Sadece backend’i yeniden başlatır. |
| `docker compose exec backend alembic revision --autogenerate -m "..."` | Yeni migration üretir. |
| `docker compose exec backend pytest` | (Eğer testler eklenirse) backend testlerini çalıştırır. |
| `docker compose exec db psql -U neso -d neso` | Veritabanına bağlanır. |

---

## 10. Üretim Notları

- `SECRET_KEY`, admin şifreleri ve API anahtarlarını mutlaka değiştirin.
- `alembic upgrade head` komutu backend konteyneri her başladığında çalışır; büyük veritabanlarında önceden manuel çalıştırmayı düşünebilirsiniz.
- Medya dosyaları `media_data` volume’unda tutulur. Yedekleme stratejisi belirleyin.
- Gerekiyorsa Redis, Celery gibi ek servisler için docker-compose dosyasını genişletin.

---

## Sonraki Adımlar

1. Müşteri demosu öncesi örnek verileri yükleyip sistemi uçtan uca test edin (sipariş açma, kasa kapama, rapor alma, asistan ile diyalog).
2. Müşteri geri bildirimleri doğrultusunda tema/renk ayarlarını ve ses tonlarını özelleştirin.
3. Domain yönlendirmesi ve SSL kurulumu tamamlandıktan sonra üretim moduna geçin.

Kurulum sırasında sorun yaşarsanız `docs/manual-regression-checklist.md` içindeki maddeleri de kontrol ederek geriye dönük inceleme yapabilirsiniz.



