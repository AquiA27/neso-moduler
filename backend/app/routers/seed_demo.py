# backend/app/routers/seed_demo.py
"""
Geçici demo veri seed endpoint'i.
Canlı sunucuda /seed/demo POST çağırılarak demo verisi oluşturulur.
Deploy sonrası kaldırılmalıdır.
"""
from fastapi import APIRouter, HTTPException
from ..db.database import db
from ..core.security import hash_password
import json
import random
import uuid
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/seed", tags=["Seed (Geçici)"])

# Sabit bir güvenlik anahtarı (basit koruma)
SEED_SECRET = "neso-demo-seed-2026"

MENU_ITEMS = [
    {"ad": "Türk Kahvesi", "fiyat": 55, "kategori": "Sıcak İçecekler", "aciklama": "Geleneksel köpüklü Türk kahvesi"},
    {"ad": "Espresso", "fiyat": 50, "kategori": "Sıcak İçecekler", "aciklama": "Yoğun İtalyan espresso"},
    {"ad": "Americano", "fiyat": 60, "kategori": "Sıcak İçecekler", "aciklama": "Espresso + sıcak su"},
    {"ad": "Latte", "fiyat": 75, "kategori": "Sıcak İçecekler", "aciklama": "Espresso + buharla ısıtılmış süt"},
    {"ad": "Cappuccino", "fiyat": 75, "kategori": "Sıcak İçecekler", "aciklama": "Espresso + süt köpüğü"},
    {"ad": "Mocha", "fiyat": 85, "kategori": "Sıcak İçecekler", "aciklama": "Espresso + çikolata + süt"},
    {"ad": "Çay (Çaydanlık)", "fiyat": 40, "kategori": "Sıcak İçecekler", "aciklama": "2 kişilik demlik çay"},
    {"ad": "Sıcak Çikolata", "fiyat": 70, "kategori": "Sıcak İçecekler", "aciklama": "Belçika çikolatalı"},
    {"ad": "Ice Latte", "fiyat": 85, "kategori": "Soğuk İçecekler", "aciklama": "Buzlu latte"},
    {"ad": "Frappe", "fiyat": 90, "kategori": "Soğuk İçecekler", "aciklama": "Buzlu karışık kahve"},
    {"ad": "Limonata", "fiyat": 60, "kategori": "Soğuk İçecekler", "aciklama": "Taze sıkılmış limonata"},
    {"ad": "Smoothie (Mango)", "fiyat": 95, "kategori": "Soğuk İçecekler", "aciklama": "Taze mangolu smoothie"},
    {"ad": "Soğuk Çay", "fiyat": 50, "kategori": "Soğuk İçecekler", "aciklama": "Şeftali aromalı"},
    {"ad": "Ayran", "fiyat": 35, "kategori": "Soğuk İçecekler", "aciklama": "Geleneksel ev yapımı ayran"},
    {"ad": "Serpme Kahvaltı (2 Kişilik)", "fiyat": 450, "kategori": "Kahvaltı", "aciklama": "Zengin serpme kahvaltı tabağı"},
    {"ad": "Sahanda Yumurta", "fiyat": 90, "kategori": "Kahvaltı", "aciklama": "Tereyağında sahanda yumurta"},
    {"ad": "Menemen", "fiyat": 95, "kategori": "Kahvaltı", "aciklama": "Sebzeli menemen"},
    {"ad": "Tavuk Sote", "fiyat": 180, "kategori": "Yemekler", "aciklama": "Sebzeli tavuk sote + pilav"},
    {"ad": "Köfte Izgara", "fiyat": 200, "kategori": "Yemekler", "aciklama": "El yapımı ızgara köfte + patates"},
    {"ad": "Makarna Bolonez", "fiyat": 160, "kategori": "Yemekler", "aciklama": "Kıymalı bolonez soslu makarna"},
    {"ad": "Tavuk Wrap", "fiyat": 150, "kategori": "Yemekler", "aciklama": "Izgara tavuklu wrap"},
    {"ad": "Caesar Salata", "fiyat": 140, "kategori": "Yemekler", "aciklama": "Tavuklu Caesar salata"},
    {"ad": "Cheesecake", "fiyat": 110, "kategori": "Tatlılar", "aciklama": "New York usulü cheesecake"},
    {"ad": "Brownie", "fiyat": 90, "kategori": "Tatlılar", "aciklama": "Çikolatalı brownie + dondurma"},
    {"ad": "San Sebastian", "fiyat": 120, "kategori": "Tatlılar", "aciklama": "San Sebastian cheesecake"},
    {"ad": "Sufle", "fiyat": 100, "kategori": "Tatlılar", "aciklama": "Sıcak çikolatalı sufle"},
    {"ad": "Tiramisu", "fiyat": 110, "kategori": "Tatlılar", "aciklama": "İtalyan tiramisu"},
]

