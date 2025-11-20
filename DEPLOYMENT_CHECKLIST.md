# Deployment Checklist - Vercel & Render

Bu checklist, Vercel (frontend) ve Render (backend) deployment'ı için adım adım kontrol listesidir.

## 📋 Pre-Deployment Kontrolleri

### Backend (Render) Hazırlığı

#### 1. Environment Variables Kontrolü
Render dashboard'da şu environment variables'ları ekleyin:

```env
ENV=prod
SECRET_KEY=<güçlü-random-key-oluşturun>
DATABASE_URL=<render-postgres-url>
CORS_ORIGINS=https://your-frontend-domain.vercel.app,https://your-custom-domain.com
RATE_LIMIT_PER_MINUTE=60
ACCESS_TOKEN_EXPIRE_MINUTES=1440
PASSWORD_MIN_LENGTH=12
BCRYPT_ROUNDS=12

# Opsiyonel
OPENAI_API_KEY=<openai-key>
REDIS_ENABLED=false
BACKUP_ENABLED=true
```

**SECRET_KEY Oluşturma:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### 2. Render.yaml Kontrolü
- ✅ `render.yaml` dosyası mevcut
- ✅ Build command doğru
- ✅ Start command doğru
- ✅ Environment variables tanımlı

#### 3. Database Migration
- Render'da PostgreSQL instance oluşturuldu
- Database URL Render environment variables'a eklendi
- İlk deployment'ta migration'lar otomatik çalışacak

### Frontend (Vercel) Hazırlığı

#### 1. Environment Variables Kontrolü
Vercel dashboard'da şu environment variable'ı ekleyin:

```env
VITE_API_URL=https://your-backend.onrender.com
```

**ÖNEMLİ:** Vercel'de environment variable eklerken:
- Production, Preview, Development için ayrı ayrı ekleyin
- Veya "All Environments" seçeneğini kullanın

#### 2. Vercel.json Kontrolü
- ✅ `vercel.json` dosyası mevcut
- ✅ Build command: `npm run build`
- ✅ Output directory: `dist`
- ✅ SPA routing için rewrites yapılandırılmış

#### 3. Root Directory
Eğer monorepo kullanıyorsanız:
- Vercel'de **Root Directory**: `frontend-modern` olarak ayarlayın

## 🚀 Deployment Adımları

### Backend (Render) Deployment

1. **Render Dashboard'a Giriş**
   - https://dashboard.render.com adresine gidin
   - Login olun

2. **Yeni Web Service Oluştur**
   - "New +" butonuna tıklayın
   - "Web Service" seçin
   - GitHub repository'nizi bağlayın

3. **Service Ayarları**
   - **Name**: `neso-backend` (veya istediğiniz isim)
   - **Environment**: `Python 3`
   - **Build Command**: `cd backend && pip install -r requirements.txt`
   - **Start Command**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Root Directory**: `backend` (eğer monorepo ise)

4. **Environment Variables Ekle**
   - Settings > Environment Variables bölümüne gidin
   - Yukarıdaki environment variables'ları ekleyin

5. **PostgreSQL Database Oluştur**
   - "New +" > "PostgreSQL" seçin
   - Database oluşturun
   - Internal Database URL'yi kopyalayın
   - `DATABASE_URL` environment variable'ına ekleyin

6. **Deploy**
   - "Create Web Service" butonuna tıklayın
   - Build ve deployment sürecini izleyin
   - Logs'u kontrol edin

### Frontend (Vercel) Deployment

1. **Vercel Dashboard'a Giriş**
   - https://vercel.com/dashboard adresine gidin
   - Login olun

2. **Yeni Proje Ekle**
   - "Add New..." > "Project" seçin
   - GitHub repository'nizi seçin

3. **Proje Ayarları**
   - **Framework Preset**: `Vite` veya `Other`
   - **Root Directory**: `frontend-modern` (eğer monorepo ise)
   - **Build Command**: `npm run build` (otomatik algılanır)
   - **Output Directory**: `dist` (otomatik algılanır)
   - **Install Command**: `npm install` (otomatik algılanır)

