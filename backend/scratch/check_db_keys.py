
import asyncio
import os
import sys

# Ensure backend path is in sys.path
sys.path.append(os.getcwd())

from app.db.database import db

async def test():
    await db.connect()
    try:
        # Platform Settings
        rows = await db.fetch_all("SELECT key, value FROM platform_settings WHERE key LIKE '%openai%'")
        print("PLATFORM SETTINGS:")
        for r in rows:
            print(f"  {r['key']}: {'SET (NOT REVEALED)' if r['value'] else 'EMPTY'}")
            
        # Tenant Customizations
        rows = await db.fetch_all("SELECT isletme_id, openai_api_key, business_assistant_openai_api_key FROM tenant_customizations")
        print("\nTENANT CUSTOMIZATIONS:")
        for r in rows:
            print(f"  Tenant {r['isletme_id']}: GenKey={'SET' if r['openai_api_key'] else 'EMPTY'}, BIKey={'SET' if r['business_assistant_openai_api_key'] else 'EMPTY'}")
            
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