STOK_ITEMS = [
    {"ad": "Kahve Çekirdeği (Arabica)", "kategori": "Hammadde", "birim": "kg", "mevcut": 15, "min": 5, "alis_fiyat": 450},
    {"ad": "Süt (Günlük)", "kategori": "Hammadde", "birim": "litre", "mevcut": 30, "min": 10, "alis_fiyat": 35},
    {"ad": "Çikolata Sosu", "kategori": "Hammadde", "birim": "litre", "mevcut": 5, "min": 2, "alis_fiyat": 120},
    {"ad": "Çay (Rize Turist)", "kategori": "Hammadde", "birim": "kg", "mevcut": 8, "min": 3, "alis_fiyat": 280},
    {"ad": "Şeker", "kategori": "Hammadde", "birim": "kg", "mevcut": 20, "min": 5, "alis_fiyat": 45},
    {"ad": "Yumurta", "kategori": "Hammadde", "birim": "adet", "mevcut": 120, "min": 30, "alis_fiyat": 5.5},
    {"ad": "Tereyağı", "kategori": "Hammadde", "birim": "kg", "mevcut": 4, "min": 2, "alis_fiyat": 350},
    {"ad": "Un", "kategori": "Hammadde", "birim": "kg", "mevcut": 25, "min": 10, "alis_fiyat": 42},
    {"ad": "Tavuk Göğüs", "kategori": "Hammadde", "birim": "kg", "mevcut": 12, "min": 5, "alis_fiyat": 180},
    {"ad": "Kıyma (Dana)", "kategori": "Hammadde", "birim": "kg", "mevcut": 8, "min": 3, "alis_fiyat": 350},
    {"ad": "Domates", "kategori": "Sebze", "birim": "kg", "mevcut": 10, "min": 3, "alis_fiyat": 35},
    {"ad": "Biber", "kategori": "Sebze", "birim": "kg", "mevcut": 6, "min": 2, "alis_fiyat": 40},
    {"ad": "Soğan", "kategori": "Sebze", "birim": "kg", "mevcut": 8, "min": 3, "alis_fiyat": 20},
    {"ad": "Limon", "kategori": "Meyve", "birim": "kg", "mevcut": 5, "min": 2, "alis_fiyat": 50},
    {"ad": "Peçete", "kategori": "Sarf Malzeme", "birim": "paket", "mevcut": 50, "min": 10, "alis_fiyat": 15},
    {"ad": "Bardak (Karton)", "kategori": "Sarf Malzeme", "birim": "adet", "mevcut": 200, "min": 50, "alis_fiyat": 3.5},
]

MASA_ADLARI = ["Masa 1","Masa 2","Masa 3","Masa 4","Masa 5","Masa 6","Masa 7","Masa 8","Bahçe 1","Bahçe 2","VIP 1","Bar 1"]

