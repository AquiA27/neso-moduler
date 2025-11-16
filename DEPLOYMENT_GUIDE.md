# 🚀 İKİ ASİSTAN SİSTEMİ - DEPLOYMENT KILAVUZU

Bu kılavuz, yeni oluşturulan **Customer Assistant** (Müşteri Asistanı) sistemini production'a almak için gereken adımları içerir.

---

## 📋 ÖN KOŞULLAR

### 1. Gerekli Araçlar
- Python 3.9+ (backend)
- PostgreSQL 14+ (pgvector extension desteği)
- Redis (cache için, opsiyonel)
- Node.js 16+ (frontend, opsiyonel)

### 2. API Keys
- **OpenAI API Key** (embeddings + LLM için)
  - Alembic/versions dosyası migrate edilirken gerekli değil
  - Servis çalışırken embeddings oluşturmak için gerekli

### 3. Bağımlılıklar Kurulumu
```bash
cd backend

# Yeni bağımlılıklar (varsa requirements.txt'e ekle)
pip install openai>=1.0.0
pip install rapidfuzz  # Türkçe fuzzy matching için (opsiyonel, difflib fallback var)
```

---

## 🔧 ADIM 1: ENVIRONMENT CONFIGURATION

`.env` dosyasına aşağıdaki değişkenleri ekleyin:

```bash
# OpenAI API (Zorunlu)
OPENAI_API_KEY=sk-...

# Embedding Ayarları (Opsiyonel, default değerler var)
EMBEDDING_MODEL=text-embedding-ada-002
EMBEDDING_DIMENSION=1536

# Matching Ayarları (Opsiyonel)
SEMANTIC_THRESHOLD=0.7  # Minimum semantic similarity (0-1)
FUZZY_THRESHOLD=0.7     # Minimum fuzzy match score (0-1)

# LLM Ayarları (Sentiment analysis için)
LLM_MODEL=gpt-3.5-turbo  # veya gpt-4
LLM_TEMPERATURE=0.3
```

---

## 🗄️ ADIM 2: DATABASE MIGRATION

### 2.1. pgvector Extension Kontrolü

PostgreSQL'de pgvector extension'ı yüklü olmalı:

```sql
-- PostgreSQL'e bağlan
psql -U your_user -d your_database

-- Extension'ı yükle (ilk kez)
CREATE EXTENSION IF NOT EXISTS vector;

-- Kontrol et
SELECT * FROM pg_extension WHERE extname = 'vector';
```

**NOT:** Eğer pgvector yüklü değilse:
```bash
# Ubuntu/Debian
sudo apt install postgresql-14-pgvector

# macOS (Homebrew)
brew install pgvector

# Docker
docker pull ankane/pgvector
```

### 2.2. Alembic Migration Çalıştır

```bash
cd backend

# Migration'ları kontrol et
alembic history

# Son migration'a git
alembic upgrade head

# Başarılı olursa göreceksiniz:
# INFO  [alembic.runtime.migration] Running upgrade ... -> 2025_01_15_0000, add pgvector and menu embeddings
```

### 2.3. Migration Doğrulama

```sql
-- Yeni tabloları kontrol et
\dt menu_embeddings

-- View'ları kontrol et
\dv vw_ai_*

-- Schema
\d menu_embeddings
```

**Beklenen çıktı:**
```
Column      | Type                  | Nullable
------------+-----------------------+---------
id          | integer               | not null
menu_id     | integer               | not null
sube_id     | integer               | not null
embedding   | real[]                | not null
metadata    | jsonb                 |
created_at  | timestamp             | not null
updated_at  | timestamp             | not null
```

---

## 🧬 ADIM 3: EMBEDDINGS OLUŞTURMA

### 3.1. İlk Embeddings Sync

Backend uygulaması çalışırken, Python konsolu ile:

```python
import asyncio
from app.services.embedding_service import get_embedding_service

async def init_embeddings():
    service = get_embedding_service()

    # Tüm şubeler için (örnek: sube_id=1)
    stats = await service.sync_menu_embeddings(sube_id=1, force=False)

    print(f"✅ Created: {stats['created']}")
    print(f"🔄 Updated: {stats['updated']}")
    print(f"⏭️ Skipped: {stats['skipped']}")
    print(f"❌ Errors: {stats['errors']}")

    # Vector index oluştur (>=100 embedding gerekli)
    if stats['created'] + stats['updated'] >= 100:
        success = await service.create_vector_index()
        if success:
            print("✅ Vector index created successfully")

asyncio.run(init_embeddings())
```

