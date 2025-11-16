## Sprint 1 — Veri Entegrasyonu Katmanı (Müşteri Asistanı)

Bu doküman, müşteri asistanını veriyle beslemek için uygulanacak ilk sprintin hedeflerini ve yapılacak teknik adımları özetler. Amaç; menü, stok, reçete, satış vb. kaynakları tek bir erişim katmanında toplamak ve asistan için tutarlı bir şema sözlüğü sağlamaktır.

---

### 1. Mevcut Durum Analizi

- **Veritabanı**  
  - `menu`, `siparisler`, `adisyons`, `odemeler`, `stok_kalemleri`, `receteler`, `users`, `kampanyalar` (kampanya yapısı `giderler` ve `analytics` raporlarına dağılmış durumda).  
  - `siparisler` JSONB `sepet` alanı içeriyor; ürün varyasyonları burada saklanıyor.  
  - `created_by_username` sayesinde siparişlerin kaynağı (AI/personel) ayırt edilebiliyor.
- **Backend API**  
  - Çeşitli router’lar (`menu.py`, `stok.py`, `analytics.py`, `analytics_advanced.py`, `kasa.py` vb.) doğrudan SQL çalıştırıyor.  
  - Şu anda asistan için tekilleştirilmiş bir veri erişim servisi bulunmuyor; her ihtiyaç için ayrı sorgu yazılıyor.  
  - Cache ve event tetikleyiciler sınırlı; stok uyarıları için websocket var, ancak menü/kampanya değişimleri merkezi değil.

---

### 2. Hedef Mimari Bileşenleri

| Bileşen | Açıklama | Dosya/Modül |
|---------|----------|-------------|
| **Business View / Materialized View** | Menü, stok, reçete, satış, kampanya, kullanıcı bilgilerini birleştiren sorgu katmanı. Performans için matview veya view kullanılacak. | `backend/app/db/views/business_data.sql` (oluşturulacak) |
| **Data Access Servisi** | `{intent, entity}` → SQL/ORM sorgusu dönüşümü yapan servis. | `backend/app/services/data_access.py` (oluşturulacak) |
| **Schema Registry** | Kolon takma adları, veri tipleri, açıklamalar. Prompt ve servis bu dosyadan beslenecek. | `backend/app/config/schema_registry.json` (oluşturulacak) |
| **Cache & Event Bus** | 60 saniyelik refresh + kritik tablolar için gerçek zamanlı tetikleme. | `backend/app/services/event_bus.py` & servis cache katmanı |

---

### 3. Implementasyon Adımları

1. **Schema Registry Tasarımı**
   - JSON formatında bölümleme: `menu`, `stok`, `recete`, `kampanya`, `satis`, `personel`, `sube`.  
   - Her alan için `field`, `aliases`, `type`, `description`, `source_table` bilgileri tutulacak.  
   - `assistant` prompt builder’ı ve data access servisi bu dosyayı okuyacak.
   - _Yapılacak dosyalar_
     - `backend/app/config/schema_registry.json`
     - `backend/app/config/schema_registry_loader.py` (okuma, doğrulama ve cache)
   - _Doğrulama_
     - CI aşamasında JSON şemasını `scripts/validate_schema_registry.py` ile kontrol et.
     - Eksik/yanlış alias durumunda hata logu üret, build’i başarısız say.

2. **Business View Oluşturma**
   - `db/views` klasörü oluşturulacak.  
   - View örneği: `vw_ai_business_data` → menü + stok + reçete + kategori + fiyat + kampanya ilişkileri.  
   - Satış/adisyon verilerini ayrı view’larda (`vw_ai_sales_summary`, `vw_ai_active_adisyons`) toplamak, AI sorgularının sadeleşmesini sağlayacak.
   - _View listesi taslağı_
     - `vw_ai_menu_stock` → ürün, kategori, stok, fiyat, reçete anahtarı
     - `vw_ai_sales_summary` → son N gün satış adet/ciro, personel/AI kırılımı
     - `vw_ai_active_sessions` → açık adisyon, masa, bakiye, bekleyen siparişler
     - `vw_ai_campaigns` → aktif kampanyalar, tarih aralığı, koşullar
   - Bu SQL dosyaları `backend/app/db/views/*.sql` içinde versiyonlanacak; `alembic` migration ile `CREATE VIEW` / `DROP VIEW IF EXISTS` komutları yönetilecek.

