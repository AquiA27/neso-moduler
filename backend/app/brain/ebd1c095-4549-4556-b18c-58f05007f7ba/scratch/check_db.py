import asyncio
import os
import sys
import json
sys.path.append('backend')
from app.db.database import db

async def check_recipe():
    await db.connect()
    try:
        rows = await db.fetch_all("SELECT * FROM receteler WHERE LOWER(urun) LIKE '%adana%'")
        print('RECIPES:', json.dumps([dict(r) for r in rows], indent=2, default=str))
        
        stok_rows = await db.fetch_all("SELECT * FROM stok_kalemleri WHERE LOWER(ad) LIKE '%kuzu%' OR LOWER(ad) LIKE '%et%'")
        print('STOCKS:', json.dumps([dict(r) for r in stok_rows], indent=2, default=str))
        
        # Check sales
        sales_rows = await db.fetch_all("SELECT * FROM siparisler WHERE durum = 'odendi'")
        print('SALES:', json.dumps([dict(r) for r in sales_rows], indent=2, default=str))
        
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_recipe())
