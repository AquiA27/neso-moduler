#!/usr/bin/env python3
"""
Local database'deki işletmeleri listele
"""
import asyncio
import os
from dotenv import load_dotenv
from databases import Database

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://neso:neso123@localhost:5432/neso")


async def list_tenants():
    """Local database'deki tüm işletmeleri listele"""
    db = Database(DB_URL)
    await db.connect()
    
    try:
        # İşletmeleri al
        isletmeler = await db.fetch_all(
            """
            SELECT id, ad, vergi_no, telefon, aktif, created_at
            FROM isletmeler
            ORDER BY id
            """
        )
        
        if not isletmeler:
            print("[!] Hic isletme bulunamadi")
            return
        
        print(f"[OK] {len(isletmeler)} isletme bulundu:\n")
        print(f"{'ID':<5} {'Ad':<30} {'Vergi No':<15} {'Telefon':<15} {'Durum':<10}")
        print("-" * 80)
        
        for isletme in isletmeler:
            isletme_dict = dict(isletme) if hasattr(isletme, 'keys') else isletme
            durum = "Aktif" if isletme_dict.get("aktif") else "Pasif"
            vergi_no = isletme_dict.get("vergi_no") or "-"
            telefon = isletme_dict.get("telefon") or "-"
            print(f"{isletme_dict['id']:<5} {isletme_dict['ad']:<30} {vergi_no:<15} {telefon:<15} {durum:<10}")
        
        print("\n[INFO] Export icin ornek komut:")
        if isletmeler:
            first_tenant = dict(isletmeler[0]) if hasattr(isletmeler[0], 'keys') else isletmeler[0]
            print(f'python scripts/export_tenant_data.py "{first_tenant["ad"]}"')
        
    except Exception as e:
        print(f"[ERROR] Hata: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(list_tenants())

