# Deployment Önerileri - Geliştirme ve Güvenlik

Bu doküman, Neso Modüler projesinin production ortamına deploy edilmeden önce dikkate alınması gereken geliştirme ve güvenlik önerilerini içermektedir.

## 🔒 Güvenlik Önerileri

### 1. **Kritik Güvenlik Düzeltmeleri (Zorunlu)**

#### 1.1 Environment Variables Güvenliği
- ✅ **SECRET_KEY**: Production'da mutlaka güçlü, rastgele bir değer kullanın
  ```bash
  # Güçlü SECRET_KEY oluşturma:
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- ✅ **DATABASE_URL**: Production veritabanı şifreleri güçlü olmalı
- ✅ **OPENAI_API_KEY**: API key'ler .env dosyasında saklanmalı, Git'e commit edilmemeli

**Önerilen Backend .env.example:**
```env
# Backend Environment Variables
ENV=prod
SECRET_KEY=<generate-strong-random-key>
DATABASE_URL=postgresql+asyncpg://user:strong_password@host:5432/dbname
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
RATE_LIMIT_PER_MINUTE=60
ACCESS_TOKEN_EXPIRE_MINUTES=1440
PASSWORD_MIN_LENGTH=12
OPENAI_API_KEY=sk-...
REDIS_ENABLED=false
BACKUP_ENABLED=true
```

**Önerilen Frontend .env.example:**
```env
# Frontend Environment Variables
VITE_API_URL=https://api.yourdomain.com
```

#### 1.2 CORS Yapılandırması
**Sorun:** `CORS_ALLOW_HEADERS: ["*"]` ve `CORS_ALLOW_METHODS: ["*"]` çok açık.

**Çözüm:**
```python
# backend/app/core/config.py
CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS: List[str] = [
    "Content-Type",
    "Authorization",
    "X-Sube-Id",
    "X-Tenant-Id",
    "X-Request-ID"
]
```

#### 1.3 Rate Limiting
**Sorun:** `RATE_LIMIT_PER_MINUTE: int = 0` (devre dışı)

**Çözüm:**
```python
# Production'da aktif et:
RATE_LIMIT_PER_MINUTE=60  # API endpoints için
RATE_LIMIT_PER_MINUTE=120  # Public endpoints için
RATE_LIMIT_PER_MINUTE=30   # Assistant endpoints için
```

#### 1.4 Debug Endpoint'lerini Kaldır
**Sorun:** `auth_debug.py` production'da bulunmamalı.

**Çözüm:**
```python
# backend/app/main.py
# Production'da debug router'ı kaldır:
if settings.ENV != "prod":
    from .routers.auth_debug import router as debug_router
    app.include_router(debug_router)
```

#### 1.5 Varsayılan Admin Kullanıcısı
**Sorun:** Zayıf varsayılan şifreler (`admin123`)

**Çözüm:**
- İlk kurulumdan sonra varsayılan admin'i değiştirin
- Production'da varsayılan admin oluşturmayı devre dışı bırakın
- Minimum şifre uzunluğunu 12 karaktere çıkarın

#### 1.6 API Documentation Erişimi
**Sorun:** `/docs` ve `/redoc` production'da herkese açık.

**Çözüm:**
```python
# backend/app/main.py
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url="/docs" if settings.ENV != "prod" else None,
    redoc_url="/redoc" if settings.ENV != "prod" else None,
)
```

### 2. **Güvenlik İyileştirmeleri (Önerilen)**

#### 2.1 HTTPS Zorunluluğu
- Production'da mutlaka HTTPS kullanın
- HTTP'den HTTPS'ye redirect ekleyin
- HSTS (HTTP Strict Transport Security) header'ı ekleyin

#### 2.2 Content Security Policy (CSP)
Frontend'e CSP header'ları ekleyin:
```typescript
// vite.config.ts - build sonrası nginx/apache'de de eklenebilir
export default defineConfig({
  // ...
  server: {
    headers: {
      "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
    }
  }
})
```

#### 2.3 SQL Injection Koruması
✅ **İyi:** Parametreli sorgular kullanılıyor
⚠️ **Dikkat:** String concatenation ile sorgu oluşturulmuyor (güzel)

#### 2.4 XSS Koruması
- Frontend'de user input'ları sanitize edin
- React otomatik XSS koruması var ama ek kontroller eklenebilir

#### 2.5 Input Validation
- Backend'de Pydantic modelleri ile validation var (güzel)
- Ek olarak, tüm user input'ları için strict validation ekleyin

#### 2.6 Password Policy
✅ **İyi:** bcrypt kullanılıyor
⚠️ **İyileştirme:** Minimum şifre uzunluğunu 12 karaktere çıkarın
```python
# backend/app/core/security.py
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
```

### 3. **Logging ve Monitoring**

#### 3.1 Sensitive Data Censoring
✅ **İyi:** Log'larda hassas veriler gizleniyor (`censor_sensitive_data`)

#### 3.2 Production Logging
```python
# Production'da structured logging kullanın
# backend/app/core/logging_config.py
if settings.ENV == "prod":
    setup_logging(log_level="INFO", json_logs=True)
