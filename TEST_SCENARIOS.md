# 🧪 Müşteri Asistanı Test Senaryoları

Müşteri asistanınızın zeka seviyesini test etmek için hazırlanmış senaryolar.

## ✅ Test Edilecek Özellikler

### 1. Karmaşık Sağlık Talepleri
**Amaç:** Asistanın hastalık/sağlık durumlarında doğru ürün önerip öneremediğini test et

#### Test 1.1: Basit Hastalık
```
Müşteri: "Biraz hastayım, ne önerebilirsin?"

Beklenen Davranış:
✅ Adaçayı, Nane Limon, Ihlamur gibi BİTKİ ÇAYLARI önermeli
✅ "Geçmiş olsun" gibi empati göstermeli
✅ Ürünlerin özelliklerini kısa açıklamalı (örn: "boğazı rahatlatır")
❌ Genel "Çay" önermemeli (çünkü çay genel bir kategoridir)
❌ Kahve önermemeli
```

#### Test 1.2: Boğaz Ağrısı
```
Müşteri: "Boğazım çok ağrıyor"

Beklenen Davranış:
✅ Özellikle Adaçayı ve Nane Limon önermeli (boğaz için en iyi)
✅ "çok iyi gelir" gibi ifadeler kullanmalı
❌ Soğuk içecek önermemeli
```

#### Test 1.3: Çok Katmanlı Talep (ZEKA TESTİ)
```
Müşteri: "Yorgunum ama aynı zamanda boğazım da ağrıyor. Ne alsam?"

Beklenen Davranış:
✅ İKİ ihtiyacı da anlamalı: 1) Enerji 2) Boğaz ağrısı
✅ ÖNCELİK vermeli: Boğaz ağrısı daha acil → bitki çayı öner
✅ İKİNCİL seçenek sunmalı: "Enerjiye de ihtiyacınız varsa yanına Çay ekleyebiliriz"
✅ Her ikisine de çözüm önermeli (örn: Adaçayı + Çay)
❌ Sadece bir tanesini çözmemeli
❌ "Ne istersiniz?" gibi pasif sorular sormalı
```

---

### 2. Çok Kriterli Talepler
**Amaç:** Asistanın birden fazla kriteri aynı anda anlayıp doğru filtreleme yapabildiğini test et

#### Test 2.1: İki Kriter
```
Müşteri: "Kafeinli ama sütsüz bir şey istiyorum."

Beklenen Davranış:
✅ Türk Kahvesi, Espresso, Americano önermeli (kafeinli + sütsüz)
✅ Her birinin özelliklerini kısaca açıklamalı
❌ Latte, Cappuccino gibi sütlü kahveler önermemeli
❌ Menengiç Kahvesi önermemeli (kafeinsiz)
```

#### Test 2.2: Üç Kriter (ZEKA TESTİ)
```
Müşteri: "Biraz üşüdüm de sıcak bir şey içsem iyi olur ama kafein istemiyorum çünkü geceleri uyuyamıyorum."

Beklenen Davranış:
✅ 3 kriteri anlamalı: 1) Sıcak 2) Kafeinsiz 3) Uyku dostu
✅ Bitki çayları önermeli (Adaçayı, Nane Limon, Ihlamur)
✅ "rahatlatıcı ve uyku dostu" gibi ifadeler kullanmalı
❌ Kahve önermemeli (kafeinli)
❌ Soğuk içecek önermemeli
```

#### Test 2.3: Negatif Kriter
```
Müşteri: "Soğuk bir şey istiyorum ama çok tatlı olmasın."

Beklenen Davranış:
✅ Soğuk + az tatlı ürünler önermeli (Limonata, Buzlu Çay)
✅ "hafif ekşi" veya "tatlı değil" gibi açıklamalar yapmalı
❌ Tatlı içecekler önermemeli
```

---

### 3. Belirsiz/Genel Talepler
**Amaç:** Asistanın belirsiz talepleri yorumlayıp proaktif önerilerde bulunabildiğini test et

#### Test 3.1: Çok Genel Talep
```
Müşteri: "Soğuk bir şey"

Beklenen Davranış:
✅ 2-3 soğuk içecek seçeneği sunmalı
✅ Her birinin özelliklerini kısaca belirtmeli
✅ Proaktif olmalı: "Hangisini tercih edersiniz?" değil, "Limonata veya Buzlu Çay harika!"
❌ "Ne istersiniz?" gibi açık uçlu sorular sormalı
```

#### Test 3.2: Sadece Greeting
```
Müşteri: "Merhaba"

Beklenen Davranış:
✅ Sıcak karşılama yapmalı
✅ Menüden 3-4 örnek ürün önermeli
✅ "Ne istersiniz?" yerine direkt örnekler vermeli
❌ Pasif kalmamalı
```

