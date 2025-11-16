"""Add sample menu items for embedding testing."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import db


SAMPLE_MENU = [
    # Sıcak İçecekler
    ("Türk Kahvesi", "Sıcak İçecekler", 15.00, "Geleneksel türk kahvesi"),
    ("Filtre Kahve", "Sıcak İçecekler", 12.00, "Filtre yöntemiyle hazırlanmış kahve"),
    ("Americano", "Sıcak İçecekler", 18.00, "Espresso üzerine sıcak su"),
    ("Latte", "Sıcak İçecekler", 22.00, "Espresso ve süt"),
    ("Cappuccino", "Sıcak İçecekler", 20.00, "Espresso, süt ve köpük"),
    ("Sıcak Çikolata", "Sıcak İçecekler", 25.00, "Sıcak çikolata içeceği"),
    ("Menengiç Kahvesi", "Sıcak İçecekler", 18.00, "Antep fıstığından yapılmış kahve"),

    # Bitki Çayları
    ("Ihlamur", "Bitki Çayları", 10.00, "Doğal ıhlamur çayı"),
    ("Papatya Çayı", "Bitki Çayları", 10.00, "Rahatlatıcı papatya çayı"),
    ("Zencefil Çayı", "Bitki Çayları", 12.00, "Taze zencefil çayı"),
    ("Yeşil Çay", "Bitki Çayları", 10.00, "Yeşil çay"),

    # Soğuk İçecekler
    ("Frappuccino", "Soğuk İçecekler", 28.00, "Buzlu kahve içeceği"),
    ("Ice Latte", "Soğuk İçecekler", 24.00, "Buzlu latte"),
    ("Ice Americano", "Soğuk İçecekler", 20.00, "Buzlu americano"),
    ("Limonata", "Soğuk İçecekler", 15.00, "Taze limonata"),

    # Tatlılar
    ("Cheesecake", "Tatlılar", 35.00, "San sebastian cheesecake"),
    ("Tiramisu", "Tatlılar", 40.00, "İtalyan tiramisu"),
    ("Waffle", "Tatlılar", 30.00, "Belçika waffle"),
    ("Çikolatalı Kek", "Tatlılar", 25.00, "Çikolatalı kek dilimi"),
    ("Sütlaç", "Tatlılar", 18.00, "Fırın sütlaç"),
    ("Baklava", "Tatlılar", 45.00, "Antep fıstıklı baklava"),

    # Tuzlular
    ("Tost", "Tuzlular", 25.00, "Kaşarlı tost"),
    ("Sandviç", "Tuzlular", 30.00, "Karışık sandviç"),
    ("Börek", "Tuzlular", 20.00, "Peynirli börek"),

    # Çorbalar
    ("Mercimek Çorbası", "Çorbalar", 20.00, "Kırmızı mercimek çorbası"),
]


async def main():
    """Add sample menu items."""
    try:
        print("[+] Connecting to database...")
        await db.connect()

        # Get or create isletme
        isletme_result = await db.fetch_one("SELECT id FROM isletmeler LIMIT 1")
        if not isletme_result:
            print("[!] No isletme found, creating default...")
            await db.execute(
                """
                INSERT INTO isletmeler (ad, aktif)
                VALUES ('Demo İşletme', TRUE)
                """
            )
            isletme_result = await db.fetch_one("SELECT id FROM isletmeler LIMIT 1")

        isletme_id = isletme_result["id"]

        # Get or create sube
        sube_result = await db.fetch_one("SELECT id FROM subeler WHERE isletme_id = :isletme_id LIMIT 1", {"isletme_id": isletme_id})
        if not sube_result:
            print("[!] No sube found, creating default sube...")
            await db.execute(
                """
                INSERT INTO subeler (ad, isletme_id, aktif)
                VALUES ('Ana Şube', :isletme_id, TRUE)
                """,
                {"isletme_id": isletme_id}
            )
            sube_result = await db.fetch_one("SELECT id FROM subeler WHERE isletme_id = :isletme_id LIMIT 1", {"isletme_id": isletme_id})

        sube_id = sube_result["id"]
        print(f"[+] Using sube_id: {sube_id}")

        print(f"[+] Adding {len(SAMPLE_MENU)} sample menu items...")

        for ad, kategori, fiyat, aciklama in SAMPLE_MENU:
            await db.execute(
                """
                INSERT INTO menu (sube_id, ad, kategori, fiyat, aciklama, aktif)
                VALUES (:sube_id, :ad, :kategori, :fiyat, :aciklama, TRUE)
                ON CONFLICT DO NOTHING
                """,
                {
                    "sube_id": sube_id,
                    "ad": ad,
                    "kategori": kategori,
                    "fiyat": fiyat,
                    "aciklama": aciklama
                }
            )

        # Count items
        count = await db.fetch_one(
            "SELECT COUNT(*) as cnt FROM menu WHERE sube_id = :sube_id",
            {"sube_id": sube_id}
        )

        print(f"[SUCCESS] {count['cnt']} menu items in database!")
        print("\n[NEXT] Run embeddings generation script")

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.disconnect()
        print("[+] Database connection closed.")


if __name__ == "__main__":
    asyncio.run(main())
