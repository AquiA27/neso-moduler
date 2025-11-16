# 🔌 pgvector KURULUM REHBERİ

## ⚠️ MEVCUT DURUM
PostgreSQL'de `pgvector` extension'ı yüklü değil. Semantic search için bu zorunlu.

---

## 🚀 SEÇENEK 1: DOCKER İLE pgvector (ÖNERİLEN)

En hızlı ve kolay yol:

```bash
# Docker'da pgvector içeren PostgreSQL çalıştır
docker run -d \
  --name nesomoduler-postgres \
  -e POSTGRES_USER=neso \
  -e POSTGRES_PASSWORD=neso123 \
  -e POSTGRES_DB=nesomoduler \
  -p 5432:5432 \
  ankane/pgvector

# Bağlantıyı test et
docker exec -it nesomoduler-postgres psql -U neso -d nesomoduler -c "CREATE EXTENSION IF NOT EXISTS vector;"

# .env dosyasını güncelle
DATABASE_URL=postgresql://neso:neso123@localhost:5432/nesomoduler
```

---

## 🔧 SEÇENEK 2: MEVCUT POSTGRESQL'E KURULUM

### Windows:
```bash
# PostgreSQL 16 için pgvector derle (karmaşık)
# Daha kolay: WSL2 + Docker kullan
```

### Linux (Ubuntu/Debian):
```bash
sudo apt install postgresql-16-pgvector

# PostgreSQL'i restart et
sudo systemctl restart postgresql

# Extension'ı ekle
psql -U your_user -d your_database -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### macOS (Homebrew):
```bash
brew install pgvector

# PostgreSQL'i restart et
brew services restart postgresql@16

# Extension'ı ekle
psql -U your_user -d your_database -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

---

## ⏭️ SEÇENEK 3: pgvector OLMADAN DEVAM ET

Eğer pgvector kurmak istemezseniz, semantic search olmadan devam edebilirsiniz:

1. **Migration'ı değiştir:** `CREATE EXTENSION vector` satırını kaldır
2. **menu_embeddings tablosu:**  `vector` tipi yerine `float[]` kullan (daha yavaş)
3. **Semantic search:** Devre dışı bırak, sadece fuzzy matching kullan

**NOT:** Bu durumda sistem çalışır ama **akıllı ürün eşleştirme** olmaz!

---

## ✅ KURULUM SONRASI

Hangisini uyguladıysanız:

```bash
# Migration'ı tekrar dene
cd backend
alembic upgrade head

# Başarılı olursa:
alembic current
# Beklenen: 2025_01_15_0000 (head)

# Tabloyu kontrol et
psql -U your_user -d your_database -c "\d menu_embeddings"
```

---

## 📊 PERFORMANS KARŞILAŞTIRMA

| Yöntem | Kurulum | Performans | Semantic Search |
|--------|---------|------------|-----------------|
| Docker (ankane/pgvector) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ |
| Sistem pgvector | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ |
| float[] (fallback) | ⭐⭐⭐⭐⭐ | ⭐⭐ | ❌ |

---

## 💡 ÖNERİM

**Development için:** Docker (Seçenek 1) - 5 dakikada hazır
**Production için:** Sistem pgvector (Seçenek 2) - Daha stabil

---

Hangi seçeneği tercih edersiniz? Bana bildirin, devam edelim! 🚀