3. **Data Access Servisi**
   - `resolve_query(intent, entity, filters)` fonksiyonu:  
     - Schema registry üzerinden alan eşleştirmesi,  
     - Sorgu şablonu seçimi (örn. stok durumu → `SELECT ... FROM vw_ai_stock_status`),  
     - Parametre enjeksiyonu ve sonuç standardizasyonu (dict listesi).
   - Hata yönetimi: Eksik intent/entity durumunda fallback açıklaması.
   - _Modül yapısı_
     - `backend/app/services/data_access/__init__.py`
     - `query_builder.py` → intent → SQL template eşleştirmesi
     - `resolver.py` → registry + builder + database çağrısı
     - `exceptions.py` → `UnknownIntentError`, `EntityNotFoundError`, `InvalidFilterError`
   - _Sorgu sözleşmeleri_
     - Girdi: `DataQueryRequest { intent: str; entities: Dict[str, str]; filters: Dict[str, Any]; limit?: int }`
     - Çıktı: `DataQueryResult { rows: List[Dict[str, Any]]; metadata: { intent, entity_map, source_view } }`
   - _Genişletilebilirlik_
     - Yeni intent eklemek için `query_builder.py` içinde `INTENT_TABLE` dictionary ve ilgili SQL şablonu eklenir.
     - SQL şablonları Jinja2 veya `%s` parametreli hale getirilecek; injection’a karşı `db.fetch_all(query, values)` kullanılacak.
   - _Test stratejisi_
     - Unit test: Sahte registry + intent ile doğru SQL çıktısı alınıyor mu?
     - Integration test: Demo veritabanı üzerinde `/assistant/data-query` test uç noktası.

4. **Cache / Event Tetikleyicileri**
   - `services/cache.py` genişletilerek `ai_data_cache` namespace’i eklenir.  
   - PostgreSQL trigger’ları veya `LISTEN/NOTIFY` ile `menu`, `stok_kalemleri`, `kampanyalar`, `adisyons` değişimlerinde invalidasyon.  
   - Frontend’de (müşteri asistanı) 60 sn’de bir “light refresh” yapılacak; websocket bildirimi gelirse anında güncellenecek.
   - _Backend tarafı_
     - `backend/app/services/event_bus.py` → `register_channel(name, handler)`; async listener görevleri.
     - `backend/app/services/cache.py` → `AI_CACHE_TTL = 60_000` (ms); `invalidate(pattern)` API’si.
     - Migration: `CREATE FUNCTION notify_ai_cache()` + ilgili tablolara trigger.
   - _Frontend tarafı_
     - `frontend-modern/src/hooks/useAssistantData.ts` → 60 sn interval + websocket event ile `invalidate()`.
     - Event payload: `{ type: 'menu_updated', sube_id, entity_ids }`.
   - _Failover_
     - LISTEN/NOTIFY başarısızsa günlük job (cron) `invalidate_all()` çalıştırır.

5. **Dokümantasyon & Test**
   - Yeni view ve servislerin kullanımını anlatan README bölümü.  
   - Unit test: Schema registry’den alan çözme, intent → sorgu eşleştirmesi, cache invalidasyonu.

---

### 4. Sprint Çıktıları

- `schema_registry.json` hazır ve CI’da doğrulanan şema.  
- `data_access.py` üzerinden asistanın veri çektiği merkezi API.  
- `vw_ai_*` view’ları ve migration betikleri.  
- Cache + event mekanizması prototipi (en azından stok güncellemesi için).  
- Asistan prompt’unda veri sözlüğü referanslarının otomatik eklenmesi için hazırlık.

---

### 5. Risk & Notlar

- View’ların performansı: Büyük veri hacimlerinde matview + cron refresh gerekebilir.  
- Schema registry değişimi prompt uzunluğunu artırabilir; gerekli alanlar seçilmeli.  
- Event tetikleyiciler için altyapı yoksa ilk etapta manual refresh (invalidate + fetch) uygulanabilir.  
- Tabloların tenant/şube bazlı filtrelenmesine dikkat edilmeli (`sube_id` zorunlu).

---

Bu plan tamamlandığında, asistanın veri katmanı modular ve genişletilebilir hale gelecek; sonraki sprintlerde intent bağlamı ve aksiyon katmanı bu temel üzerine kurulabilir.

---

## Sprint 2 — Intent & Bağlam Katmanı Hazırlığı

