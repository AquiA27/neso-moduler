# Super Admin Panel - Ayrı Uygulama Kurulumu

## 🎯 Amaç

Super Admin paneli artık müşteri uygulamasından **tamamen ayrı** bir uygulamadır. Bu sayede:
- ✅ Güvenlik daha iyi (ayrı domain/subdomain)
- ✅ Kod karmaşıklığı azalır
- ✅ Deploy süreçleri ayrılır
- ✅ Müşteri paneline super admin kodları karışmaz

## 📁 Yapı

```
NesoModuler/
├── frontend-modern/          # Müşteri uygulaması (port 5173)
│   └── (super admin paneli KALDIRILDI)
│
└── super-admin-panel/        # Platform yöneticisi uygulaması (port 5174)
    ├── src/
    │   ├── pages/
    │   │   ├── LoginPage.tsx
    │   │   └── DashboardPage.tsx (SuperAdminPanel)
    │   ├── lib/
    │   │   └── api.ts (sadece super admin API'leri)
    │   ├── store/
    │   │   └── authStore.ts
    │   └── App.tsx
    └── package.json
```

## 🚀 Kurulum

### 1. Bağımlılıkları Yükle

```bash
cd super-admin-panel
npm install
```

### 2. Çalıştır

```bash
npm run dev
```

Uygulama `http://localhost:5174` portunda çalışır.

## 📝 Notlar

### Test Aşaması
- Şu an için super admin paneli `frontend-modern` içinde hala mevcut (test için)
- Production'da tamamen kaldırılacak

### Giriş
- Sadece `super_admin` rolüne sahip kullanıcılar giriş yapabilir
- Default kullanıcı: `super` / `super123`

### Backend CORS
Backend'de super admin paneli için ayrı CORS ayarları eklenebilir:

```python
# backend/app/core/config.py
SUPER_ADMIN_FRONTEND_URL = "http://localhost:5174"
```

## 🔄 Migration Planı

1. ✅ Super admin paneli ayrı uygulama olarak oluşturuldu
2. ⏳ Test aşamasında mevcut sistemde bırakılacak
3. ⏳ Production'da frontend-modern'den kaldırılacak
4. ⏳ Ayrı domain/subdomain ile deploy edilecek

## 📦 Production Deploy

Production'da:
- `frontend-modern` → `app.neso.com` (müşteri uygulaması)
- `super-admin-panel` → `admin.neso.com` (platform yöneticisi)