GIDER_ITEMS = [
    {"kategori": "Kira", "aciklama": "Mart 2026 kira ödemesi", "tutar": 15000, "gun_offset": -5},
    {"kategori": "Elektrik", "aciklama": "Şubat 2026 elektrik faturası", "tutar": 3200, "gun_offset": -8},
    {"kategori": "Su", "aciklama": "Şubat 2026 su faturası", "tutar": 850, "gun_offset": -8},
    {"kategori": "İnternet", "aciklama": "Mart 2026 internet", "tutar": 450, "gun_offset": -3},
    {"kategori": "Personel", "aciklama": "Personel maaşları - Şubat", "tutar": 45000, "gun_offset": -1},
    {"kategori": "Hammadde", "aciklama": "Haftalık market alışverişi", "tutar": 4500, "gun_offset": -2},
    {"kategori": "Hammadde", "aciklama": "Kahve çekirdeği siparişi", "tutar": 6750, "gun_offset": -6},
    {"kategori": "Temizlik", "aciklama": "Temizlik malzemeleri", "tutar": 800, "gun_offset": -4},
    {"kategori": "Bakım", "aciklama": "Espresso makinesi bakımı", "tutar": 1200, "gun_offset": -10},
    {"kategori": "Pazarlama", "aciklama": "Instagram reklam kampanyası", "tutar": 2000, "gun_offset": -7},
]


