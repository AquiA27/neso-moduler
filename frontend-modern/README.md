# Neso Modüler - Modern Frontend

React + TypeScript + Vite ile modernize edilmiş frontend uygulaması.

## 🚀 Kurulum

```bash
cd frontend-modern
npm install
```

## 📝 Geliştirme

```bash
npm run dev
```

Uygulama http://localhost:5173 adresinde çalışacaktır.

## 🏗️ Build

```bash
npm run build
```

Build dosyaları `dist` klasörüne oluşturulur.

## 📦 Özellikler

- ✅ React 18 + TypeScript
- ✅ Vite (hızlı build tool)
- ✅ React Router v6 (routing)
- ✅ Zustand (state management)
- ✅ Axios (API client)
- ✅ Tailwind CSS (styling)
- ✅ Lucide React (icons)

## 📁 Klasör Yapısı

```
src/
├── components/     # Reusable components
├── pages/         # Sayfa componentleri
├── store/         # Zustand store'ları
├── lib/           # Utility functions, API client
├── App.tsx        # Ana component
└── main.tsx       # Entry point
```

## 🔗 API Entegrasyonu

API base URL'i `.env` dosyasında `VITE_API_URL` ile tanımlanır. Varsayılan: `http://localhost:8000`

## 🔐 Authentication

- JWT access token ve refresh token desteği
- Otomatik token refresh
- Protected routes

## 📱 Sayfalar

- `/login` - Giriş sayfası
- `/dashboard` - Genel bakış
- `/menu` - Menü yönetimi
- `/mutfak` - Mutfak kuyruğu
- `/kasa` - Kasa yönetimi
- `/stok` - Stok yönetimi

## 🎨 Styling

Tailwind CSS kullanılmaktadır. Mevcut tasarım tema renkleri (`primary-*`) kullanılarak uyumlu bir görünüm sağlanmıştır.

