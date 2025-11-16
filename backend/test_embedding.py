"""Test embedding service to check OpenAI API."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.embedding_service import get_embedding_service
from app.db.database import db


async def main():
    """Test embedding generation."""
    try:
        print("[+] Testing embedding service...")
        service = get_embedding_service()

        if not service.client:
            print("[ERROR] OpenAI client not initialized! Check OPENAI_API_KEY")
            return

        print("[+] OpenAI client initialized successfully")

        # Test generating a query embedding
        print("[+] Generating test embedding for 'sıcak kahve'...")
        embedding = await service.embed("sıcak kahve")

        print(f"[SUCCESS] Generated embedding: {len(embedding)} dimensions")
        print(f"[+] First 5 values: {embedding[:5]}")

        # Test semantic search
        await db.connect()
        print("\n[+] Testing semantic search...")
        results = await service.search_similar(
            query_text="sıcak kahve",
            sube_id=2,
            limit=5,
            threshold=0.5
        )

        print(f"[+] Found {len(results)} matches:")
        for match in results:
            print(f"  - {match['product_name']}: similarity={match['similarity']:.2f}")

        await db.disconnect()

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
