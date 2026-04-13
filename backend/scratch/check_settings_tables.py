import asyncio
import sys
import os

sys.path.insert(0, os.getcwd())
from backend.app.db.database import db

async def check_settings_tables():
    await db.connect()
    try:
        # Check for table existence
        tables = await db.fetch_all("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        table_names = [r['table_name'] for r in tables]
        print(f"Tables in public schema: {table_names}")
        
        if 'app_settings' in table_names:
            count = await db.fetch_one("SELECT count(*) as c FROM app_settings")
            print(f"app_settings count: {count['c']}")
             نمونه_data = await db.fetch_all("SELECT key FROM app_settings LIMIT 5")
            print(f"app_settings keys: {[r['key'] for r in نمونه_data]}")

        if 'platform_settings' in table_names:
            count = await db.fetch_one("SELECT count(*) as c FROM platform_settings")
            print(f"platform_settings count: {count['c']}")
            نمونه_data = await db.fetch_all("SELECT key FROM platform_settings LIMIT 5")
            print(f"platform_settings keys: {[r['key'] for r in نمونه_data]}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_settings_tables())