---

### 4. Eksik Bilgi ile Siparişler
**Amaç:** Asistanın eksik bilgileri akıllıca tamamlayıp müşteriyi yönlendirebilmesini test et

#### Test 4.1: Genel Ürün Adı
```
Müşteri: "2 kahve"

Beklenen Davranış:
✅ "Kahve" çok genel → popüler kahve türlerini sorgulamalı
✅ "Latte mi, Türk Kahvesi mi yoksa Americano mu?" gibi spesifik seçenekler sunmalı
❌ Varsayım yapıp rastgele kahve seçmemeli
```

#### Test 4.2: Varyasyon Eksik
```
Müşteri: "Bir Türk kahvesi"

Beklenen Davranış:
✅ Varyasyon seçeneklerini sunmalı (sade/şekerli/orta vb.)
✅ Varsayılan varyasyonu seçip sipariş oluşturmalı
✅ Müşteriye onay verip "Afiyet olsun!" demeli
```

---

### 5. Menüde Olmayan Ürünler
**Amaç:** Asistanın menüde olmayan ürünleri nazikçe reddedip alternatif sunabilmesini test et

#### Test 5.1: Olmayan Ürün
```
Müşteri: "Çikolatalı pasta var mı?"

Beklenen Davranış:
✅ "Çikolatalı pasta maalesef şu an menümüzde bulunmuyor" demeli
✅ Direkt alternatif önermeli (tatlı kategorisinden)
❌ "Sipariş almak ister misiniz?" gibi pasif sorular sormalı
❌ Ürün hakkında yorum yapmamalı (örn: "Çikolatalı pasta lezzetlidir")
```

---

### 6. Fiyat Bilgisi
**Amaç:** Asistanın fiyatı doğru zamanda söyleyip söylemediğini test et

#### Test 6.1: Öneri Sırasında Fiyat
```
Müşteri: "Soğuk ne var?"

Beklenen Davranış:
✅ Ürünleri önermeli AMA fiyat söylememeli
❌ "Limonata 30 TL" gibi fiyat içeren ifadeler kullanmamalı
```

#### Test 6.2: Sipariş Onayında Fiyat
```
Müşteri: "2 latte"

Beklenen Davranış:
✅ Sipariş oluşturduktan sonra TOPLAM fiyatı söylemeli
✅ "2 Latte. Toplam [FİYAT] TL. Afiyet olsun!" formatı kullanmalı
```

---

### 7. Ürün Özelliği Filtreleme
**Amaç:** Asistanın menüdeki ürünleri özelliklere göre filtreleyip doğru listeleyebildiğini test et

#### Test 7.1: Sütlü Kahveler
```
Müşteri: "Sütlü kahveleriniz nedir?"

Beklenen Davranış:
✅ Menüden [sütlü, kafeinli] etiketli kahveleri listele (Latte, Cappuccino, Mocha vb.)
✅ Kısa açıklama ekle (örn: "Latte en hafif ve sütlü")
❌ Sütsüz kahveler (Türk Kahvesi, Espresso) önerme
❌ "Kahvelerimiz var" gibi belirsiz cevaplar verme
```

#### Test 7.2: Kafeinsiz İçecekler
```
Müşteri: "Kafeinsiz bir şey istiyorum"

Beklenen Davranış:
✅ Menüden [kafeinsiz] etiketli TÜM ürünleri listele (bitki çayları, kafeinsiz içecekler)
✅ "Kafeinsiz seçeneklerimiz..." diye başla
❌ Kahve, çay gibi kafeinli ürünler önerme
```

#### Test 7.3: Çoklu Kriter (ZEKA TESTİ)
```
Müşteri: "Kafeinli ama sütsüz soğuk bir şey var mı?"

Beklenen Davranış:
✅ 3 kriteri birden karşılayan ürünleri bul: [kafeinli + sütsüz + soğuk]
✅ Soğuk Americano, Buzlu Espresso gibi ürünler öner
❌ Sütlü soğuk içecekler (Iced Latte) önerme
❌ Sıcak içecekler önerme
```

---

### 8. Sağlık Durumları (GENİŞLETİLMİŞ)
**Amaç:** Asistanın farklı sağlık durumlarına uygun ürün önerebilmesini test et

#### Test 8.1: Baş Ağrısı
```
Müşteri: "Baş ağrım var, ne önerebilirsin?"

Beklenen Davranış:
✅ Kafeinli içecekler önermeli (Türk Kahvesi, Espresso, Americano)
✅ "Kafein baş ağrısını hafifletmeye yardımcı olur" bilgisi vermeli
❌ Bitki çayları önermemeli (kafein yok)
❌ Kafeinsiz ürünler önermemeli
```

