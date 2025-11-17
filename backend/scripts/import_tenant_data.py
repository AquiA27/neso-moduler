#!/usr/bin/env python3
"""
Export edilen tenant (işletme) verilerini production'a import et
"""
import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from databases import Database

load_dotenv()

# Production Database URL (Render'dan al)
PROD_DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://neso:neso123@localhost:5432/neso")


async def import_tenant_data(json_file: str, isletme_id: int, sube_id: int = None):
    """
    Export edilen verileri production'a import et
    
    Args:
        json_file: Export edilmiş JSON dosyası yolu
        isletme_id: Production'daki işletme ID
        sube_id: Production'daki şube ID (None ise ilk şubeyi kullan)
    """
    db = Database(PROD_DB_URL)
    await db.connect()
    
    try:
        # 1. JSON dosyasını oku
        with open(json_file, "r", encoding="utf-8") as f:
            export_data = json.load(f)
        
        print(f"✅ Export dosyası okundu: {json_file}")
        print(f"   İşletme: {export_data['isletme']['ad']}")
        print(f"   Şube sayısı: {len(export_data['subeler'])}")
        
        # 2. İşletme kontrolü
        isletme = await db.fetch_one(
            "SELECT id, ad FROM isletmeler WHERE id = :id",
            {"id": isletme_id}
        )
        
        if not isletme:
            print(f"❌ İşletme bulunamadı (ID: {isletme_id})")
            return False
        
        print(f"✅ İşletme bulundu: {isletme['ad']} (ID: {isletme_id})")
        
        # 3. Şube kontrolü
        if sube_id:
            sube = await db.fetch_one(
                "SELECT id, ad FROM subeler WHERE isletme_id = :iid AND id = :sid",
                {"iid": isletme_id, "sid": sube_id}
            )
        else:
            sube = await db.fetch_one(
                "SELECT id, ad FROM subeler WHERE isletme_id = :iid ORDER BY id LIMIT 1",
                {"iid": isletme_id}
            )
        
        if not sube:
            print(f"❌ Şube bulunamadı (İşletme ID: {isletme_id}, Şube ID: {sube_id})")
            return False
        
        prod_sube_id = sube["id"]
        print(f"✅ Şube bulundu: {sube['ad']} (ID: {prod_sube_id})")
        
        # 4. İlk şube verilerini import et (şimdilik)
        if len(export_data["subeler"]) > 0:
            sube_data = export_data["subeler"][0]
            
            print(f"\n📦 Veriler import ediliyor...")
            
            # Menu items import
            menu_count = 0
            for menu_item in sube_data.get("menu", []):
                try:
                    # Menu item ekle
                    menu_row = await db.fetch_one(
                        """
                        INSERT INTO menu (sube_id, ad, fiyat, kategori, aktif, aciklama, gorsel_url)
                        VALUES (:sid, :ad, :fiyat, :kategori, :aktif, :aciklama, :gorsel_url)
                        ON CONFLICT DO NOTHING
                        RETURNING id
                        """,
                        {
                            "sid": prod_sube_id,
                            "ad": menu_item["ad"],
                            "fiyat": menu_item.get("fiyat", 0.0),
                            "kategori": menu_item.get("kategori"),
                            "aktif": menu_item.get("aktif", True),
                            "aciklama": menu_item.get("aciklama"),
                            "gorsel_url": menu_item.get("gorsel_url"),
                        }
                    )
                    
                    if menu_row:
                        menu_id = menu_row["id"]
                        menu_count += 1
                        
                        # Varyasyonları ekle
                        for var in menu_item.get("varyasyonlar", []):
                            await db.execute(
                                """
                                INSERT INTO menu_varyasyonlar (menu_id, ad, ek_fiyat, sira, aktif)
                                VALUES (:menu_id, :ad, :ek_fiyat, :sira, :aktif)
                                ON CONFLICT DO NOTHING
                                """,
                                {
                                    "menu_id": menu_id,
                                    "ad": var["ad"],
                                    "ek_fiyat": var.get("ek_fiyat", 0.0),
                                    "sira": var.get("sira", 0),
                                    "aktif": var.get("aktif", True),
                                }
                            )
                
                except Exception as e:
                    print(f"  ⚠️ Menu item hatası ({menu_item.get('ad')}): {e}")
            
            print(f"  ✅ Menu: {menu_count} ürün import edildi")
            
            # Stok items import
            stok_count = 0
            for stok_item in sube_data.get("stok", []):
                try:
                    await db.execute(
                        """
                        INSERT INTO stok_kalemleri (sube_id, ad, kategori, birim, mevcut, min, alis_fiyat)
                        VALUES (:sid, :ad, :kategori, :birim, :mevcut, :min, :alis_fiyat)
                        ON CONFLICT (sube_id, ad) DO UPDATE
                           SET kategori = EXCLUDED.kategori,
                               birim = EXCLUDED.birim,
                               mevcut = EXCLUDED.mevcut,
                               min = EXCLUDED.min,
                               alis_fiyat = EXCLUDED.alis_fiyat
                        """,
                        {
                            "sid": prod_sube_id,
                            "ad": stok_item["ad"],
                            "kategori": stok_item.get("kategori"),
                            "birim": stok_item.get("birim"),
                            "mevcut": stok_item.get("mevcut", 0.0),
                            "min": stok_item.get("min", 0.0),
                            "alis_fiyat": stok_item.get("alis_fiyat", 0.0),
                        }
                    )
                    stok_count += 1
                except Exception as e:
                    print(f"  ⚠️ Stok item hatası ({stok_item.get('ad')}): {e}")
            
            print(f"  ✅ Stok: {stok_count} kalem import edildi")
            
            # Reçeteler import
            recete_count = 0
            for recete in sube_data.get("receteler", []):
                try:
                    await db.execute(
                        """
                        INSERT INTO receteler (sube_id, urun, stok, miktar, birim)
                        VALUES (:sid, :urun, :stok, :miktar, :birim)
                        ON CONFLICT (sube_id, urun, stok) DO UPDATE
                           SET miktar = EXCLUDED.miktar,
                               birim = EXCLUDED.birim
                        """,
                        {
                            "sid": prod_sube_id,
                            "urun": recete["urun"],
                            "stok": recete["stok"],
                            "miktar": recete.get("miktar", 0.0),
                            "birim": recete.get("birim"),
                        }
                    )
                    recete_count += 1
                except Exception as e:
                    print(f"  ⚠️ Reçete hatası ({recete.get('urun')}): {e}")
            
            print(f"  ✅ Reçete: {recete_count} reçete import edildi")
            
            # Masalar import
            masa_count = 0
            for masa in sube_data.get("masalar", []):
                try:
                    await db.execute(
                        """
                        INSERT INTO masalar (sube_id, masa_adi, qr_code, durum, kapasite, pozisyon_x, pozisyon_y)
                        VALUES (:sid, :masa_adi, :qr_code, :durum, :kapasite, :pozisyon_x, :pozisyon_y)
                        ON CONFLICT (sube_id, masa_adi) DO UPDATE
                           SET qr_code = EXCLUDED.qr_code,
                               durum = EXCLUDED.durum,
                               kapasite = EXCLUDED.kapasite,
                               pozisyon_x = EXCLUDED.pozisyon_x,
                               pozisyon_y = EXCLUDED.pozisyon_y
                        """,
                        {
                            "sid": prod_sube_id,
                            "masa_adi": masa["masa_adi"],
                            "qr_code": masa.get("qr_code"),
                            "durum": masa.get("durum", "bos"),
                            "kapasite": masa.get("kapasite", 4),
                            "pozisyon_x": masa.get("pozisyon_x"),
                            "pozisyon_y": masa.get("pozisyon_y"),
                        }
                    )
                    masa_count += 1
                except Exception as e:
                    print(f"  ⚠️ Masa hatası ({masa.get('masa_adi')}): {e}")
            
            print(f"  ✅ Masa: {masa_count} masa import edildi")
            
            print(f"\n✅ Import tamamlandı!")
            return True
        else:
            print("❌ Export dosyasında şube verisi yok")
            return False
        
    except Exception as e:
        print(f"❌ Hata: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await db.disconnect()


async def main():
    import sys
    
    if len(sys.argv) < 3:
        print("Kullanım: python import_tenant_data.py <json_file> <isletme_id> [sube_id]")
        print("\nÖrnek:")
        print("  python import_tenant_data.py exports/fistik_kafe.json 1")
        print("  python import_tenant_data.py exports/fistik_kafe.json 1 2")
        sys.exit(1)
    
    json_file = sys.argv[1]
    isletme_id = int(sys.argv[2])
    sube_id = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else None
    
    await import_tenant_data(json_file, isletme_id, sube_id)


if __name__ == "__main__":
    asyncio.run(main())

