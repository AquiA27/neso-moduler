"""
Relax Cafe için ödeme kaydı oluştur
"""
import asyncio
from app.db.database import db
from datetime import datetime

async def create_relax_payment():
    await db.connect()
    
    try:
        # Relax Cafe'yi bul
        relax = await db.fetch_one(
            "SELECT id, ad FROM isletmeler WHERE ad ILIKE '%relax%'"
        )
        
        if not relax:
            print("Relax Cafe bulunamadı!")
            return
        
        relax_id = relax['id']
        print(f"Relax Cafe bulundu: ID={relax_id}, Ad={relax['ad']}")
        
        # Aboneliği bul
        subscription = await db.fetch_one(
            "SELECT id, ayllik_fiyat FROM subscriptions WHERE isletme_id = :id",
            {"id": relax_id}
        )
        
        if not subscription:
            print("Relax Cafe için abonelik bulunamadı!")
            return
        
        sub_id = subscription['id']
        ayllik_fiyat = subscription['ayllik_fiyat']
        print(f"Abonelik bulundu: ID={sub_id}, Aylık Fiyat={ayllik_fiyat}")
        
        # Mevcut ödeme kontrolü
        existing = await db.fetch_one(
            """
            SELECT id FROM payments 
            WHERE isletme_id = :id AND subscription_id = :sub_id
            ORDER BY created_at DESC LIMIT 1
            """,
            {"id": relax_id, "sub_id": sub_id}
        )
        
        if existing:
            print(f"Zaten bir ödeme kaydı var: ID={existing['id']}")
            # Ödeme detaylarını göster
            payment = await db.fetch_one(
                "SELECT * FROM payments WHERE id = :id",
                {"id": existing['id']}
            )
            print(f"Ödeme: {dict(payment)}")
        else:
            # Yeni ödeme kaydı oluştur
            payment = await db.fetch_one(
                """
                INSERT INTO payments (
                    isletme_id, subscription_id, tutar, odeme_turu, durum,
                    aciklama, odeme_tarihi
                )
                VALUES (
                    :isletme_id, :subscription_id, :tutar, :odeme_turu, :durum,
                    :aciklama, :odeme_tarihi
                )
                RETURNING id, isletme_id, subscription_id, tutar, odeme_turu, durum,
                          fatura_no, aciklama, odeme_tarihi, created_at, updated_at
                """,
                {
                    "isletme_id": relax_id,
                    "subscription_id": sub_id,
                    "tutar": ayllik_fiyat,
                    "odeme_turu": "odeme_sistemi",
                    "durum": "completed",
                    "aciklama": "Aylık abonelik ücreti",
                    "odeme_tarihi": datetime.utcnow(),
                }
            )
            print(f"Ödeme kaydı oluşturuldu: ID={payment['id']}, Tutar={payment['tutar']}")
        
    except Exception as e:
        print(f"Hata: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(create_relax_payment())