#### Test 8.2: Uyku Problemi
```
Müşteri: "Uykum var ama bir şey içmek istiyorum"

Beklenen Davranış:
✅ Kafeinsiz + rahatlatıcı ürünler önermeli (bitki çayları)
✅ "Uyku dostu, rahatlatıcı" gibi ifadeler kullanmalı
❌ Kahve gibi kafeinli ürünler önermemeli
❌ "Sizi canlandırır" gibi uyku kaçıran ifadeler kullanmamalı
```

#### Test 8.3: Yorgunluk
```
Müşteri: "Çok yorgunum, enerji lazım"

Beklenen Davranış:
✅ Kafeinli içecekler önermeli (kahveler)
✅ "Sizi canlandırır, enerji verir" gibi ifadeler kullanmalı
❌ Bitki çayları önermemeli (enerji vermez)
```

---

## 🎯 Test Etme Adımları

1. **Backend'i Başlat:**
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   ```

2. **Frontend'i Başlat:**
   ```bash
   cd frontend-modern
   npm run dev
   ```

3. **Test Et:**
   - Yukarıdaki senaryoları sırayla dene
   - Her testte asistanın cevaplarını not al
   - Beklenen davranışla karşılaştır

---

## 📊 Sonuç Değerlendirmesi

### Başarı Kriterleri:
- ✅ **%80+ başarı:** Mükemmel! Asistan çok zeki ve anlayışlı
- ⚠️ **%60-80 başarı:** İyi ama iyileştirme gerekiyor
- ❌ **%60 altı başarı:** Ciddi sorunlar var, daha fazla iyileştirme gerekli

### Test Sonuçları (Manuel Doldurun):
```
Test 1.1 (Basit Hastalık): [ ] ✅ / [ ] ❌
Test 1.2 (Boğaz Ağrısı): [ ] ✅ / [ ] ❌
Test 1.3 (Çok Katmanlı): [ ] ✅ / [ ] ❌
Test 2.1 (İki Kriter): [ ] ✅ / [ ] ❌
Test 2.2 (Üç Kriter): [ ] ✅ / [ ] ❌
Test 2.3 (Negatif Kriter): [ ] ✅ / [ ] ❌
Test 3.1 (Genel Talep): [ ] ✅ / [ ] ❌
Test 3.2 (Greeting): [ ] ✅ / [ ] ❌
Test 4.1 (Genel Ürün): [ ] ✅ / [ ] ❌
Test 4.2 (Varyasyon Eksik): [ ] ✅ / [ ] ❌
Test 5.1 (Olmayan Ürün): [ ] ✅ / [ ] ❌
Test 6.1 (Öneri Fiyatı): [ ] ✅ / [ ] ❌
Test 6.2 (Sipariş Fiyatı): [ ] ✅ / [ ] ❌
Test 7.1 (Sütlü Kahveler): [ ] ✅ / [ ] ❌
Test 7.2 (Kafeinsiz): [ ] ✅ / [ ] ❌
Test 7.3 (Çoklu Kriter): [ ] ✅ / [ ] ❌
Test 8.1 (Baş Ağrısı): [ ] ✅ / [ ] ❌
Test 8.2 (Uyku Problemi): [ ] ✅ / [ ] ❌
Test 8.3 (Yorgunluk): [ ] ✅ / [ ] ❌

Toplam Başarı: ___ / 19 (% ___)
```

---

## 💡 Sorun Çözme İpuçları

### Eğer asistan hala sorun yaşıyorsa:

1. **LLM Provider'ı Kontrol Et:**
   - `backend/app/core/config.py` içindeki `LLM_PROVIDER` ayarını kontrol et
   - Anthropic (Claude) veya OpenAI (GPT-4) kullandığından emin ol
   - Zayıf modeller (GPT-3.5 gibi) bu kadar karmaşık promptları işleyemeyebilir

2. **Temperature Ayarını Düşür:**
   - `backend/app/routers/assistant.py` içinde `temperature=0.3-0.5` olmalı
   - Yüksek temperature (>0.7) tutarsız sonuçlara yol açar

3. **Menü Verilerini Kontrol Et:**
   - Menüde yeterli ürün var mı? (En az 10-15 ürün olmalı)
   - Kategoriler doğru mu? (sıcak/soğuk, kafeinli/kafeinsiz vb.)
   - Ürün açıklamaları yeterli mi?

4. **Loglara Bak:**
   - Backend loglarında hata var mı?
   - Intent detection düzgün çalışıyor mu?
   - Parse işlemi başarılı mı?