@router.post("/demo")
async def seed_demo_data(secret: str = ""):
    """Demo verisi oluştur (tek kullanımlık)"""
    if secret != SEED_SECRET:
        raise HTTPException(status_code=403, detail="Geçersiz seed anahtarı")

    now = datetime.now(timezone.utc)
    results = {"steps": []}

    try:
        # 1. İşletme
        existing = await db.fetch_one("SELECT id FROM isletmeler WHERE ad = :ad", {"ad": "Fıstık Cafe & Bistro"})
        if existing:
            isletme_id = existing["id"]
            results["steps"].append(f"İşletme mevcut: ID={isletme_id}")
        else:
            row = await db.fetch_one(
                "INSERT INTO isletmeler (ad, telefon, aktif) VALUES (:ad, :tel, TRUE) RETURNING id",
                {"ad": "Fıstık Cafe & Bistro", "tel": "0532 555 12 34"}
            )
            isletme_id = row["id"]
            results["steps"].append(f"İşletme oluşturuldu: ID={isletme_id}")

        # 2. Şube
        existing_sube = await db.fetch_one(
            "SELECT id FROM subeler WHERE isletme_id = :iid AND ad = :ad",
            {"iid": isletme_id, "ad": "Merkez Şube"}
        )
        if existing_sube:
            sube_id = existing_sube["id"]
            results["steps"].append(f"Şube mevcut: ID={sube_id}")
        else:
            row = await db.fetch_one(
                "INSERT INTO subeler (isletme_id, ad, aktif) VALUES (:iid, :ad, TRUE) RETURNING id",
                {"iid": isletme_id, "ad": "Merkez Şube"}
            )
            sube_id = row["id"]
            results["steps"].append(f"Şube oluşturuldu: ID={sube_id}")

        # 3. Kullanıcılar
        users_data = [
            ("demo_admin", "DemoAdmin123!", "admin"),
            ("kasiyer1", "Kasiyer123!", "operator"),
            ("mutfak1", "Mutfak1234!", "mutfak"),
            ("garson1", "Garson12345!", "garson"),
        ]
        for username, password, role in users_data:
            eu = await db.fetch_one("SELECT id FROM users WHERE username = :u", {"u": username})
            if not eu:
                hashed = hash_password(password)
                await db.execute(
                    "INSERT INTO users (username, sifre_hash, role, tenant_id, aktif) VALUES (:u, :h, :r, :tid, TRUE)",
                    {"u": username, "h": hashed, "r": role, "tid": isletme_id}
                )
            # Şube izni
            await db.execute(
                "INSERT INTO user_sube_izinleri (username, sube_id) VALUES (:u, :sid) ON CONFLICT DO NOTHING",
                {"u": username, "sid": sube_id}
            )
        results["steps"].append("4 kullanıcı oluşturuldu")

        # 4. Menü
        menu_ids = {}
        for item in MENU_ITEMS:
            em = await db.fetch_one("SELECT id FROM menu WHERE sube_id = :sid AND ad = :ad", {"sid": sube_id, "ad": item["ad"]})
            if em:
                menu_ids[item["ad"]] = em["id"]
            else:
                row = await db.fetch_one(
                    "INSERT INTO menu (sube_id, ad, fiyat, kategori, aktif, aciklama) VALUES (:sid, :ad, :fiyat, :kat, TRUE, :acik) RETURNING id",
                    {"sid": sube_id, "ad": item["ad"], "fiyat": item["fiyat"], "kat": item["kategori"], "acik": item.get("aciklama")}
                )
                menu_ids[item["ad"]] = row["id"]
        results["steps"].append(f"{len(MENU_ITEMS)} menü ürünü eklendi")

        # Varyasyonlar
        varyasyonlar = [
            ("Latte", [("Küçük", -10, 1), ("Orta", 0, 2), ("Büyük", 15, 3)]),
            ("Cappuccino", [("Küçük", -10, 1), ("Orta", 0, 2), ("Büyük", 15, 3)]),
            ("Mocha", [("Vanilyalı", 5, 1), ("Karamelli", 5, 2), ("Fındıklı", 10, 3)]),
            ("Ice Latte", [("Küçük", -10, 1), ("Orta", 0, 2), ("Büyük", 15, 3)]),
            ("Cheesecake", [("Çilekli", 15, 1), ("Çikolatalı", 15, 2), ("Sade", 0, 3)]),
        ]
        vc = 0
        for menu_ad, vars_list in varyasyonlar:
            if menu_ad in menu_ids:
                for var_ad, ek_fiyat, sira in vars_list:
                    await db.execute(
                        "INSERT INTO menu_varyasyonlar (menu_id, ad, ek_fiyat, sira, aktif) VALUES (:mid, :ad, :ef, :s, TRUE) ON CONFLICT (menu_id, ad) DO NOTHING",
                        {"mid": menu_ids[menu_ad], "ad": var_ad, "ef": ek_fiyat, "s": sira}
                    )
                    vc += 1
        results["steps"].append(f"{vc} varyasyon eklendi")

        # 5. Masalar
        for masa_adi in MASA_ADLARI:
            em = await db.fetch_one("SELECT id FROM masalar WHERE sube_id = :sid AND masa_adi = :m", {"sid": sube_id, "m": masa_adi})
            if not em:
                kap = 6 if "VIP" in masa_adi else (2 if "Bar" in masa_adi else 4)
                qr = f"MAS_{sube_id}_{uuid.uuid4().hex[:12].upper()}"
                await db.execute(
                    "INSERT INTO masalar (sube_id, masa_adi, qr_code, kapasite, durum) VALUES (:sid, :m, :qr, :kap, 'bos')",
                    {"sid": sube_id, "m": masa_adi, "qr": qr, "kap": kap}
                )
        results["steps"].append(f"{len(MASA_ADLARI)} masa eklendi")

        # 6. Stok
        for item in STOK_ITEMS:
            es = await db.fetch_one("SELECT id FROM stok_kalemleri WHERE sube_id = :sid AND ad = :ad", {"sid": sube_id, "ad": item["ad"]})
            if not es:
                await db.execute(
                    "INSERT INTO stok_kalemleri (sube_id, ad, kategori, birim, mevcut, min, alis_fiyat) VALUES (:sid, :ad, :kat, :bir, :mev, :mn, :af)",
                    {"sid": sube_id, "ad": item["ad"], "kat": item["kategori"], "bir": item["birim"], "mev": item["mevcut"], "mn": item["min"], "af": item["alis_fiyat"]}
                )
        results["steps"].append(f"{len(STOK_ITEMS)} stok kalemi eklendi")

        # 7. Geçmiş siparişler (son 14 gün)
        siparis_count = 0
        odeme_count = 0
        for day_offset in range(14, 0, -1):
            gun = now - timedelta(days=day_offset)
            gun_siparis = random.randint(15, 35) if gun.weekday() >= 5 else random.randint(8, 20)
            for _ in range(gun_siparis):
                saat = random.randint(8, 22)
                dakika = random.randint(0, 59)
                siparis_zamani = gun.replace(hour=saat, minute=dakika, second=random.randint(0, 59))
                masa = random.choice(MASA_ADLARI)
                secilen = random.sample(MENU_ITEMS, min(random.randint(1, 4), len(MENU_ITEMS)))
                sepet = []
                toplam = 0
                for urun in secilen:
                    adet = random.randint(1, 3)
                    sepet.append({"urun": urun["ad"], "adet": adet, "fiyat": urun["fiyat"]})
                    toplam += urun["fiyat"] * adet
                await db.execute(
                    "INSERT INTO siparisler (sube_id, masa, sepet, durum, tutar, created_at) VALUES (:sid, :m, :s, 'tamamlandi', :t, :ca)",
                    {"sid": sube_id, "m": masa, "s": json.dumps(sepet), "t": toplam, "ca": siparis_zamani}
                )
                siparis_count += 1
                yontem = random.choice(["nakit", "kredi_karti", "kredi_karti", "kredi_karti"])
                await db.execute(
                    "INSERT INTO odemeler (sube_id, masa, tutar, yontem, created_at) VALUES (:sid, :m, :t, :y, :ca)",
                    {"sid": sube_id, "m": masa, "t": toplam, "y": yontem, "ca": siparis_zamani + timedelta(minutes=random.randint(15, 60))}
                )
                odeme_count += 1

        # Bugün aktif siparişler
        for masa in random.sample(MASA_ADLARI, 4):
            secilen = random.sample(MENU_ITEMS, min(random.randint(1, 3), len(MENU_ITEMS)))
            sepet = []
            toplam = 0
            for urun in secilen:
                adet = random.randint(1, 2)
                sepet.append({"urun": urun["ad"], "adet": adet, "fiyat": urun["fiyat"]})
                toplam += urun["fiyat"] * adet
            durum = random.choice(["yeni", "hazirlaniyor"])
            await db.execute(
                "INSERT INTO siparisler (sube_id, masa, sepet, durum, tutar, created_at) VALUES (:sid, :m, :s, :d, :t, :ca)",
                {"sid": sube_id, "m": masa, "s": json.dumps(sepet), "d": durum, "t": toplam, "ca": now - timedelta(minutes=random.randint(5, 30))}
            )
            siparis_count += 1
        results["steps"].append(f"{siparis_count} sipariş + {odeme_count} ödeme oluşturuldu")

        # 8. Giderler
        for gider in GIDER_ITEMS:
            tarih = (now + timedelta(days=gider["gun_offset"])).strftime("%Y-%m-%d")
            eg = await db.fetch_one(
                "SELECT id FROM giderler WHERE sube_id = :sid AND aciklama = :ac AND tarih = :t",
                {"sid": sube_id, "ac": gider["aciklama"], "t": tarih}
            )
            if not eg:
                await db.execute(
                    "INSERT INTO giderler (sube_id, kategori, aciklama, tutar, tarih) VALUES (:sid, :kat, :ac, :tu, :ta)",
                    {"sid": sube_id, "kat": gider["kategori"], "ac": gider["aciklama"], "tu": gider["tutar"], "ta": tarih}
                )
        results["steps"].append(f"{len(GIDER_ITEMS)} gider eklendi")

        # 9. Abonelik
        es = await db.fetch_one("SELECT id FROM subscriptions WHERE isletme_id = :iid", {"iid": isletme_id})
        if not es:
            await db.execute(
                "INSERT INTO subscriptions (isletme_id, plan_type, status, max_subeler, max_kullanicilar, max_menu_items, ayllik_fiyat) VALUES (:iid, 'pro', 'active', 3, 10, 200, 999)",
                {"iid": isletme_id}
            )
            results["steps"].append("Pro plan abonelik oluşturuldu")
        else:
            results["steps"].append("Abonelik zaten mevcut")

        results["success"] = True
        results["isletme_id"] = isletme_id
        results["sube_id"] = sube_id
        results["credentials"] = {
            "admin": "demo_admin / DemoAdmin123!",
            "kasiyer": "kasiyer1 / Kasiyer123!",
            "mutfak": "mutfak1 / Mutfak1234!",
            "garson": "garson1 / Garson12345!",
        }
        return results

    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"Seed hatası: {str(e)}\n{traceback.format_exc()}")
