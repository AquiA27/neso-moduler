# 🧪 BI Assistant Test Rehberi

Backend çalışırken Swagger UI veya curl ile test edin.

## 1. Swagger UI ile Test (En Kolay)

### Adım 1: Swagger'ı Açın
```
http://localhost:8000/docs
```

### Adım 2: Login
1. **Authorize** tıklayın
2. Username: `admin`, Password: `admin123`
3. **Authorize** → **Close**

### Adım 3: BI Assistant Endpoint'ini Bulun
- **POST /bi-assistant/query** bölümünü açın
- **Try it out** tıklayın

### Adım 4: Test Sorularını Deneyin

#### Test 1: Ciro Sorusu
```json
{
  "text": "Bu ayki ciromuz ne kadar?"
}
```
**Beklenen Yanıt:**
- Net rakamlar (45.250 ₺ gibi)
- Sipariş sayısı
- Ortalama sepet
- Kısa analiz (maksimum 6 cümle)

---

#### Test 2: Stok Sorusu
```json
{
  "text": "Hangi ürünlerin stoğu kritik?"
}
```
**Beklenen Yanıt:**
- Kritik stok listesi
- Mevcut/minimum değerler
- Kalan gün tahmini
- Aciliyet vurgusu

---

#### Test 3: Kar Marjı
```json
{
  "text": "Kar marjımız nasıl?"
}
```
**Beklenen Yanıt:**
- Net kar rakamı
- Kar marjı yüzdesi
- Sektör karşılaştırması
- Somut öneriler

---

#### Test 4: Personel Performansı
```json
{
  "text": "Personel performansı nasıl?"
}
```
**Beklenen Yanıt:**
- Personel listesi
- Ciro/sipariş metrikleri
- Performans karşılaştırması

---

#### Test 5: Alışveriş Önerileri
```json
{
  "text": "Ne almamız lazım?"
}
```
**Beklenen Yanıt:**
- Kritik stoklar
- Önerilen miktarlar
- Aciliyet (günlük kalan süre)
- Tahmini maliyet

---

#### Test 6: Genel Özet
```json
{
  "text": "İşletme durumumuz nasıl?"
}
```
**Beklenen Yanıt:**
- Ciro özeti
- Kar/zarar durumu
- Kritik noktalar
- Genel sağlık skoru

---

## 2. Curl ile Test

### Test 1: Ciro Sorusu
```bash
curl -X POST http://localhost:8000/bi-assistant/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Sube-Id: 1" \
  -H "Content-Type: application/json" \
  -d '{"text": "Bu ayki ciromuz ne kadar?"}'
```

### Test 2: Stok Sorusu
```bash
curl -X POST http://localhost:8000/bi-assistant/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Sube-Id: 1" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hangi ürünlerin stoğu kritik?"}'
```

### Test 3: Kar Sorusu
```bash
curl -X POST http://localhost:8000/bi-assistant/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Sube-Id: 1" \
  -H "Content-Type: application/json" \
  -d '{"text": "Kar marjımız nasıl?"}'
```

---

## 3. Yanıt Kalitesi Değerlendirme

### ✅ İyi Yanıt Özellikleri:

1. **Kısa (maksimum 6 cümle)**
2. **Net rakamlar** (tahmin yok)
3. **Karşılaştırma** (geçmiş dönem, sektör)
4. **Somut öneri** (ne yapmalı)
5. **Profesyonel ton** (ama samimi)
6. **Türkçe karakterler** doğru

### ❌ Kötü Yanıt İşaretleri:

- Çok uzun paragraflar
- Belirsiz ifadeler ("sanırım", "muhtemelen")
- Gereksiz tekrar
- Abartılı övgü
- Hallüsinasyon (olmayan veri)

---

## 4. Karşılaştırma Örnekleri

### Eski Sistem ❌
```
Soru: "Bu ayki ciromuz ne kadar?"

Yanıt: "İşletmenizin son 30 günlük performansına baktığımda,
toplam cironuz 45.250 TL civarında görünüyor. Bu rakam,
yaklaşık olarak 312 adet siparişten oluşmakta. Ortalama sepet
tutarınız 145 TL seviyelerinde. Geçen aya kıyasla %12'lik bir
artış var gibi. Hafta sonları genellikle daha yüksek ciro elde
ediyorsunuz, özellikle Cuma ve Pazar günleri dikkat çekici.
Bu trendleri göz önünde bulundurarak, hafta sonu stratejilerinizi
güçlendirebilirsiniz. Ayrıca ortalama sepet tutarınızı artırmak
için çapraz satış tekniklerini deneyebilirsiniz..."
```
**Sorunlar:**
- Çok uzun (8+ cümle)
- Gereksiz detay
- Belirsiz dil ("civarında", "gibi")
- Fazla öneri

### Yeni Sistem ✅
```
Soru: "Bu ayki ciromuz ne kadar?"

Yanıt: "Son 30 günde 45.250 ₺ ciro yaptınız (312 sipariş).
Ortalama sepet 145 ₺. Geçen aya göre %12 artış var.
Hafta sonları ciron daha yüksek, cuma-pazar günlerine odaklan."
```
**Avantajlar:**
- Kısa (4 cümle)
- Net rakamlar
- Karşılaştırma var
- Somut öneri

