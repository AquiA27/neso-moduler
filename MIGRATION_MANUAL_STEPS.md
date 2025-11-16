# 🔧 MIGRATION MANUEL ADIMLAR

İlk migration'da (`2025_01_01_0000-initial_schema.py`) bir hata var: `urun_norm` kolonu yok ama index'te kullanılıyor.

## ÇÖZÜM SEÇENEKLERİ

### **Seçenek 1: Mevcut Database'i Kullan (Eğer Tablolar Zaten Varsa)**

Eğer `menu`, `siparisler`, `stok_kalemleri` vb. tablolar zaten varsa:

```bash
cd backend

# Sadece yeni migration'ı çalıştır
alembic stamp initial_schema
alembic stamp 2025_01_02_0000

# Şimdi pgvector migration'ı çalıştır
alembic upgrade head
```

### **Seçenek 2: Temiz Başla (Önerilen - Development)**

```sql
-- PostgreSQL'e bağlan
psql -U your_user -d your_database

-- Tüm tabloları sil (DİKKAT: VERİ KAYBI!)
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO your_user;
GRANT ALL ON SCHEMA public TO public;

-- pgvector extension'ı ekle
CREATE EXTENSION IF NOT EXISTS vector;
```

Sonra:
```bash
# Backend'e git
cd backend

# Schema'yı application üzerinden oluştur (migration kullanmadan)
python -c "
import asyncio
from app.db.database import db
from app.db.schema import create_tables

async def init():
    await db.connect()
    await create_tables(db)
    print('✅ Tables created')
    await db.disconnect()

asyncio.run(init())
"

# Şimdi sadece pgvector migration'ı çalıştır
alembic stamp initial_schema
alembic stamp 2025_01_02_0000
alembic upgrade head
```

### **Seçenek 3: İlk Migration'ı Düzelt (Kalıcı Çözüm)**

`backend/alembic/versions/2025_01_01_0000-initial_schema.py` dosyasında:

**Satır 151'deki şu satırı yorum satırı yap:**
```python
# op.execute("CREATE INDEX IF NOT EXISTS idx_recete_sube_urun ON receteler (sube_id, urun_norm)")
```

**Veya `urun_norm` kolonunu ekle:**
```python
# receteler tablosuna (line ~130 civarı)
urun_norm TEXT,
```

Sonra:
```bash
alembic upgrade head
```

---

## 💡 HEM SEÇENEKLERİNİ DENE

```bash
# Database var mı kontrol et
psql -U your_user -d your_database -c "\dt"

# Tablolar varsa: Seçenek 1
# Tablolar yoksa: Seçenek 2 veya 3
```

---

## ✅ BAŞARILI OLURSA

Migration başarılı olduktan sonra:

```bash
alembic current
# Beklenen çıktı: 2025_01_15_0000 (head)

# Tabloları kontrol et
psql -U your_user -d your_database -c "\dt menu_embeddings"
psql -U your_user -d your_database -c "\dv vw_ai_*"
```

---

## 📝 NOTLAR

- **Production'da:** Seçenek 1 tercih edin (veri kaybını önler)
- **Development'ta:** Seçenek 2 tercih edin (temiz başlangıç)
- **Kalıcı çözüm:** Seçenek 3 (migration dosyasını düzelt)

---

Hangi seçeneği uyguladığınızı bana bildirin, sonraki adıma geçelim! 🚀
