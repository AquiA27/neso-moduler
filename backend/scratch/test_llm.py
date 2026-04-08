
import asyncio
import os
import sys

# Ensure backend path is in sys.path
sys.path.append(os.getcwd())

from app.llm.providers import get_llm_provider
from app.core.config import settings
from app.db.database import db

async def test():
    await db.connect()
    try:
        print(f"Settings API KEY: {settings.OPENAI_API_KEY[:10]}..." if settings.OPENAI_API_KEY else "Settings API KEY: None")
        print(f"LLM ENABLED: {settings.ASSISTANT_ENABLE_LLM}")
        
        # Test for a generic tenant or None
        provider = await get_llm_provider(tenant_id=None, assistant_type="business")
        print(f"Provider Type (None tenant): {type(provider).__name__}")
        
        # Check database for any tenant keys
        rows = await db.fetch_all("SELECT isletme_id, openai_api_key, business_assistant_openai_api_key FROM tenant_customizations")
        print(f"Found {len(rows)} tenant customization rows.")
        for r in rows:
            print(f"Tenant {r['isletme_id']}: GenKey={'SET' if r['openai_api_key'] else 'EMPTY'}, BIKey={'SET' if r['business_assistant_openai_api_key'] else 'EMPTY'}")
            
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
