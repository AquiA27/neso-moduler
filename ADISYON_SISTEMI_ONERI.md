# Adisyon Sistemi Önerisi

## Mevcut Sistemin Sorunları
- Ödemeler siparişlere bağlı değil, sadece masa bazında
- Bakiye hesaplama karmaşık (odendi/hazir siparişler karışık)
- Hangi ödemenin hangi siparişe ait olduğu belli değil

## Adisyon Sisteminin Avantajları
✅ Daha temiz ve anlaşılır mantık
✅ Bakiye hesaplama basit: adisyon_toplamı - ödemeler
✅ Her masa için tek bir hesap
✅ Geçmiş verileri koruma

## Yapılacak Değişiklikler

### 1. Veritabanı Değişiklikleri
```sql
-- Yeni adisyons tablosu
CREATE TABLE adisyons (
    id BIGSERIAL PRIMARY KEY,
    sube_id BIGINT NOT NULL,
    masa TEXT NOT NULL,
    acilis_zamani TIMESTAMPTZ DEFAULT NOW(),
    kapanis_zamani TIMESTAMPTZ,
    durum TEXT DEFAULT 'acik', -- 'acik', 'kapali'
    toplam_tutar NUMERIC(10,2) DEFAULT 0,
    odeme_toplam NUMERIC(10,2) DEFAULT 0,
    bakiye NUMERIC(10,2) DEFAULT 0,
    iskonto_orani NUMERIC(5,2) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- siparisler tablosuna adisyon_id ekle
ALTER TABLE siparisler ADD COLUMN adisyon_id BIGINT REFERENCES adisyons(id);

-- odemeler tablosuna adisyon_id ekle
ALTER TABLE odemeler ADD COLUMN adisyon_id BIGINT REFERENCES adisyons(id);
```

### 2. Yeni Akış
1. **Masa açılışı**: Adisyon oluşturulur (durum='acik')
2. **Sipariş ekleme**: Siparişler adisyon'a bağlanır
3. **Ödeme alma**: Ödemeler adisyon'a yapılır
4. **Adisyon kapatma**: 
   - Tüm "hazir" siparişler "odendi" olur
   - Stok düşer
   - Adisyon durumu "kapali" olur

### 3. Backend Değişiklikleri
- `adisyons` tablosu için CRUD endpoint'leri
- Sipariş ekleme: Adisyon'a bağlama
- Ödeme ekleme: Adisyon'a bağlama
- Adisyon kapatma: Tüm siparişleri finalize etme
- Bakiye hesaplama: `adisyon.toplam_tutar - adisyon.odeme_toplam`

### 4. Frontend Değişiklikleri
- Adisyon listesi görünümü
- Adisyon detay sayfası
- Adisyon kapatma butonu
- Ödeme formu adisyon'a bağlı

## Alternatif: Basitleştirilmiş Sistem
Mevcut sistemi koruyup sadece mantığı basitleştirme:
- Sadece "hazir" durumundaki siparişlerin toplamı = bakiye
- Ödemeler yapıldıkça bakiye azalır
- Bakiye sıfır olduğunda "hazir" siparişler otomatik "odendi" olur

## Öneri
**Adisyon sistemine geçiş** - Daha temiz ve sürdürülebilir bir çözüm.