else:
    setup_logging(log_level="DEBUG", json_logs=False)
```

#### 3.3 Error Tracking
- Sentry veya benzeri bir error tracking servisi entegre edin
- Production hatalarını izleyin ve alert'ler kurun

## 🚀 Geliştirme Önerileri

### 1. **Kod Kalitesi**

#### 1.1 Code Duplication
**Sorun:** Record objesi dict'e çevirme tekrarlanıyor.

**Çözüm:**
```python
# backend/app/core/utils.py
def safe_dict(record: Any) -> Dict[str, Any]:
    """Safely convert database Record to dict"""
    if record is None:
        return {}
    if isinstance(record, dict):
        return record
    if hasattr(record, 'keys'):
        return dict(record)
    return {}
```

#### 1.2 Type Hints
✅ **İyi:** Type hints kullanılıyor
⚠️ **İyileştirme:** Tüm fonksiyonlara type hints ekleyin

#### 1.3 Error Handling
- Daha spesifik exception handling
- Kullanıcı dostu hata mesajları
- Error code sistemi ekleyin

### 2. **Test Coverage**

#### 2.1 Unit Tests
```python
# tests/test_auth.py
# tests/test_menu.py
# tests/test_subscriptions.py
```

#### 2.2 Integration Tests
```python
# tests/integration/test_api.py
```

#### 2.3 Test Framework
- pytest kullanın
- Test coverage minimum %70 olmalı

### 3. **Performance**

#### 3.1 Database Indexing
Kritik sorgular için index'ler ekleyin:
```sql
-- Örnek index'ler
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_siparisler_sube_id ON siparisler(sube_id);
CREATE INDEX idx_menu_sube_id ON menu(sube_id);
CREATE INDEX idx_subscriptions_isletme_id ON subscriptions(isletme_id);
```

#### 3.2 Caching Strategy
✅ **İyi:** Redis cache sistemi var
⚠️ **İyileştirme:**
- Menu listesi için cache kullanın
- Statistics için cache kullanın
- Cache TTL'leri optimize edin

#### 3.3 Database Connection Pooling
✅ **İyi:** Connection pooling yapılandırılmış
⚠️ **İyileştirme:** Production'da pool size'ları optimize edin

#### 3.4 Query Optimization
- N+1 query problemlerini kontrol edin
- Gerekli yerlerde JOIN kullanın (zaten kullanılıyor)
- Pagination ekleyin (bazı yerlerde var)

### 4. **Frontend Optimizasyonları**

#### 4.1 Build Optimizations
```typescript
// vite.config.ts
export default defineConfig({
  build: {
    sourcemap: false,  // Production'da kapat
    minify: 'terser',
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          charts: ['recharts'],
        }
      }
    }
  }
})
```

#### 4.2 Environment Variables
```typescript
// Frontend'de sadece public env var'lar olmalı
// VITE_API_URL production'da doğru URL'e set edilmeli
```

#### 4.3 Asset Optimization
- Image optimization
- Font optimization
- Bundle size optimization

### 5. **DevOps ve Deployment**

#### 5.1 Docker Configuration
```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application
COPY . .

# Non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### 5.2 Environment Configuration
```bash
# .env.production
ENV=prod
SECRET_KEY=<strong-random-key>
DATABASE_URL=postgresql+asyncpg://...
CORS_ORIGINS=https://app.yourdomain.com
RATE_LIMIT_PER_MINUTE=60
REDIS_ENABLED=true
REDIS_URL=redis://...
```

#### 5.3 Database Migrations
- Alembic migration'ları düzenli kullanın
- Migration script'leri test edin
- Rollback planı hazırlayın

#### 5.4 Backup Strategy
✅ **İyi:** Backup servisi var
⚠️ **İyileştirme:**
- Otomatik backup schedule'ı aktif edin
- Backup'ları test edin
- Restore procedure dokümante edin

#### 5.5 Monitoring ve Alerting
- Health check endpoint'leri (`/health`)
- Metrics collection (Prometheus/Grafana)
- Uptime monitoring
- Error alerting

### 6. **CI/CD Pipeline**