### 1. Hedefler
- Kullanıcı ifadelerini doğru niyet (intent) ve varlık (entity) etiketlerine dönüştürmek.
- Konuşma geçmişi, masa/adisyon durumu ve kampanya bilgilerini merkezi bir context yöneticisiyle yönetmek.
- Kurallı ve öğrenen karar mekanizmalarını aynı akışta uyumlu hale getirmek.

### 2. Bileşenler ve Modül Planı

| Bileşen | Açıklama | Dosya/Modül |
|---------|----------|-------------|
| Intent/Entity Model | NLP servis katmanı; OpenAI/HF modeli veya karma çözüm | `backend/app/services/nlp/intents.py` (yeni) |
| Kurallı Motor | Menü dışı ürün, stok yetersizliği, kampanya tetikleri | `backend/app/rules/engine.py` (yeni) |
| Bağlam Yöneticisi | Konuşma geçmişi, aktif masa/adisyon, sepet | `backend/app/services/context_manager.py` (yeni) |
| Fuzzy Eşleştirme | Ürün/menü normalizasyonu ve eş anlamlı yönetimi | `backend/app/utils/text_matching.py` (yeni) |
| Intent Konfigürasyonu | Intent tanımları, örnekler, minimum alan gereksinimleri | `backend/app/config/intent_registry.json` (yeni) |

### 3. Uygulama Adımları
1. **Intent/Entity Pipeline**
   - `intent_registry.json`: intent adı, gerekli entity’ler, açıklama ve örnek cümleler.
   - `IntentClassifier` sınıfı:
     - `load_model()` → uzaktan/yerel model seçimi.
     - `predict(text, context_hint)` → `{ intent, entities, confidence, rationale }`.
     - Fallback: RegEx/keyword kuralları.
   - Test dataseti: `tests/data/assistant/intent_samples.json`.

2. **Fuzzy & Semantik Eşleşme**
   - `text_matching.py` util:
     - `normalize(text)` → accent strip, lower, sinonim değişimleri.
     - `closest_menu_item(text)` → Levenshtein + embedding (SBERT vb.).
   - Reçete eşleme: Menü → reçete → stok bağlantısını doğrular.

3. **Context Manager**
   - `context_manager.py`:
     - `get_or_create_session(conversation_id)` → Redis/DB cache üzerinden.
     - `update_context(...)` → sepet, masa, son intent, kampanya bilgileri.
     - `build_prompt_context()` → prompt builder için JSON özet döndürür.
   - Persist katmanı: `assistant_conversations` tablosu için migration hazırlanacak.

4. **Kurallı Motor**
   - `rules/engine.py`:
     - `evaluate(intent, entities, context)` → aksiyon listesi (`WARN_STOCK_LOW`, `OFFER_CAMPAIGN`, `REQUEST_CONFIRMATION`).
   - Kurallar JSON formatında `backend/app/rules/config.json` içinde tutulur.

5. **Akış Entegrasyonu**
   - `assistant.py` sıralaması:
     1. Intent çıkarımı + fuzzy eşleşme.
     2. Schema registry aracılığıyla veri çekimi (`data_access`).
     3. Context güncellemesi.
     4. Kurallı motorun tetiklediği ek aksiyonlar.
     5. Yanıt üretimi (prompt builder + doğrulama).
   - Log formatı: intent, confidence, resolved entities, triggered rules.

### 4. Test & Validasyon
- Unit: `tests/unit/services/test_intents.py`, `test_context_manager.py`, `test_rules_engine.py`.
- Integration: `tests/integration/test_assistant_flow.py` (örnek konuşma senaryoları).
- CI: Model erişimi yoksa mock inference; gerçek entegrasyon için env flag ile devreye alınır.

### 5. Risk & Notlar
- OpenAI/HF rate-limit ve maliyet kısıtları → kurallı fallback her zaman hazır olmalı.
- Fuzzy eşleşme için minimum güven eşiği (örn. 0.7) belirlenmeli.
- Konuşma geçmişi saklama süresi GDPR uyumlu olacak şekilde konfigüre edilmeli.

---

## Sprint 3+ (Kısa Özet)
- **Sprint 3:** AI aksiyon servisleri, onay/geri alma akışı, audit log iyileştirmeleri.  
- **Sprint 4:** Prompt builder, yanıt doğrulama, TTS pipeline entegrasyonu.  
- **Sprint 5:** Analytics & geri bildirim katmanı, `ai_interaction_logs` raporlaması.


