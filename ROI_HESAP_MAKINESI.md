# 💰 ROI Hesaplayıcı - Neso Modüler

## İşletme İçin Yıllık Kazanç Hesaplama

### Formül Özeti:

```
TOPLAM YILLIK KAZANÇ = 
  Yazılım Tasarrufu + 
  Sipariş Hatası Azaltma + 
  Stok Kaybı Önleme + 
  Verimlilik Artışı + 
  Data-Driven Optimizasyon
```

---

## 1. YAZILIM MALİYETİ TASARRUFU

**Geleneksel Sistem Maliyeti (Aylık):**
- POS Lisans: ₺[POS_LISANS]
- Stok Yazılımı: ₺[STOK_YAZILIM]
- Raporlama: ₺[RAPORLAMA]
- IT Desteği: ₺[IT_DESTEK]
- Güncelleme: ₺[GUNCELLEME]
- Backup: ₺[BACKUP]

**Toplam Geleneksel:** ₺[TOPLAM_GELENEKSEL]/ay

**Neso Modüler:** ₺[NESO_FIYAT]/ay

**Aylık Tasarruf:** ₺[TOPLAM_GELENEKSEL] - ₺[NESO_FIYAT] = **₺[AYLIK_TASARRUF]**

**Yıllık Tasarruf:** ₺[AYLIK_TASARRUF] × 12 = **₺[YILLIK_YAZILIM_TASARRUF]**

---

## 2. SİPARİŞ HATASI AZALTMA

**İşletme Bilgileri:**
- Günlük sipariş sayısı: [GUNLUK_SIPARIS]
- Ortalama sipariş tutarı: ₺[ORTALAMA_SIPARIS]
- Geleneksel hata oranı: %[GELENEKSEL_HATA] (örn: %10)
- Neso hata oranı: %[NESO_HATA] (örn: %2.5)

**Hesaplama:**
- Günlük ciro: [GUNLUK_SIPARIS] × ₺[ORTALAMA_SIPARIS] = **₺[GUNLUK_CIRO]**
- Aylık ciro: ₺[GUNLUK_CIRO] × 30 = **₺[AYLIK_CIRO]**

- Geleneksel aylık kayıp: ₺[AYLIK_CIRO] × %[GELENEKSEL_HATA] = **₺[GELENEKSEL_KAYIP]**
- Neso aylık kayıp: ₺[AYLIK_CIRO] × %[NESO_HATA] = **₺[NESO_KAYIP]**
- Aylık kazanç: ₺[GELENEKSEL_KAYIP] - ₺[NESO_KAYIP] = **₺[AYLIK_SIPARIS_KAZANC]**

**Yıllık Kazanç:** ₺[AYLIK_SIPARIS_KAZANC] × 12 = **₺[YILLIK_SIPARIS_KAZANC]**

---

## 3. STOK KAYBI ÖNLEME

**İşletme Bilgileri:**
- Aylık stok değeri: ₺[AYLIK_STOK]
- Geleneksel kayıp oranı: %[GELENEKSEL_STOK_KAYIP] (örn: %6)
- Neso kayıp oranı: %[NESO_STOK_KAYIP] (örn: %0.75)

**Hesaplama:**
- Geleneksel aylık kayıp: ₺[AYLIK_STOK] × %[GELENEKSEL_STOK_KAYIP] = **₺[GELENEKSEL_STOK_KAYIP]**
- Neso aylık kayıp: ₺[AYLIK_STOK] × %[NESO_STOK_KAYIP] = **₺[NESO_STOK_KAYIP]**
- Aylık kazanç: ₺[GELENEKSEL_STOK_KAYIP] - ₺[NESO_STOK_KAYIP] = **₺[AYLIK_STOK_KAZANC]**

**Yıllık Kazanç:** ₺[AYLIK_STOK_KAZANC] × 12 = **₺[YILLIK_STOK_KAZANC]**

---

## 4. VERİMLİLİK ARTIŞI

**İşletme Bilgileri:**
- Ortalama çalışan sayısı: [CALISAN_SAYISI]
- Ortalama çalışan maliyeti: ₺[CALISAN_MALIYET]/ay
- Günlük zaman tasarrufu: [GUNLUK_SAAT] saat (örn: 1.5)

**Hesaplama:**
- Aylık çalışma saatleri: 30 gün × 8 saat = 240 saat
- Saatlik çalışan maliyeti: ₺[CALISAN_MALIYET] ÷ 240 = **₺[SAATLIK_MALIYET]**

- Günlük tasarruf: [GUNLUK_SAAT] saat × ₺[SAATLIK_MALIYET] = **₺[GUNLUK_VERIMLILIK]**
- Aylık tasarruf: ₺[GUNLUK_VERIMLILIK] × 30 = **₺[AYLIK_VERIMLILIK]**

**Yıllık Tasarruf:** ₺[AYLIK_VERIMLILIK] × 12 = **₺[YILLIK_VERIMLILIK]**

---

## 5. DATA-DRIVEN OPTİMİZASYON