```yaml
# .github/workflows/deploy.yml veya .gitlab-ci.yml
stages:
  - test
  - build
  - deploy

test:
  - pytest tests/
  - flake8 backend/
  - eslint frontend-modern/

build:
  - docker build -t backend:latest ./backend
  - docker build -t frontend:latest ./frontend-modern

deploy:
  - deploy to production
```

### 7. **Documentation**

#### 7.1 API Documentation
✅ **İyi:** FastAPI otomatik Swagger docs üretiyor

#### 7.2 Code Documentation
- Docstring'ler ekleyin
- README güncelleyin
- Deployment guide ekleyin

## 📋 Pre-Deployment Checklist

### Backend
- [ ] SECRET_KEY güçlü bir değer ile değiştirildi
- [ ] CORS_ORIGINS production domain'leri ile güncellendi
- [ ] CORS_ALLOW_HEADERS ve CORS_ALLOW_METHODS kısıtlandı
- [ ] RATE_LIMIT_PER_MINUTE aktif edildi
- [ ] Debug router'lar production'da devre dışı
- [ ] /docs ve /redoc production'da kapatıldı
- [ ] Database connection pool optimize edildi
- [ ] Redis cache aktif edildi (eğer kullanılacaksa)
- [ ] Backup schedule aktif edildi
- [ ] Logging production moduna alındı
- [ ] Environment variables doğru yapılandırıldı
- [ ] Database migration'lar çalıştırıldı
- [ ] Health check endpoint'leri test edildi

### Frontend
- [ ] VITE_API_URL production URL'e set edildi
- [ ] Sourcemap production build'de kapatıldı
- [ ] Build optimization aktif edildi
- [ ] Environment variables doğru yapılandırıldı
- [ ] Vercel/Render deployment yapılandırması tamamlandı

### Infrastructure
- [ ] HTTPS sertifikası yapılandırıldı
- [ ] Domain DNS ayarları yapıldı
- [ ] Database backup stratejisi hazırlandı
- [ ] Monitoring ve alerting kuruldu
- [ ] Error tracking (Sentry) entegre edildi

### Security
- [ ] Tüm hassas bilgiler environment variables'da
- [ ] .env dosyası .gitignore'da
- [ ] API keys güvenli şekilde saklanıyor
- [ ] Password policy uygulanıyor
- [ ] Rate limiting aktif
- [ ] CORS kısıtlamaları uygulandı

## 🔧 Hızlı Düzeltmeler (Öncelikli)

### 1. Backend Config Düzeltmeleri
```python
# backend/app/core/config.py
# Bu değişiklikleri yapın:
SECRET_KEY: str = Field(default="change-me")  # ENV'den zorunlu yapın
CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS: List[str] = ["Content-Type", "Authorization", "X-Sube-Id", "X-Tenant-Id", "X-Request-ID"]
RATE_LIMIT_PER_MINUTE: int = Field(default=60)  # 0 yerine 60
```

### 2. Debug Router Kaldırma
```python
# backend/app/main.py
# Bu satırı conditional yapın:
if settings.ENV != "prod":
    from .routers.auth_debug import router as debug_router
    app.include_router(debug_router)
```

### 3. Docs Kapatma
```python
# backend/app/main.py
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url="/docs" if settings.ENV != "prod" else None,
    redoc_url="/redoc" if settings.ENV != "prod" else None,
)
```

### 4. Frontend Build Optimization
```typescript
// frontend-modern/vite.config.ts
export default defineConfig({
  build: {
    sourcemap: process.env.NODE_ENV !== 'production',  // Production'da false
    minify: 'terser',
  }
})
```

## 📊 Monitoring Önerileri

### 1. Application Metrics
- Request count
- Response time
- Error rate
- Database query time
- Cache hit rate

### 2. Infrastructure Metrics
- CPU usage
- Memory usage
- Database connection pool usage
- Disk usage

### 3. Business Metrics
- Active tenants
- Active subscriptions
- Payment success rate
- User activity

## 🎯 Sonraki Adımlar

1. ✅ Güvenlik düzeltmelerini uygulayın
2. ✅ Environment variables'ı yapılandırın
3. ✅ Build optimization'ları ekleyin
4. ✅ Test suite'i oluşturun
5. ✅ CI/CD pipeline kurun
6. ✅ Monitoring sistemi kurun
7. ✅ Backup stratejisini test edin
8. ✅ Staging environment'da test edin
9. ✅ Production deployment yapın
10. ✅ Post-deployment monitoring başlatın

---

**Not:** Bu öneriler production deployment için kritiktir. Özellikle güvenlik düzeltmeleri mutlaka uygulanmalıdır.

