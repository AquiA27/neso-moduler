"""
Neso Modüler - Demo Veri Seed Script
=====================================
Yarınki satış tanıtımı için gerçekçi bir kafe/restoran verisi oluşturur.

Kullanım:
  cd backend
  python seed_demo.py
"""

import asyncio
import os
import sys
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Backend modüllerini import edebilmek için
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://neso:neso123@localhost:5433/neso")

import asyncpg

# ===== KONFİGÜRASYON =====
DEMO_ISLETME_ADI = "Fıstık Cafe & Bistro"
DEMO_SUBE_ADI = "Merkez Şube"
DEMO_ADMIN_USER = "demo_admin"
DEMO_ADMIN_PASS = "DemoAdmin123!"  # Güçlü şifre (production policy)
DEMO_OPERATOR_USER = "kasiyer1"
DEMO_OPERATOR_PASS = "Kasiyer123!"
DEMO_MUTFAK_USER = "mutfak1"
DEMO_MUTFAK_PASS = "Mutfak1234!"
DEMO_GARSON_USER = "garson1"
DEMO_GARSON_PASS = "Garson12345!"

# ===== MENÜ VERİSİ =====
MENU_ITEMS = [
    # Sıcak İçecekler
    {"ad": "Türk Kahvesi", "fiyat": 55, "kategori": "Sıcak İçecekler", "aciklama": "Geleneksel köpüklü Türk kahvesi"},
    {"ad": "Espresso", "fiyat": 50, "kategori": "Sıcak İçecekler", "aciklama": "Yoğun İtalyan espresso"},
    {"ad": "Americano", "fiyat": 60, "kategori": "Sıcak İçecekler", "aciklama": "Espresso + sıcak su"},
    {"ad": "Latte", "fiyat": 75, "kategori": "Sıcak İçecekler", "aciklama": "Espresso + buharla ısıtılmış süt"},
    {"ad": "Cappuccino", "fiyat": 75, "kategori": "Sıcak İçecekler", "aciklama": "Espresso + süt köpüğü"},
    {"ad": "Mocha", "fiyat": 85, "kategori": "Sıcak İçecekler", "aciklama": "Espresso + çikolata + süt"},
    {"ad": "Çay (Çaydanlık)", "fiyat": 40, "kategori": "Sıcak İçecekler", "aciklama": "2 kişilik demlik çay"},
    {"ad": "Sıcak Çikolata", "fiyat": 70, "kategori": "Sıcak İçecekler", "aciklama": "Belçika çikolatalı"},

    # Soğuk İçecekler
    {"ad": "Ice Latte", "fiyat": 85, "kategori": "Soğuk İçecekler", "aciklama": "Buzlu latte"},
    {"ad": "Frappe", "fiyat": 90, "kategori": "Soğuk İçecekler", "aciklama": "Buzlu karışık kahve"},
    {"ad": "Limonata", "fiyat": 60, "kategori": "Soğuk İçecekler", "aciklama": "Taze sıkılmış limonata"},
    {"ad": "Smoothie (Mango)", "fiyat": 95, "kategori": "Soğuk İçecekler", "aciklama": "Taze mangolu smoothie"},
    {"ad": "Soğuk Çay", "fiyat": 50, "kategori": "Soğuk İçecekler", "aciklama": "Şeftali aromalı"},
    {"ad": "Ayran", "fiyat": 35, "kategori": "Soğuk İçecekler", "aciklama": "Geleneksel ev yapımı ayran"},

    # Kahvaltı
    {"ad": "Serpme Kahvaltı (2 Kişilik)", "fiyat": 450, "kategori": "Kahvaltı", "aciklama": "Zengin serpme kahvaltı tabağı"},
    {"ad": "Sahanda Yumurta", "fiyat": 90, "kategori": "Kahvaltı", "aciklama": "Tereyağında sahanda yumurta"},
    {"ad": "Menemen", "fiyat": 95, "kategori": "Kahvaltı", "aciklama": "Sebzeli menemen"},

    # Yemekler
    {"ad": "Tavuk Sote", "fiyat": 180, "kategori": "Yemekler", "aciklama": "Sebzeli tavuk sote + pilav"},
    {"ad": "Köfte Izgara", "fiyat": 200, "kategori": "Yemekler", "aciklama": "El yapımı ızgara köfte + patates"},
    {"ad": "Makarna Bolonez", "fiyat": 160, "kategori": "Yemekler", "aciklama": "Kıymalı bolonez soslu makarna"},
    {"ad": "Tavuk Wrap", "fiyat": 150, "kategori": "Yemekler", "aciklama": "Izgara tavuklu wrap"},
    {"ad": "Caesar Salata", "fiyat": 140, "kategori": "Yemekler", "aciklama": "Tavuklu Caesar salata"},

    # Tatlılar
    {"ad": "Cheesecake", "fiyat": 110, "kategori": "Tatlılar", "aciklama": "New York usulü cheesecake"},
    {"ad": "Brownie", "fiyat": 90, "kategori": "Tatlılar", "aciklama": "Çikolatalı brownie + dondurma"},
    {"ad": "San Sebastian", "fiyat": 120, "kategori": "Tatlılar", "aciklama": "San Sebastian cheesecake"},
    {"ad": "Sufle", "fiyat": 100, "kategori": "Tatlılar", "aciklama": "Sıcak çikolatalı sufle"},
    {"ad": "Tiramisu", "fiyat": 110, "kategori": "Tatlılar", "aciklama": "İtalyan tiramisu"},
]