**Alternatif: API Endpoint üzerinden**
```bash
# Embedding endpoint'i ekleyin (opsiyonel)
curl -X POST http://localhost:8000/admin/sync-embeddings \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "X-Sube-Id: 1"
```

### 3.2. Maliyet Hesaplama

```
Menü ürün sayısı: 100
Embedding model: text-embedding-ada-002
Maliyet: ~$0.01 (bir kez)

Günlük kullanım (1000 sipariş):
Query embeddings: 1000 × $0.0001 = $0.10/gün
Aylık: ~$3-5
```

---

## ⚙️ ADIM 4: SERVİS BAŞLATMA

### 4.1. Backend Başlat

```bash
cd backend

# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production (Gunicorn + Uvicorn workers)
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

### 4.2. Log Kontrol

```bash
tail -f logs/app.log | grep -E "(customer_assistant|embedding|sentiment)"

# Beklenen loglar:
# [INFO] Embedding service initialized
# [INFO] Generated embedding for menu_id=1
# [INFO] Customer chat: intent=siparis, confidence=0.85
# [INFO] Sentiment: mood=uzgun, confidence=0.92
```

---

## 🧪 ADIM 5: TEST SENARYOLARI

### 5.1. Semantic Search Testi

```bash
curl -X POST http://localhost:8000/customer-assistant/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "X-Sube-Id: 1" \
  -d '{
    "text": "sıcak kahve istiyorum",
    "masa": "A1"
  }'
```

**Beklenen Sonuç:**
```json
{
  "type": "success",
  "message": "Tamam, 1 adet Türk Kahvesi sipariş ediyorum. Toplam: 15.00 ₺",
  "matched_products": [
    {
      "menu_id": 123,
      "product_name": "Türk Kahvesi",
      "category": "Sıcak İçecekler",
      "price": 15.0,
      "confidence": 0.92,
      "semantic_score": 0.89,
      "fuzzy_score": 0.85
    }
  ],
  "intent": "siparis"
}
```

### 5.2. Sentiment Analysis Testi

```bash
curl -X POST http://localhost:8000/customer-assistant/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "X-Sube-Id: 1" \
  -d '{
    "text": "çok üzgünüm, bir şey içebilir miyim?",
    "masa": "A1"
  }'
```

**Beklenen Sonuç:**
```json
{
  "type": "recommendation",
  "message": "Anlıyorum, zor bir gün geçiriyorsunuz. Size Sıcak Çikolata önerebilirim, moral verir.",
  "recommendations": [
    {
      "menu_id": 456,
      "product_name": "Sıcak Çikolata",
      "category": "Sıcak İçecekler",
      "price": 20.0,
      "reason": "Ruh halinize uygun (uzgun)",
      "stock_status": "yeterli"
    }
  ],
  "sentiment": {
    "mood": "uzgun",
    "confidence": 0.92
  }
}
```

### 5.3. Fuzzy Matching Testi (Yazım Hatası)

```bash
curl -X POST http://localhost:8000/customer-assistant/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "X-Sube-Id: 1" \
  -d '{
    "text": "menengiş kahvesi",
    "masa": "A1"
  }'
```

**Beklenen:** "Menengiç Kahvesi" ile eşleşmeli (fuzzy matching)

### 5.4. Low Confidence Testi

```bash
curl -X POST http://localhost:8000/customer-assistant/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "X-Sube-Id: 1" \
  -d '{
    "text": "şu tatlı şey",
    "masa": "A1"
  }'
```

**Beklenen Sonuç:**
```json
{
  "type": "options",
  "message": "Bunlardan birini mi istediniz?",
  "options": [
    {"value": "1", "label": "Cheesecake (25.00 ₺)", "menu_id": 789},
    {"value": "2", "label": "Tiramisu (30.00 ₺)", "menu_id": 790},
    {"value": "3", "label": "Waffle (18.00 ₺)", "menu_id": 791},
    {"value": "none", "label": "Hiçbiri"}
  ]
}
```

---

## 📊 ADIM 6: MONİTÖRİNG & PERFORMANS

### 6.1. Embeddings Performansı

```sql
-- Embedding sayısı
SELECT COUNT(*) as total_embeddings FROM menu_embeddings;

-- Şube bazlı
SELECT sube_id, COUNT(*) as embeddings_count
FROM menu_embeddings
GROUP BY sube_id;

-- Vector index var mı?
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'menu_embeddings';
```

### 6.2. Semantic Search Performansı

```sql
-- Örnek semantic search query (test)
EXPLAIN ANALYZE
SELECT
    menu_id,
    1 - (embedding <=> '[0.1, 0.2, ...]'::vector) AS similarity
