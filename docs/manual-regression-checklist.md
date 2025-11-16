# Manual Regression Checklist (Release Baseline)

Bu doküman her yeni sürüm öncesinde çalıştırılacak manuel senaryoların adım adım kontrol listesini içerir. Senaryolar üç ana başlık altında gruplanmıştır: **Sipariş Akışı**, **Stok Yönetimi** ve **Raporlar & İşletme Asistanı**. Her senaryoda test ortamı, önkoşul, izlenecek adımlar ve beklenen sonuçlar belirtilmiştir.

> İpucu: Her senaryoyu tamamladıktan sonra tarih & sürüm numarasıyla birlikte "PASS / FAIL" notu ekleyin. Yaşanan sorunları kısa açıklama ve ekran görüntüsüyle destekleyin.

---

## 1. Sipariş Akışı

### 1.1 Müşteri QR → Masa → Sipariş oluşturma
- **Amaç:** QR ile gelen müşteri için doğru masaya sipariş açılabildiğini doğrulamak.
- **Önkoşul:** Masa listesinde aktif bir masa; müşteri menüsü yayında (`/musteri?qr=MASA_ID`)
- **Adımlar:**
  1. Tarayıcıda QR URL’sine gidin, “Menüyü Gör” veya “Asistana Bağlan” butonlarından menüyü açın.
  2. Menüden en az 2 farklı ürün seçin, sepete ekleyin.
  3. Sepeti onaylayıp sipariş gönderin.
- **Beklenen Sonuçlar:**
  - Müşteri ekranında “siparişiniz alındı” mesajı görüntülenir.
  - Yönetim panelindeki `Masalar` ekranında ilgili masaya yeni adisyon açılır.
  - `Mutfak` ve `Kasa` panellerinde sipariş kuyruğa düşer.

### 1.2 Sepet düzenleme & ödeme
- **Amaç:** Yönetici panelinde siparişin düzenlenmesi ve kapatılması akışını doğrulamak.
- **Önkoşul:** Önceki senaryoda açılan açık adisyon.
- **Adımlar:**
  1. Yönetim panelinde adisyonu açın, ürünü silin veya adet değiştirin.
  2. İskonto (%) veya tutar uygularsanız sonuçları gözlemleyin.
  3. Ödeme alma ekranında nakit / kart / diğer yöntemlerden biriyle tahsilat girin, adisyonu kapatın.
- **Beklenen Sonuçlar:**
  - Sepet tutarı değişikliklere göre yeniden hesaplanır.
  - İndirim sonrası ara toplam, vergi, toplam tutar tutarlı şekilde güncellenir.
  - Adisyon kapatıldığında durum “Ödendi” olur ve kasa raporlarında görünür.

### 1.3 Gerçek zamanlı bildirimler
- **Amaç:** Realtime güncellemelerin mutfak ve kasa ekranlarına düştüğünü doğrulamak.
- **Önkoşul:** `npm run dev` ile frontend, backend servisi ayakta; mutfak/kasa sayfaları farklı tarayıcı sekmelerinde açık.
- **Adımlar:**
  1. Yeni sipariş gönderin veya var olan siparişi güncelleyin.
  2. Diğer sekmelerde websocket üzerinden veri akışını izleyin.
- **Beklenen Sonuçlar:**
  - Sipariş durumu ve içerik değişiklikleri 1-2 saniye içinde düşer.
  - Hatada websocket bağlantısı yeniden kuruluyor olmalı (konsolda hata gözlemlenmez).

---

## 2. Stok Yönetimi

### 2.1 Stok kalemi oluşturma ve giriş/çıkış
- **Amaç:** Yeni stok kalemi ekleme, giriş ve çıkış hareketlerinin kayda geçtiğini doğrulamak.
- **Önkoşul:** Yönetici rolüyle giriş yapılmış olmalı.
- **Adımlar:**
  1. `Stok` sayfasında yeni kalem ekleyin (kategori, minimum stok, alış fiyatı gibi alanları doldurun).
  2. Aynı kalem için stok giriş hareketi ekleyin; ardından stok çıkışı kaydedin.
  3. Hareket geçmişinde kayıtların göründüğünü kontrol edin.
- **Beklenen Sonuçlar:**
  - Stok miktarı giriş/çıkış sonrası doğru güncellenir.
  - Kritik stok uyarısı varsa badge/pill olarak görünür.

### 2.2 Reçeteli ürün siparişi sonrası stok düşümü
- **Amaç:** Reçete tanımlı ürün satıldığında ilgili stokların otomatik düşüp düşmediğini kontrol etmek.
- **Önkoşul:** Reçetesi tanımlı ürün ve karşılığı stok kalemleri mevcut.
- **Adımlar:**
  1. Reçeteli ürünü menüden veya yönetim panelinden siparişe ekleyin ve adisyonu kapatın.
  2. İlgili stok kalemlerinin yeni miktarlarını inceleyin.
- **Beklenen Sonuçlar:**
  - Reçetedeki miktarlar çarpanla (adet) birlikte stoktan düşülür.
  - Kritik eşik aşılırsa stok listesinde uyarı görünür.

