# İşletme Zekası Asistanı - LLM Kurulumu

## OpenAI API Key Ayarlama

İşletme Asistanı (BI Assistant) için OpenAI entegrasyonu tamamlandı. Kullanmak için şu adımları takip edin:

### 1. OpenAI API Key Alma

1. https://platform.openai.com/ adresine gidin
2. Hesap oluşturun veya giriş yapın
3. API Keys bölümünden yeni bir API key oluşturun
4. Key'i kopyalayın (tekrar gösterilmez!)

### 2. Environment Variable Ayarlama

Backend dizininde `.env` dosyası oluşturun (yoksa):

```bash
cd backend
```

`.env` dosyasına şu satırları ekleyin:

```env
# OpenAI API Key for LLM features
OPENAI_API_KEY=sk-your-actual-openai-api-key-here

# OpenAI Model (önerilen: gpt-4o-mini - düşük maliyet)
OPENAI_MODEL=gpt-4o-mini

# Assistant Features
ASSISTANT_ENABLE_LLM=True
ASSISTANT_ENABLE_TTS=True
ASSISTANT_ENABLE_STT=True

# Database
DATABASE_URL=postgresql+asyncpg://neso:neso123@localhost:5432/neso

# JWT Secret Key
SECRET_KEY=change-me-to-a-strong-random-secret-key-in-production

# Environment
ENV=dev

# CORS Origins
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Default Admin
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin123
```

### 3. Backend'i Yeniden Başlatın

```bash
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. Test Etme

İşletme Asistanı sayfasına gidin: http://localhost:5173/isletme-asistani

Sorular örneği:
- "Bu ayki toplam ciromuz ne kadar?"
- "Hangi ürünlerin stoğu kritik seviyede?"
- "En yüksek gider kalemimiz nedir?"
- "Personel performans raporunu göster."
- "Geçen hafta en çok satan ürünler nelerdi?"

### API Key Yoksa

Eğer OpenAI API key eklemezseniz, sistem otomatik olarak **kural tabanlı modda** çalışır:
- Anahtar kelimeleri tanır (ciro, gider, stok, personel, vb.)
- Basit yanıtlar döner
- LLM özelliği devre dışı kalır

### Maliyet

- `gpt-4o-mini`: Düşük maliyetli, çoğu iş için yeterli
- OpenAI fiyatlandırması: https://openai.com/pricing

### Güvenlik

⚠️ **ÖNEMLİ**: `.env` dosyasını **ASLA** Git'e commit etmeyin! Zaten `.gitignore` dosyasında tanımlı.