FROM menu_embeddings
WHERE sube_id = 1
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 5;

-- Beklenen: <50ms (indexed), <500ms (sequential scan)
```

### 6.3. Uygulama Metrikleri

```python
# backend/app/services/monitoring.py (eklenebilir)
from prometheus_client import Counter, Histogram

# Metrikler
customer_chat_requests = Counter('customer_chat_requests_total', 'Total chat requests')
semantic_search_duration = Histogram('semantic_search_duration_seconds', 'Semantic search duration')
sentiment_analysis_total = Counter('sentiment_analysis_total', 'Sentiment analyses', ['mood'])
```

---

## 🔄 ADIM 7: OTOMATİK SYNC (Opsiyonel)

Menü değişikliklerinde otomatik embedding güncellemesi için:

### 7.1. Menu Router'a Hook Ekle

`backend/app/routers/menu.py` dosyasında:

```python
from app.services.menu_embedding_hook import on_menu_created, on_menu_updated

@router.post("/ekle")
async def menu_ekle(...):
    # ... mevcut kod ...

    # Yeni eklenen kısım
    await on_menu_created(
        menu_id=new_item_id,
        sube_id=sube_id,
        product_name=item.ad,
        category=item.kategori,
        description=item.aciklama
    )

    return {...}
```

### 7.2. Scheduled Sync (Günlük)

```python
# backend/app/services/scheduler.py (mevcut scheduler'a ekle)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.menu_embedding_hook import sync_all_embeddings_background

scheduler = AsyncIOScheduler()

# Her gün saat 02:00'da tüm embeddings'i sync et
scheduler.add_job(
    sync_all_embeddings_background,
    'cron',
    hour=2,
    minute=0,
    args=[1]  # sube_id
)
```

---

## 🚨 SORUN GİDERME

### Problem 1: pgvector extension yok
```
ERROR: type "vector" does not exist
```

**Çözüm:**
```bash
# PostgreSQL'e pgvector extension'ı yükle
sudo apt install postgresql-14-pgvector
# veya
brew install pgvector
```

### Problem 2: OpenAI API hatası
```
ERROR: OpenAI API error: Invalid API key
```

**Çözüm:**
```bash
# .env dosyasını kontrol et
cat .env | grep OPENAI_API_KEY

# Geçerli bir key ekle
echo "OPENAI_API_KEY=sk-..." >> .env
```

### Problem 3: Semantic search çok yavaş
```
WARNING: Sequential scan on menu_embeddings (slow)
```

**Çözüm:**
```python
# Vector index oluştur (>=100 embedding gerekli)
from app.services.embedding_service import get_embedding_service
import asyncio

asyncio.run(get_embedding_service().create_vector_index())
```

### Problem 4: Sentiment her zaman "neutral" dönüyor
```
INFO: Sentiment: mood=neutral, confidence=0.5
```

**Çözüm:**
1. LLM provider ayarlarını kontrol et
2. Schema registry'deki sentiment keywords'leri kontrol et
3. OpenAI API limitlerini kontrol et

---

## 📈 PROD CHECKLIST

- [ ] pgvector extension yüklü
- [ ] Migration çalıştırıldı (`alembic upgrade head`)
- [ ] Embeddings oluşturuldu (tüm şubeler için)
- [ ] Vector index oluşturuldu (>=100 embedding)
- [ ] OpenAI API key geçerli ve limitleri yeterli
- [ ] Customer assistant router kayıtlı (`main.py`)
- [ ] Test senaryoları başarılı
- [ ] Monitoring metrikleri aktif
- [ ] Log rotasyonu yapılandırıldı
- [ ] Backup stratejisi tanımlandı (embeddings tablosu dahil)
- [ ] Frontend entegrasyonu tamamlandı
- [ ] Dokümantasyon güncellendi

---

## 🎯 SONRAKI GELİŞTİRMELER

1. **A/B Testing:** Farklı confidence threshold'ları test et
2. **User Feedback Loop:** Onay/red oranlarını takip et, modeli iyileştir
3. **Multi-language:** İngilizce desteği ekle
4. **Voice Integration:** STT/TTS ile sesli sipariş
5. **Context Awareness:** Müşteri geçmişi (past orders) ile kişiselleştirme
6. **Kampanya Entegrasyonu:** Otomatik indirim ve promosyon önerileri

---

**Son Güncelleme:** 2025-01-15
**Destek:** [GitHub Issues](https://github.com/your-repo/issues)