# ===== STOK VERİSİ =====
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
    {"ad": "Mango (Dondurulmuş)", "kategori": "Meyve", "birim": "kg", "mevcut": 3, "min": 1, "alis_fiyat": 200},
    {"ad": "Limon", "kategori": "Meyve", "birim": "kg", "mevcut": 5, "min": 2, "alis_fiyat": 50},
    {"ad": "Peçete", "kategori": "Sarf Malzeme", "birim": "paket", "mevcut": 50, "min": 10, "alis_fiyat": 15},
    {"ad": "Bardak (Karton)", "kategori": "Sarf Malzeme", "birim": "adet", "mevcut": 200, "min": 50, "alis_fiyat": 3.5},
]

# ===== GİDER VERİSİ =====
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

# ===== MASA ADLARI =====
MASA_ADLARI = [
    "Masa 1", "Masa 2", "Masa 3", "Masa 4", "Masa 5",
    "Masa 6", "Masa 7", "Masa 8", "Bahçe 1", "Bahçe 2",
    "VIP 1", "Bar 1",
]


async def main():
    # Database URL - Render PostgreSQL (External - dışarıdan erişim)
    # Internal URL'de "-a" son eki var, External'da yok
    conn_str = os.getenv(
        "SEED_DATABASE_URL",
        "postgresql://neso_prod_user:zi1U5obfDlZXB142XElIQGM0DVDhTBJq@dpg-d4cu6r3uibrs73852mo0-a.frankfurt-postgres.render.com:5432/neso_prod"
    )
    
    print("=" * 60)
    print("🚀 NESO MODÜLER - Demo Veri Seed Script")
    print("=" * 60)
    print(f"Veritabanı: {conn_str.split('@')[1] if '@' in conn_str else conn_str}")
    print()

    import ssl as _ssl
    ssl_ctx = _ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = _ssl.CERT_NONE
    
    conn = await asyncpg.connect(conn_str, ssl=ssl_ctx, timeout=30)
    
    try:
        # ============================================
        # 1. DEMO İŞLETME OLUŞTUR
        # ============================================
        print("📦 1/8 - İşletme oluşturuluyor...")
        
        # Mevcut demo işletmeyi kontrol et
        existing = await conn.fetchrow(
            "SELECT id FROM isletmeler WHERE ad = $1", DEMO_ISLETME_ADI
        )
        if existing:
            isletme_id = existing["id"]
            print(f"   ⚡ Mevcut işletme bulundu: ID={isletme_id}")
        else:
            row = await conn.fetchrow(
                "INSERT INTO isletmeler (ad, telefon, aktif) VALUES ($1, $2, TRUE) RETURNING id",
                DEMO_ISLETME_ADI, "0532 555 12 34"
            )
            isletme_id = row["id"]
            print(f"   ✅ İşletme oluşturuldu: ID={isletme_id}")

        # ============================================
        # 2. ŞUBE OLUŞTUR
        # ============================================
        print("🏪 2/8 - Şube oluşturuluyor...")
        
        existing_sube = await conn.fetchrow(
            "SELECT id FROM subeler WHERE isletme_id = $1 AND ad = $2",
            isletme_id, DEMO_SUBE_ADI
        )
        if existing_sube:
            sube_id = existing_sube["id"]
            print(f"   ⚡ Mevcut şube bulundu: ID={sube_id}")
        else:
            row = await conn.fetchrow(
                "INSERT INTO subeler (isletme_id, ad, aktif) VALUES ($1, $2, TRUE) RETURNING id",
                isletme_id, DEMO_SUBE_ADI
            )
            sube_id = row["id"]
            print(f"   ✅ Şube oluşturuldu: ID={sube_id}")

        # ============================================
        # 3. KULLANICILAR OLUŞTUR
        # ============================================
        print("👥 3/8 - Kullanıcılar oluşturuluyor...")
        
        import bcrypt
        
        users = [
            (DEMO_ADMIN_USER, DEMO_ADMIN_PASS, "admin"),
            (DEMO_OPERATOR_USER, DEMO_OPERATOR_PASS, "operator"),
            (DEMO_MUTFAK_USER, DEMO_MUTFAK_PASS, "mutfak"),
            (DEMO_GARSON_USER, DEMO_GARSON_PASS, "garson"),
        ]
        
        for username, password, role in users:
            existing_user = await conn.fetchrow(
                "SELECT id FROM users WHERE username = $1", username
            )
            if existing_user:
                print(f"   ⚡ Kullanıcı mevcut: {username} ({role})")
                user_id = existing_user["id"]
            else:
                hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
                row = await conn.fetchrow(
                    "INSERT INTO users (username, sifre_hash, role, tenant_id, aktif) VALUES ($1, $2, $3, $4, TRUE) RETURNING id",
                    username, hashed, role, isletme_id
                )
                user_id = row["id"]
                print(f"   ✅ Kullanıcı: {username} ({role}) - Şifre: {password}")
            
            # Şube izni ver
            await conn.execute(
                "INSERT INTO user_sube_izinleri (username, sube_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                username, sube_id
            )

        # ============================================
        # 4. MENÜ ÖĞELERİ OLUŞTUR
        # ============================================
        print("🍽️  4/8 - Menü oluşturuluyor...")
        
        menu_ids = {}
        for item in MENU_ITEMS:
            existing_menu = await conn.fetchrow(
                "SELECT id FROM menu WHERE sube_id = $1 AND ad = $2",
                sube_id, item["ad"]
            )
            if existing_menu:
                menu_ids[item["ad"]] = existing_menu["id"]
            else:
                row = await conn.fetchrow(
                    """INSERT INTO menu (sube_id, ad, fiyat, kategori, aktif, aciklama) 
                       VALUES ($1, $2, $3, $4, TRUE, $5) RETURNING id""",
                    sube_id, item["ad"], item["fiyat"], item["kategori"], item.get("aciklama")
                )
                menu_ids[item["ad"]] = row["id"]
        
        print(f"   ✅ {len(MENU_ITEMS)} menü ürünü eklendi")
        
        # Varyasyonlar ekle
        varyasyonlar = [
            ("Latte", [("Küçük", -10, 1), ("Orta", 0, 2), ("Büyük", 15, 3)]),
            ("Cappuccino", [("Küçük", -10, 1), ("Orta", 0, 2), ("Büyük", 15, 3)]),
            ("Mocha", [("Vanilyalı", 5, 1), ("Karamelli", 5, 2), ("Fındıklı", 10, 3)]),
            ("Ice Latte", [("Küçük", -10, 1), ("Orta", 0, 2), ("Büyük", 15, 3)]),
            ("Cheesecake", [("Çilekli", 15, 1), ("Çikolatalı", 15, 2), ("Sade", 0, 3)]),
        ]
        var_count = 0
        for menu_ad, vars in varyasyonlar:
            if menu_ad in menu_ids:
                for var_ad, ek_fiyat, sira in vars:
                    await conn.execute(
                        """INSERT INTO menu_varyasyonlar (menu_id, ad, ek_fiyat, sira, aktif) 
                           VALUES ($1, $2, $3, $4, TRUE) ON CONFLICT (menu_id, ad) DO NOTHING""",
                        menu_ids[menu_ad], var_ad, ek_fiyat, sira
                    )
                    var_count += 1
        print(f"   ✅ {var_count} varyasyon eklendi")

        # ============================================
        # 5. MASALAR OLUŞTUR
        # ============================================
        print("🪑 5/8 - Masalar oluşturuluyor...")
        
        for masa_adi in MASA_ADLARI:
            existing_masa = await conn.fetchrow(
                "SELECT id FROM masalar WHERE sube_id = $1 AND masa_adi = $2",
                sube_id, masa_adi
            )
            if not existing_masa:
                kapasite = 6 if "VIP" in masa_adi else (2 if "Bar" in masa_adi else 4)
                qr_code = f"MAS_{sube_id}_{uuid.uuid4().hex[:12].upper()}"
                await conn.execute(
                    """INSERT INTO masalar (sube_id, masa_adi, qr_code, kapasite, durum) 
                       VALUES ($1, $2, $3, $4, 'bos')""",
                    sube_id, masa_adi, qr_code, kapasite
                )
        print(f"   ✅ {len(MASA_ADLARI)} masa eklendi")

        # ============================================
        # 6. STOK KALEMLERİ OLUŞTUR
        # ============================================
        print("📦 6/8 - Stok kalemleri oluşturuluyor...")
        
        for item in STOK_ITEMS:
            existing_stok = await conn.fetchrow(
                "SELECT id FROM stok_kalemleri WHERE sube_id = $1 AND ad = $2",
                sube_id, item["ad"]
            )
            if not existing_stok:
                await conn.execute(
                    """INSERT INTO stok_kalemleri (sube_id, ad, kategori, birim, mevcut, min, alis_fiyat) 
                       VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                    sube_id, item["ad"], item["kategori"], item["birim"],
                    item["mevcut"], item["min"], item["alis_fiyat"]
                )
        print(f"   ✅ {len(STOK_ITEMS)} stok kalemi eklendi")

        # ============================================
        # 7. GEÇMİŞ SİPARİŞLER OLUŞTUR (Son 14 gün)
        # ============================================
        print("📋 7/8 - Geçmiş siparişler ve ödemeler oluşturuluyor...")
        
        now = datetime.now(timezone.utc)
        siparis_count = 0
        odeme_count = 0
        
        # Son 14 gün için sipariş oluştur
        for day_offset in range(14, 0, -1):
            gun = now - timedelta(days=day_offset)
            
            # Gün bazında sipariş sayısı (hafta sonu daha yoğun)
            if gun.weekday() >= 5:  # Cumartesi-Pazar
                siparis_sayisi = random.randint(25, 40)
            else:
                siparis_sayisi = random.randint(12, 25)
            
            for _ in range(siparis_sayisi):
                # Rastgele saat (08:00 - 23:00 arası)
                saat = random.randint(8, 22)
                dakika = random.randint(0, 59)
                siparis_zamani = gun.replace(hour=saat, minute=dakika, second=random.randint(0, 59))
                
                # Rastgele masa
                masa = random.choice(MASA_ADLARI)
                
                # Rastgele sepet (1-4 ürün)
                urun_sayisi = random.randint(1, 4)
                secilen_urunler = random.sample(MENU_ITEMS, min(urun_sayisi, len(MENU_ITEMS)))
                
                sepet = []
                toplam = 0
                for urun in secilen_urunler:
                    adet = random.randint(1, 3)
                    sepet.append({
                        "urun": urun["ad"],
                        "adet": adet,
                        "fiyat": urun["fiyat"]
                    })
                    toplam += urun["fiyat"] * adet
                
                # Sipariş ekle (tamamlanmış)
                await conn.execute(
                    """INSERT INTO siparisler (sube_id, masa, sepet, durum, tutar, created_at) 
                       VALUES ($1, $2, $3, 'tamamlandi', $4, $5)""",
                    sube_id, masa, json.dumps(sepet), toplam, siparis_zamani
                )
                siparis_count += 1
                
                # Ödeme ekle
                yontem = random.choice(["nakit", "kredi_karti", "kredi_karti", "kredi_karti"])  # %75 kart
                await conn.execute(
                    """INSERT INTO odemeler (sube_id, masa, tutar, yontem, created_at) 
                       VALUES ($1, $2, $3, $4, $5)""",
                    sube_id, masa, toplam, yontem, siparis_zamani + timedelta(minutes=random.randint(15, 60))
                )
                odeme_count += 1
        
        # Bugün için de birkaç aktif sipariş ekle
        aktif_masalar = random.sample(MASA_ADLARI, 4)
        for masa in aktif_masalar:
            urun_sayisi = random.randint(1, 3)
            secilen_urunler = random.sample(MENU_ITEMS, min(urun_sayisi, len(MENU_ITEMS)))
            sepet = []
            toplam = 0
            for urun in secilen_urunler:
                adet = random.randint(1, 2)
                sepet.append({"urun": urun["ad"], "adet": adet, "fiyat": urun["fiyat"]})
                toplam += urun["fiyat"] * adet
            
            durum = random.choice(["yeni", "hazirlaniyor"])
            await conn.execute(
                """INSERT INTO siparisler (sube_id, masa, sepet, durum, tutar, created_at) 
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                sube_id, masa, json.dumps(sepet), durum, toplam, now - timedelta(minutes=random.randint(5, 30))
            )
            siparis_count += 1
        
        print(f"   ✅ {siparis_count} sipariş oluşturuldu (14 gün + bugün aktif)")
        print(f"   ✅ {odeme_count} ödeme kaydı oluşturuldu")

        # ============================================
        # 8. GİDERLER OLUŞTUR
        # ============================================
        print("💰 8/8 - Giderler oluşturuluyor...")
        
        for gider in GIDER_ITEMS:
            tarih = (now + timedelta(days=gider["gun_offset"])).date()
            existing_gider = await conn.fetchrow(
                "SELECT id FROM giderler WHERE sube_id = $1 AND aciklama = $2 AND tarih = $3",
                sube_id, gider["aciklama"], tarih
            )
            if not existing_gider:
                await conn.execute(
                    """INSERT INTO giderler (sube_id, kategori, aciklama, tutar, tarih) 
                       VALUES ($1, $2, $3, $4, $5)""",
                    sube_id, gider["kategori"], gider["aciklama"], gider["tutar"], tarih
                )
        print(f"   ✅ {len(GIDER_ITEMS)} gider kaydı eklendi")

        # ============================================
        # ABONELİK OLUŞTUR
        # ============================================
        print("📋 Abonelik oluşturuluyor...")
        existing_sub = await conn.fetchrow(
            "SELECT id FROM subscriptions WHERE isletme_id = $1", isletme_id
        )
        if not existing_sub:
            await conn.execute(
                """INSERT INTO subscriptions (isletme_id, plan_type, status, max_subeler, max_kullanicilar, max_menu_items, ayllik_fiyat)
                   VALUES ($1, 'pro', 'active', 3, 10, 200, 999)""",
                isletme_id
            )
            print("   ✅ Pro plan abonelik oluşturuldu")
        else:
            print("   ⚡ Abonelik zaten mevcut")

        # ============================================
        # SONUÇ
        # ============================================
        print()
        print("=" * 60)
        print("🎉 Demo verisi başarıyla oluşturuldu!")
        print("=" * 60)
        print()
        print("📌 GİRİŞ BİLGİLERİ:")
        print(f"   Admin  : {DEMO_ADMIN_USER} / {DEMO_ADMIN_PASS}")
        print(f"   Kasiyer: {DEMO_OPERATOR_USER} / {DEMO_OPERATOR_PASS}")
        print(f"   Mutfak : {DEMO_MUTFAK_USER} / {DEMO_MUTFAK_PASS}")
        print(f"   Garson : {DEMO_GARSON_USER} / {DEMO_GARSON_PASS}")
        print()
        print("📊 OLUŞTURULAN VERİLER:")
        print(f"   İşletme  : {DEMO_ISLETME_ADI} (ID: {isletme_id})")
        print(f"   Şube     : {DEMO_SUBE_ADI} (ID: {sube_id})")
        print(f"   Menü     : {len(MENU_ITEMS)} ürün + varyasyonlar")
        print(f"   Masalar  : {len(MASA_ADLARI)} masa")
        print(f"   Stok     : {len(STOK_ITEMS)} kalem")
        print(f"   Siparişler: {siparis_count} (son 14 gün)")
        print(f"   Ödemeler : {odeme_count} kayıt")
        print(f"   Giderler : {len(GIDER_ITEMS)} kayıt")
        print()
        print("🔑 TANITIM İÇİN:")
        print(f"   1. '{DEMO_ADMIN_USER}' ile giriş yapın")
        print(f"   2. Dashboard'da son 14 günlük verileri görün")
        print(f"   3. Menü, Kasa, Mutfak, Raporlar sayfalarını gezin")
        print(f"   4. AI Asistana 'Bugün en çok ne sattık?' diye sorun")
        print()

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
