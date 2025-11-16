# 🚀 NESO MODÜLER - DEPLOYMENT REHBERİ

## Hızlı Başlangıç (5 Dakika)

### 1. RENDER (Backend) Kurulumu

#### Adım 1: GitHub Repository Bağla
1. [Render Dashboard](https://dashboard.render.com)'a git
2. **New +** → **Web Service** seç
3. GitHub repository'ni bağla
4. Branch: `main` seç

#### Adım 2: Service Ayarları
```
Name: neso-backend
Region: Frankfurt (veya en yakın bölge)
Branch: main
Root Directory: (boş bırak)
Runtime: Python 3
Build Command: cd backend && pip install -r requirements.txt
Start Command: cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
```

#### Adım 3: PostgreSQL Database Oluştur
1. **New +** → **PostgreSQL**
2. Name: `neso-db`
3. Database: `neso`
4. User: `neso`
5. Plan: Starter ($7/ay) veya Standard ($20/ay)

#### Adım 4: Redis Oluştur
1. **New +** → **Redis**
2. Name: `neso-redis`
3. Plan: Starter ($10/ay)

#### Adım 5: Environment Variables
Render Dashboard'da backend service'ine gidip **Environment** sekmesinde:

```
# Database (otomatik eklenir)
DATABASE_URL=<Render otomatik ekler>

# Redis (otomatik eklenir)
REDIS_URL=<Render otomatik ekler>

# Security
SECRET_KEY=<Render'da "Generate" butonuna tıkla>
ENV=production

# CORS
CORS_ORIGINS=https://neso-frontend.vercel.app,https://*.vercel.app

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60

# Media & Storage
MEDIA_ROOT=/opt/render/project/src/backend/media
BACKUP_DIR=/opt/render/project/src/backend/backups

# Optional: OpenAI
OPENAI_API_KEY=<kendi API key'in>
OPENAI_MODEL=gpt-4o-mini

# Optional: TTS
TTS_PROVIDER=google
GOOGLE_TTS_API_KEY=<kendi API key'in>
```

#### Adım 6: Health Check
**Health Check Path**: `/health` olarak ayarla

#### Adım 7: Deploy
**Create Web Service** butonuna tıkla. Render otomatik deploy başlatacak.

---

### 2. VERCEL (Frontend) Kurulumu

#### Adım 1: GitHub Repository Bağla
1. [Vercel Dashboard](https://vercel.com/dashboard)'a git
2. **Add New Project** → GitHub repository'ni seç

#### Adım 2: Project Settings
```
Framework Preset: Vite
Root Directory: frontend-modern
Build Command: npm run build
Output Directory: dist
Install Command: npm install
```

#### Adım 3: Environment Variables
```
VITE_API_URL=https://neso-backend.onrender.com
```
⚠️ **ÖNEMLİ**: Render backend URL'inizi buraya yazın (örn: `https://neso-backend.onrender.com`)

#### Adım 4: Deploy
**Deploy** butonuna tıkla. Vercel otomatik deploy başlatacak.

---

## 📋 Post-Deployment Checklist

### Backend (Render)

- [ ] Deploy başarılı oldu
- [ ] Health check çalışıyor: `https://neso-backend.onrender.com/health`
- [ ] Swagger docs erişilebilir: `https://neso-backend.onrender.com/docs`
- [ ] Database migration başarılı
- [ ] Redis bağlantısı çalışıyor
- [ ] Environment variables doğru ayarlandı

### Frontend (Vercel)

- [ ] Deploy başarılı oldu
- [ ] Frontend yükleniyor: `https://neso-frontend.vercel.app`
- [ ] API bağlantısı çalışıyor (Network tab'da kontrol et)
- [ ] Login sayfası açılıyor
- [ ] CORS hatası yok

### İlk Kurulum

#### 1. Database Migration (Eğer manuel gerekiyorsa)
Render Dashboard'da backend service'ine git → **Shell** → Şu komutları çalıştır:
```bash
cd backend
alembic upgrade head
```

#### 2. Super Admin Oluştur
```bash
# Render Shell'de
cd backend
python -c "
import asyncio
from app.db.database import db
from app.core.security import hash_password
from datetime import datetime

async def create_admin():
    await db.connect()
    try:
        username = 'admin'
        password = 'admin123'
        password_hash = hash_password(password)
        
        await db.execute(
            'INSERT INTO users (username, sifre_hash, role, aktif, created_at) '
            'VALUES (:u, :p, :r, :a, :d) '
            'ON CONFLICT (username) DO UPDATE SET sifre_hash = :p',
            {
                'u': username,
                'p': password_hash,
                'r': 'super_admin',
                'a': True,
                'd': datetime.now()
            }
        )
        print('✅ Super admin oluşturuldu!')
        print(f'   Username: {username}')
        print(f'   Password: {password}')
    finally:
        await db.disconnect()

asyncio.run(create_admin())
"
```

#### 3. Test Et
1. Frontend'e git: `https://neso-frontend.vercel.app`
2. Login yap: `admin` / `admin123`
3. Dashboard'u kontrol et
4. Menü ekle/sipariş ver
5. Her şey çalışıyorsa ✅

---

## 🔧 Sorun Giderme

### Backend Çalışmıyor

**Problem**: Health check fail oluyor
**Çözüm**:
1. Render Dashboard → Logs'a bak
2. Environment variables kontrol et
3. Database URL doğru mu?

**Problem**: Database connection hatası
**Çözüm**:
1. PostgreSQL service'in çalıştığından emin ol
2. `DATABASE_URL` environment variable doğru mu?
3. Database'de `neso` database'i var mı?

**Problem**: Redis connection hatası
**Çözüm**:
- Redis optional, uygulama çalışmaya devam eder
- Ama cache çalışmaz, yavaş olabilir

### Frontend Çalışmıyor

**Problem**: API bağlantısı hatası
**Çözüm**:
1. `VITE_API_URL` doğru mu?
2. Backend CORS ayarları frontend URL'ini içeriyor mu?
3. Browser console'da hata var mı?

**Problem**: Build hatası
**Çözüm**:
1. Vercel Logs'a bak
2. `package.json` dependencies eksik mi?
3. TypeScript hataları var mı?

---

## 🔒 Güvenlik Önerileri

### Production Checklist

- [ ] `SECRET_KEY` generate edildi (Render'da "Generate" kullan)
- [ ] `DEFAULT_ADMIN_PASSWORD` değiştirildi
- [ ] `RATE_LIMIT_PER_MINUTE` aktif (60 veya üzeri)
- [ ] CORS sadece frontend URL'lerini içeriyor
- [ ] Environment variables git'e commit edilmedi
- [ ] Database password güçlü
- [ ] SSL aktif (Render ve Vercel otomatik sağlıyor)

### API Keys

- [ ] OpenAI API key güvenli saklanıyor (Render Environment Variables)
- [ ] Google TTS API key güvenli saklanıyor
- [ ] API keys rotate ediliyor (aylık önerilir)

---

## 📊 Monitoring

### Render Dashboard
- ✅ Uptime monitoring (otomatik)
- ✅ Log streaming (gerçek zamanlı)
- ✅ Metrics (CPU, Memory, Request count)
- ✅ Alerts (email notifications)

### Vercel Dashboard
- ✅ Analytics (traffic, performance)
- ✅ Function logs
- ✅ Build logs
- ✅ Real-time logs

### Ek Monitoring (Önerilen)

**Sentry (Error Tracking)**
```python
# backend/requirements.txt'e ekle
sentry-sdk[fastapi]==1.40.0

# backend/app/main.py'ye ekle
import sentry_sdk
sentry_sdk.init(
    dsn="https://...@sentry.io/...",
    traces_sample_rate=1.0,
)
```

**Uptime Robot (External Monitoring)**
1. [UptimeRobot](https://uptimerobot.com)'a kaydol
2. Monitor ekle:
   - Type: HTTPS
   - URL: `https://neso-backend.onrender.com/health`
   - Interval: 5 minutes

---

## 💰 Maliyet Yönetimi

### Render
- **Starter Plan**: $7/ay (Web) + $7/ay (Database) + $10/ay (Redis) = **$24/ay**
- **Standard Plan**: $25/ay (Web) + $20/ay (Database) + $10/ay (Redis) = **$55/ay**

### Vercel
- **Hobby Plan**: Ücretsiz (100GB bandwidth)
- **Pro Plan**: $20/ay (1TB bandwidth)

### Önerilen Başlangıç
- Render Starter + Vercel Hobby = **~$24/ay**
- Traffic artarsa Standard'a geç

---

## 🔄 Güncelleme Süreci

### Backend Güncelleme
1. GitHub'a push yap
2. Render otomatik detect eder ve deploy başlatır
3. Health check geçerse deploy başarılı

### Frontend Güncelleme
1. GitHub'a push yap
2. Vercel otomatik detect eder ve deploy başlatır
3. Build başarılı olursa deploy başarılı

### Database Migration
```bash
# Render Shell'de
cd backend
alembic upgrade head
```

---

## 📞 Destek

### Render Support
- [Docs](https://render.com/docs)
- [Community](https://community.render.com)
- [Email](support@render.com)

### Vercel Support
- [Docs](https://vercel.com/docs)
- [Community](https://github.com/vercel/vercel/discussions)
- [Email](support@vercel.com)

---

**Son Güncelleme**: 2025-01-XX  
**Versiyon**: 1.0.0