**İşletme Bilgileri:**
- Aylık ciro: ₺[AYLIK_CIRO] (yukarıdan)
- Gelir artış oranı: %[GELIR_ARTIS] (örn: %6)
- Maliyet azaltma oranı: %[MALIYET_AZALTMA] (örn: %4)

**Hesaplama:**
- Gelir artışı: ₺[AYLIK_CIRO] × %[GELIR_ARTIS] = **₺[AYLIK_GELIR_ARTIS]**
- Stok maliyeti (cironun %40'ı varsayımı): ₺[AYLIK_CIRO] × %40 = **₺[STOK_MALIYET]**
- Maliyet azaltma: ₺[STOK_MALIYET] × %[MALIYET_AZALTMA] = **₺[AYLIK_MALIYET_AZALTMA]**
- Toplam aylık kazanç: ₺[AYLIK_GELIR_ARTIS] + ₺[AYLIK_MALIYET_AZALTMA] = **₺[AYLIK_OPTIMIZASYON]**

**Yıllık Kazanç:** ₺[AYLIK_OPTIMIZASYON] × 12 = **₺[YILLIK_OPTIMIZASYON]**

---

## 6. TOPLAM YILLIK KAZANÇ

**Özet:**
1. Yazılım Tasarrufu: **₺[YILLIK_YAZILIM_TASARRUF]**
2. Sipariş Hatası Azaltma: **₺[YILLIK_SIPARIS_KAZANC]**
3. Stok Kaybı Önleme: **₺[YILLIK_STOK_KAZANC]**
4. Verimlilik Artışı: **₺[YILLIK_VERIMLILIK]**
5. Data-Driven Optimizasyon: **₺[YILLIK_OPTIMIZASYON]**

**TOPLAM YILLIK KAZANÇ:** **₺[TOPLAM_YILLIK_KAZANC]**

---

## 7. ROI HESAPLAMA

**Yatırım:**
- Neso Modüler yıllık maliyet: ₺[NESO_FIYAT] × 12 = **₺[YILLIK_MALIYET]**

**ROI:**
- ROI = (₺[TOPLAM_YILLIK_KAZANC] - ₺[YILLIK_MALIYET]) / ₺[YILLIK_MALIYET] × 100
- ROI = **%[ROI]**

**Geri Ödeme Süresi:**
- Geri Ödeme (gün) = ₺[YILLIK_MALIYET] / (₺[TOPLAM_YILLIK_KAZANC] / 365)
- Geri Ödeme = **[GERI_ODEME_GUN] gün**

---

## 📊 ÖRNEK HESAPLAMA

### Varsayımlar:
- **Günlük sipariş:** 100
- **Ortalama sipariş:** ₺150
- **Aylık stok değeri:** ₺50,000
- **Çalışan sayısı:** 5
- **Çalışan maliyeti:** ₺15,000/ay
- **Günlük zaman tasarrufu:** 1.5 saat
- **Neso Pro Plan:** ₺999/ay

### Sonuçlar:

1. **Yazılım Tasarrufu:** ₺[1,800-5,600/ay × 12] = **₺21,600 - ₺67,200**
2. **Sipariş Hatası:** ₺[33,750/ay × 12] = **₺405,000**
3. **Stok Kaybı:** ₺[2,625/ay × 12] = **₺31,500**
4. **Verimlilik:** ₺[2,813/ay × 12] = **₺33,750**
5. **Optimizasyon:** ₺[29,000/ay × 12] = **₺348,000**

**TOPLAM:** **₺838,850 - ₺884,450/yıl**

**ROI:** **6,970%**  
**Geri Ödeme:** **5 gün**

---

## 💡 HIZLI HESAP ARACI (Excel Formülü)

Excel'de hesaplamak için:

```
A1: Günlük Sipariş
B1: Ortalama Sipariş Tutarı
C1: Aylık Stok Değeri
D1: Çalışan Sayısı
E1: Çalışan Maliyeti/ay
F1: Neso Plan Fiyatı/ay

Günlük Ciro = A1 * B1
Aylık Ciro = Günlük Ciro * 30

Sipariş Hatası Kazancı = (Aylık Ciro * 0.075) * 12
Stok Kazancı = (C1 * 0.0525) * 12
Verimlilik = ((E1/240) * 1.5 * 30) * 12
Optimizasyon = ((Aylık Ciro * 0.06) + (Aylık Ciro * 0.4 * 0.04)) * 12

TOPLAM = Sipariş + Stok + Verimlilik + Optimizasyon
ROI = (TOPLAM - (F1 * 12)) / (F1 * 12) * 100
```

---

## 🎯 SONUÇ

Bu hesaplama aracı ile her işletme için özelleştirilmiş ROI hesabı yapılabilir. Genel olarak:

- **Küçük işletme (günlük 50 sipariş):** ₺200K-400K/yıl kazanç
- **Orta ölçek (günlük 100 sipariş):** ₺800K-900K/yıl kazanç
- **Büyük işletme (günlük 200+ sipariş):** ₺1.5M-2M+/yıl kazanç

**Ortalama ROI:** %5,000-7,000  
**Ortalama Geri Ödeme:** 3-7 gün