---

## 5. Intent Tespiti Test

Farklı soru şekillerinin aynı intent'i tetiklemesini test edin:

### REVENUE Intent
```json
{"text": "Bu ayki ciromuz ne kadar?"}
{"text": "Ne kadar kazandık?"}
{"text": "Toplam satışlarımız nedir?"}
{"text": "Gelirlerimiz nasıl?"}
```

### STOCK Intent
```json
{"text": "Hangi ürünlerin stoğu kritik?"}
{"text": "Stok durumumuz nasıl?"}
{"text": "Neyin stoğu bitti?"}
{"text": "Envanter raporu?"}
```

### PROFIT Intent
```json
{"text": "Kar marjımız nasıl?"}
{"text": "Ne kadar kar ettik?"}
{"text": "Karlılık durumumuz?"}
{"text": "Net karımız ne kadar?"}
```

**Beklenen:** Her varyasyon benzer kalitede yanıt vermeli.

---

## 6. Performance Test

### Yanıt Süresi Kontrolü

```bash
# Time ile test et
time curl -X POST http://localhost:8000/bi-assistant/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Sube-Id: 1" \
  -H "Content-Type: application/json" \
  -d '{"text": "Bu ayki ciromuz ne kadar?"}'
```

**Beklenen:**
- < 4 saniye (normal)
- < 2 saniye (ideal)

### Token Kullanımı

Backend log'larında:
```
[BI_INTELLIGENCE] Intent: revenue, Data sources: 3
[BI_ASSISTANT] Intent: REVENUE, Data sources: 3
```

**Beklenen:**
- Data sources: 2-5 (fazla değil!)
- Intent detection başarılı

---

## 7. Edge Cases (Uç Durumlar)

### Test: Belirsiz Soru
```json
{"text": "Durum nasıl?"}
```
**Beklenen:** Genel özet veya açıklama isteme

### Test: Çoklu Intent
```json
{"text": "Ciromuz ve stoklarımız nasıl?"}
```
**Beklenen:** Baskın intent'e odaklanma (muhtemelen REVENUE)

### Test: Türkçe Karakter
```json
{"text": "Günlük ciromuz kaç lira?"}
{"text": "Şubenin performansı nasıl?"}
{"text": "İçeceklerin satışı kaç?"}
```
**Beklenen:** Doğru anlama ve yanıt

### Test: Veri Yok Durumu
```json
{"text": "Geçen yılki ciromuz ne kadar?"}
```
**Beklenen:** "Veri bulunamadı" veya mevcut dönem önerisi

---

## 8. Checklist

Test tamamlandığında işaretleyin:

**Temel Testler:**
- [ ] Ciro sorusu doğru yanıtlandı
- [ ] Stok sorusu doğru yanıtlandı
- [ ] Kar sorusu doğru yanıtlandı
- [ ] Personel sorusu doğru yanıtlandı
- [ ] Alışveriş önerisi doğru

**Kalite Kontrolleri:**
- [ ] Yanıtlar kısa (< 6 cümle)
- [ ] Rakamlar doğru
- [ ] Türkçe karakterler düzgün
- [ ] Ton profesyonel ama samimi
- [ ] Somut öneriler var

**Performans:**
- [ ] Yanıt < 4 saniye
- [ ] Intent doğru tespit edildi
- [ ] Sadece ilgili veri kullanıldı (log kontrolü)

**Edge Cases:**
- [ ] Belirsiz sorular yönetildi
- [ ] Veri yok durumu yönetildi
- [ ] Çoklu intent yönetildi

---

## 9. Sorun Giderme

### Problem: "Sistem hatası"

**Kontrol:**
```bash
# OpenAI API key var mı?
echo $OPENAI_API_KEY

# Backend log'ları
tail -f backend/logs/app.log
```

### Problem: Yanıt çok yavaş

**Kontrol:**
- OpenAI API status: https://status.openai.com
- Network latency
- Database connection

### Problem: Yanıtlar tutarsız

**Kontrol:**
```python
# Temperature düşük mü?
# providers.py içinde:
temperature = 0.3  # BI için
```

### Problem: Intent yanlış tespit

**Ekle:**
```python
# bi_intelligence.py içinde INTENT_KEYWORDS'e
QueryIntent.REVENUE: [
    "ciro", "gelir", "kazanç",
    "senin_kelimen"  # EKLE
]
```

---

## 10. Sonraki Adımlar

Testler başarılıysa:

1. ✅ **Production'a Deploy**
2. ✅ **Frontend entegrasyonu**
3. ✅ **Kullanıcı eğitimi**
4. ✅ **Monitoring setup**

Testler başarısızsa:

1. ❌ **Log'ları incele**
2. ❌ **Intent mapping'i gözden geçir**
3. ❌ **Prompt'ları ayarla**
4. ❌ **Veri kalitesini kontrol et**

---

**Test Sürümü:** 1.0
**Tarih:** 2025-01-11