4. **Environment Variables Ekle**
   - Settings > Environment Variables bölümüne gidin
   - `VITE_API_URL` ekleyin (backend URL'iniz)
   - Production, Preview, Development için ayrı ayrı ekleyin

5. **Deploy**
   - "Deploy" butonuna tıklayın
   - Build sürecini izleyin
   - Deployment URL'ini not edin

## ✅ Post-Deployment Kontrolleri

### Backend Kontrolleri

1. **Health Check**
   ```bash
   curl https://your-backend.onrender.com/health
   ```
   Beklenen: `{"status": "ok"}`

2. **API Docs Kontrolü** (Production'da kapalı olmalı)
   ```bash
   curl https://your-backend.onrender.com/docs
   ```
   Beklenen: 404 veya erişim yok

3. **CORS Kontrolü**
   - Frontend'den API çağrısı yapın
   - Browser console'da CORS hatası olmamalı

4. **Authentication Test**
   - Login endpoint'ini test edin
   - Token alındığını kontrol edin

### Frontend Kontrolleri

1. **Sayfa Yükleniyor mu?**
   - Vercel URL'ine gidin
   - Sayfa yükleniyor mu kontrol edin

2. **API Bağlantısı**
   - Login sayfasına gidin
   - Login yapmayı deneyin
   - Network tab'da API çağrılarını kontrol edin

3. **Routing**
   - Farklı sayfalara navigate edin
   - 404 hatası olmamalı (SPA routing çalışıyor mu?)

4. **Environment Variable**
   - Browser console'da `import.meta.env.VITE_API_URL` kontrol edin
   - Doğru backend URL'i görünüyor mu?

## 🔧 Olası Sorunlar ve Çözümleri

### Backend Sorunları

#### 1. "Module not found" Hatası
**Sorun:** Python dependencies yüklenmemiş
**Çözüm:** 
- `requirements.txt` dosyasını kontrol edin
- Render build logs'u kontrol edin
- `pip install` komutunun çalıştığını doğrulayın

#### 2. "Database connection failed"
**Sorun:** DATABASE_URL yanlış veya database hazır değil
**Çözüm:**
- Render dashboard'da DATABASE_URL'i kontrol edin
- PostgreSQL instance'ın "Available" durumunda olduğunu kontrol edin
- Internal Database URL kullanıyorsanız, external URL kullanmayın

#### 3. "CORS error"
**Sorun:** CORS_ORIGINS'de frontend URL'i yok
**Çözüm:**
- CORS_ORIGINS environment variable'ına frontend URL'ini ekleyin
- Vercel deployment URL'ini ekleyin
- Custom domain varsa onu da ekleyin

#### 4. "SECRET_KEY is not set"
**Sorun:** SECRET_KEY environment variable eksik
**Çözüm:**
- Render dashboard'da SECRET_KEY ekleyin
- Güçlü bir değer kullanın

### Frontend Sorunları

#### 1. "API URL is undefined"
**Sorun:** VITE_API_URL environment variable eksik
**Çözüm:**
- Vercel dashboard'da VITE_API_URL ekleyin
- Deploy sonrası rebuild gerekebilir

#### 2. "404 on refresh"
**Sorun:** SPA routing yapılandırılmamış
**Çözüm:**
- `vercel.json` dosyasında rewrites olduğunu kontrol edin
- Vercel'de "Framework" ayarını kontrol edin

#### 3. "Build failed"
**Sorun:** TypeScript veya build hataları
**Çözüm:**
- Local'de `npm run build` çalıştırın
- Hataları düzeltin
- Git'e commit edip tekrar deploy edin

#### 4. "API calls failing"
**Sorun:** Backend URL yanlış veya CORS sorunu
**Çözüm:**
- VITE_API_URL'in doğru olduğunu kontrol edin
- Backend CORS_ORIGINS'de frontend URL'i olduğunu kontrol edin
- Network tab'da hata mesajlarını kontrol edin

## 📝 Deployment Sonrası Yapılacaklar

1. ✅ **Custom Domain Ayarları**
   - Vercel'de custom domain ekleyin
   - Render'da custom domain ekleyin (opsiyonel)
   - DNS ayarlarını yapın

2. ✅ **SSL Sertifikaları**
   - Vercel otomatik SSL sağlar
   - Render otomatik SSL sağlar

3. ✅ **Monitoring**
   - Render logs'u izleyin
   - Vercel analytics'i aktif edin
   - Error tracking (Sentry) ekleyin

4. ✅ **Backup**
   - Database backup'ı test edin
   - Backup schedule'ı aktif edin

5. ✅ **Performance**
   - Frontend bundle size'ı kontrol edin
   - Backend response time'ı kontrol edin
   - Database query performance'ı kontrol edin

## 🎯 Hızlı Test Komutları

### Backend Test
```bash
# Health check
curl https://your-backend.onrender.com/health

# Version check
curl https://your-backend.onrender.com/version

# Login test (POST)
curl -X POST https://your-backend.onrender.com/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=yourpassword"
```

### Frontend Test
```bash
# Sayfa yükleniyor mu?
curl https://your-frontend.vercel.app

# API URL kontrolü (browser console'da)
console.log(import.meta.env.VITE_API_URL)
```

## 📞 Destek

Sorun yaşarsanız:
1. Render logs'u kontrol edin
2. Vercel build logs'u kontrol edin
3. Browser console'da hataları kontrol edin
4. Network tab'da API çağrılarını kontrol edin

---

**Not:** İlk deployment'ta bazı sorunlar olabilir. Yukarıdaki checklist'i takip ederek sorunları çözebilirsiniz.