### 2.3 Alışveriş önerileri
- **Amaç:** Kritiğe yakın stoklar için önerilen miktarların, günlük tüketim baz alınarak hesaplandığını doğrulamak.
- **Önkoşul:** Son 30 günde satış girişi olan ve min stok sınırına yaklaşmış kalemler.
- **Adımlar:**
  1. `Stok → Alışveriş Önerileri` veya BI asistanında “alışveriş önerisi” isteyin.
  2. Önerilen miktarların stok tüketimiyle tutarlı olup olmadığını kontrol edin (en azından makul aralık).
- **Beklenen Sonuçlar:**
  - Liste kritikte olan stokları gösterir (mevcut, min, önerilen).
  - Önerilen miktar, 7 günlük tüketim veya minimum stok kriterine göre hesaplanmış olmalıdır.

---

## 3. Raporlar & İşletme Asistanı

### 3.1 Dashboard doğrulaması
- **Amaç:** Ana paneldeki kartların ve grafiklerin API verisiyle uyumlu olduğunu ve cache sonrası manuel yenilemeyle güncellendiğini kontrol etmek.
- **Önkoşul:** Backend API ve yeni React Query entegrasyonu aktif.
- **Adımlar:**
  1. Dashboard sayfasını açın, kartlardaki değerleri not alın.
  2. `Yenile` butonuna basın; arka uçta veri değiştiyse kartların güncellendiğini doğrulayın.
  3. Saatlik yoğunluk ve popüler ürün grafikleri için dönem filtrelerini değiştirin (gün/hafta/ay).
- **Beklenen Sonuçlar:**
  - Query cache ilk açılışta daha hızlı yükleme sağlar, `Yenile` ile veri tekrar istenir.
  - Grafikler seçilen döneme göre veri setini değiştirir, eksenler doğru formatlanır.

### 3.2 Kategori bazlı satış raporu
- **Amaç:** BI asistanının “kategorilere göre ürünler raporunu yorumla” gibi sorgulara veri odaklı yanıt verdiğini doğrulamak.
- **Önkoşul:** Menü kayıtlarında kategori alanı dolu olmalı; yakın dönemde sipariş verisi bulunmalı.
- **Adımlar:**
  1. BI asistanına “kategorilere göre ürünler raporunu yorumlasana” yazın.
  2. Dönen yanıtta kategori, ciro, adet ve pay bilgilerinin listelendiğini kontrol edin.
  3. Gerekiyorsa farklı dönem seçip aynı isteği tekrarlayın (“son 7 gün kategoriler” gibi).
- **Beklenen Sonuçlar:**
  - Yanıtta en azından en çok ciro getiren birkaç kategori sıralanır.
  - `% pay` toplamı kabaca 100’e yaklaşır; toplam ciro tutarı not alınabilir.

### 3.3 Finansal rapor & kasa hareketleri
- **Amaç:** Finansal raporlarda günlük/haftalık/aylık toplamların, adisyon kapanışlarıyla uyumlu olduğunu doğrulamak.
- **Adımlar:**
  1. Dashboard veya rapor ekranındaki ciro/gider/net kar toplamlarını önceki testlerdeki işlemlerle karşılaştırın.
  2. Kasa hareket listesinde kapanan adisyonların ödeme kayıtlarını bulun.
- **Beklenen Sonuçlar:**
  - Kasa hareket toplamı adisyon kapanışlarıyla eşleşir.
  - Gider ekleme/güncelleme yapıldıysa raporlarda yansır.

### 3.4 BI asistanı temel yetkinlikleri
- **Amaç:** Önceki prompt’larla asistanın kısa, aksiyon odaklı yanıtlar üretmeye devam ettiğini doğrulamak.
- **Adımlar:**
  1. “Bu hafta durumumuz nedir?”, “Stok maliyet analizini çıkar” gibi sorular yöneltin.
  2. Yanıtların format (3 blok, kısa), ton (pozitif/uzman) ve veri odaklılık açısından beklentiyle uyumlu olduğunu onaylayın.
- **Beklenen Sonuçlar:**
  - Yanıt üç blok formatında (Haftalık Nabız / Öne Çıkanlar / Hemen Yapılacaklar) gelir.
  - İçerik işletmenin gerçek verisine atıfta bulunur; gereksiz uzun paragraflardan kaçınır.

---

## Sonraki Adımlar
- Her senaryo için “Test Edildi” kutucuğu eklenip sonuca göre PASS/FAIL notu tutulmalı.
- FAIL durumunda, hata ayrıntıları ve tekrar adımları projedeki issue tracker’a girilmeli.
- Release sürecinde bu checklist standart bir “Manual Smoke/Regression” aşaması olarak zorunlu hale getirilmeli.

---

> **Güncelleme & Sürümleme:** Bu dokümanı her büyük feature eklemesinde gözden geçirip yeni senaryolar ekleyin veya modası geçmiş akışları kaldırın. Versiyon numarası / tarih başlıklarını güncel tutmanız, ileride otomasyon çalışmalarına temel sağlar.


