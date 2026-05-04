
import asyncio
import os
from backend.app.db.database import db

async def check_settings():
    try:
        await db.connect()
        print("--- platform_settings ---")
        rows = await db.fetch_all("SELECT key, value FROM platform_settings")
        for r in rows:
            print(f"{r['key']}: {r['value']}")
        
        print("\n--- app_settings ---")
        rows = await db.fetch_all("SELECT key, value FROM app_settings")
        for r in rows:
            print(f"{r['key']}: {r['value']}")
        
        print("\n--- .env check ---")
        print(f"OPENAI_API_KEY: {'set' if os.getenv('OPENAI_API_KEY') else 'not set'}")
        print(f"GOOGLE_API_KEY: {'set' if os.getenv('GOOGLE_API_KEY') else 'not set'}")
        
        await db.disconnect()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_settings())
