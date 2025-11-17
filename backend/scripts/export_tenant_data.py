#!/usr/bin/env python3
"""
Local'deki tenant (işletme) verilerini export et (menu, stok, reçete, masalar)
"""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from databases import Database

load_dotenv()

# Database URL
DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://neso:neso123@localhost:5432/neso")


async def export_tenant_data(isletme_ad: str, sube_id: int = None, output_file: str = None):
    """
    Tenant (işletme) verilerini export et
    
    Args:
        isletme_ad: İşletme adı (örn: "Fıstık Kafe")
        sube_id: Şube ID (None ise tüm şubeler)
        output_file: Output JSON dosyası yolu (None ise otomatik oluşturulur)
    """
    db = Database(DB_URL)
    await db.connect()
    
    try:
        # 1. İşletme bilgilerini al
        isletme = await db.fetch_one(
            """
            SELECT id, ad, vergi_no, telefon, aktif
            FROM isletmeler
            WHERE ad = :ad
            LIMIT 1
            """,
            {"ad": isletme_ad}
        )
        
        if not isletme:
            print(f"[!] Isletme bulunamadi: {isletme_ad}")
            return None
        
        isletme_dict = dict(isletme) if hasattr(isletme, 'keys') else isletme
        isletme_id = isletme_dict["id"]
        print(f"[OK] Isletme bulundu: {isletme_ad} (ID: {isletme_id})")
        
        # 2. Şubeleri al
        if sube_id:
            subeler = await db.fetch_all(
                """
                SELECT id, isletme_id, ad, adres, telefon, aktif
                FROM subeler
                WHERE isletme_id = :iid AND id = :sid
                """,
                {"iid": isletme_id, "sid": sube_id}
            )
        else:
            subeler = await db.fetch_all(
                """
                SELECT id, isletme_id, ad, adres, telefon, aktif
                FROM subeler
                WHERE isletme_id = :iid
                ORDER BY id
                """,
                {"iid": isletme_id}
            )
        
        if not subeler:
            print(f"[!] Sube bulunamadi (Isletme ID: {isletme_id})")
            return None
        
        print(f"[OK] {len(subeler)} sube bulundu")
        
        # 3. Export verilerini hazırla
        export_data = {
            "isletme": {
                "id": int(isletme_dict["id"]),
                "ad": isletme_dict["ad"],
                "vergi_no": isletme_dict.get("vergi_no") if isinstance(isletme_dict, dict) else None,
                "telefon": isletme_dict.get("telefon") if isinstance(isletme_dict, dict) else None,
                "aktif": bool(isletme_dict["aktif"]),
            },
            "subeler": [],
            "export_tarihi": datetime.now().isoformat(),
        }
        
        # 4. Her şube için verileri al
        for sube in subeler:
            sube_dict = dict(sube) if hasattr(sube, 'keys') else sube
            sid = sube_dict["id"]
            sube_ad = sube_dict["ad"]
            
            print(f"[*] Sube: {sube_ad} (ID: {sid}) - Veriler aliniyor...")
            
            # Menu items
            menu_items = await db.fetch_all(
                """
                SELECT id, ad, fiyat, kategori, aktif, aciklama, gorsel_url
                FROM menu
                WHERE sube_id = :sid
                ORDER BY kategori, ad
                """,
                {"sid": sid}
            )
            
            # Menu varyasyonları
            menu_varyasyonlar = await db.fetch_all(
                """
                SELECT mv.menu_id, mv.ad, mv.ek_fiyat, mv.sira, mv.aktif
                FROM menu_varyasyonlar mv
                JOIN menu m ON m.id = mv.menu_id
                WHERE m.sube_id = :sid
                ORDER BY mv.menu_id, mv.sira, mv.ad
                """,
                {"sid": sid}
            )
            
            # Stok kalemleri
            stok_items = await db.fetch_all(
                """
                SELECT id, ad, kategori, birim, mevcut, min, alis_fiyat
                FROM stok_kalemleri
                WHERE sube_id = :sid
                ORDER BY kategori, ad
                """,
                {"sid": sid}
            )
            
            # Reçeteler
            receteler = await db.fetch_all(
                """
                SELECT id, urun, stok, miktar, birim
                FROM receteler
                WHERE sube_id = :sid
                ORDER BY urun, stok
                """,
                {"sid": sid}
            )
            
            # Masalar
            masalar = await db.fetch_all(
                """
                SELECT id, masa_adi, qr_code, durum, kapasite, pozisyon_x, pozisyon_y
                FROM masalar
                WHERE sube_id = :sid
                ORDER BY masa_adi
                """,
                {"sid": sid}
            )
            
            # Varyasyonları menu item'lara ekle
            varyasyon_map = {}
            for var in menu_varyasyonlar:
                var_dict = dict(var) if hasattr(var, 'keys') else var
                menu_id = var_dict["menu_id"]
                if menu_id not in varyasyon_map:
                    varyasyon_map[menu_id] = []
                varyasyon_map[menu_id].append({
                    "ad": var_dict["ad"],
                    "ek_fiyat": float(var_dict["ek_fiyat"]) if var_dict.get("ek_fiyat") else 0.0,
                    "sira": int(var_dict["sira"]) if var_dict.get("sira") else 0,
                    "aktif": bool(var_dict["aktif"]),
                })
            
            # Sube verilerini hazırla
            sube_data = {
                "id": int(sid),
                "ad": sube_ad,
                "adres": sube_dict.get("adres") if isinstance(sube_dict, dict) else None,
                "telefon": sube_dict.get("telefon") if isinstance(sube_dict, dict) else None,
                "aktif": bool(sube_dict["aktif"]),
                "menu": [
                    {
                        "ad": dict(item)["ad"] if hasattr(item, 'keys') else item["ad"],
                        "fiyat": float(dict(item).get("fiyat") or 0) if hasattr(item, 'keys') else float(item.get("fiyat") or 0),
                        "kategori": dict(item).get("kategori") if hasattr(item, 'keys') else item.get("kategori"),
                        "aktif": bool(dict(item).get("aktif")) if hasattr(item, 'keys') else bool(item.get("aktif")),
                        "aciklama": dict(item).get("aciklama") if hasattr(item, 'keys') else item.get("aciklama"),
                        "gorsel_url": dict(item).get("gorsel_url") if hasattr(item, 'keys') else item.get("gorsel_url"),
                        "varyasyonlar": varyasyon_map.get(dict(item)["id"] if hasattr(item, 'keys') else item["id"], []),
                    }
                    for item in menu_items
                ],
                "stok": [
                    {
                        "ad": dict(item)["ad"] if hasattr(item, 'keys') else item["ad"],
                        "kategori": dict(item).get("kategori") if hasattr(item, 'keys') else item.get("kategori"),
                        "birim": dict(item).get("birim") if hasattr(item, 'keys') else item.get("birim"),
                        "mevcut": float(dict(item).get("mevcut") or 0) if hasattr(item, 'keys') else float(item.get("mevcut") or 0),
                        "min": float(dict(item).get("min") or 0) if hasattr(item, 'keys') else float(item.get("min") or 0),
                        "alis_fiyat": float(dict(item).get("alis_fiyat") or 0) if hasattr(item, 'keys') else float(item.get("alis_fiyat") or 0),
                    }
                    for item in stok_items
                ],
                "receteler": [
                    {
                        "urun": dict(item)["urun"] if hasattr(item, 'keys') else item["urun"],
                        "stok": dict(item)["stok"] if hasattr(item, 'keys') else item["stok"],
                        "miktar": float(dict(item).get("miktar") or 0) if hasattr(item, 'keys') else float(item.get("miktar") or 0),
                        "birim": dict(item).get("birim") if hasattr(item, 'keys') else item.get("birim"),
                    }
                    for item in receteler
                ],
                "masalar": [
                    {
                        "masa_adi": dict(item)["masa_adi"] if hasattr(item, 'keys') else item["masa_adi"],
                        "qr_code": dict(item).get("qr_code") if hasattr(item, 'keys') else item.get("qr_code"),
                        "durum": dict(item).get("durum", "bos") if hasattr(item, 'keys') else item.get("durum", "bos"),
                        "kapasite": int(dict(item).get("kapasite") or 4) if hasattr(item, 'keys') else int(item.get("kapasite") or 4),
                        "pozisyon_x": float(dict(item).get("pozisyon_x")) if hasattr(item, 'keys') and dict(item).get("pozisyon_x") else (float(item.get("pozisyon_x")) if item.get("pozisyon_x") else None),
                        "pozisyon_y": float(dict(item).get("pozisyon_y")) if hasattr(item, 'keys') and dict(item).get("pozisyon_y") else (float(item.get("pozisyon_y")) if item.get("pozisyon_y") else None),
                    }
                    for item in masalar
                ],
            }
            
            print(f"  [OK] Menu: {len(sube_data['menu'])} urun")
            print(f"  [OK] Stok: {len(sube_data['stok'])} kalem")
            print(f"  [OK] Recete: {len(sube_data['receteler'])} recete")
            print(f"  [OK] Masa: {len(sube_data['masalar'])} masa")
            
            export_data["subeler"].append(sube_data)
        
        # 5. JSON dosyasına kaydet
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = isletme_ad.lower().replace(" ", "_")
            output_file = f"exports/{safe_name}_{timestamp}.json"
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n[OK] Export tamamlandi: {output_path}")
        print(f"   [INFO] Toplam: {len(export_data['subeler'])} sube, {sum(len(s['menu']) for s in export_data['subeler'])} urun")
        
        return str(output_path)
        
    except Exception as e:
        print(f"[ERROR] Hata: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        await db.disconnect()


async def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Kullanım: python export_tenant_data.py <isletme_ad> [sube_id] [output_file]")
        print("\nÖrnek:")
        print("  python export_tenant_data.py 'Fıstık Kafe'")
        print("  python export_tenant_data.py 'Fıstık Kafe' 1")
        print("  python export_tenant_data.py 'Fıstık Kafe' 1 exports/fistik_kafe.json")
        sys.exit(1)
    
    isletme_ad = sys.argv[1]
    sube_id = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else None
    output_file = sys.argv[3] if len(sys.argv) > 3 else None
    
    await export_tenant_data(isletme_ad, sube_id, output_file)


if __name__ == "__main__":
    asyncio.run(main())

