"""Test fuzzy matching for Menengiç."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.nlp.entity_extractor import get_entity_extractor
from app.services.embedding_service import get_embedding_service
from app.db.database import db


async def main():
    """Test fuzzy and semantic matching."""
    try:
        await db.connect()

        query = "menengiş kahvesi"
        print(f"[+] Testing query: '{query}'")

        # Test entity extraction
        extractor = get_entity_extractor()
        entities = extractor.extract(query)
        print(f"\n[+] Extracted entities:")
        print(f"  - Products: {entities.products}")
        print(f"  - Quantities: {entities.quantities}")

        # Test semantic search
        print("\n[+] Semantic search:")
        embedding_service = get_embedding_service()
        semantic_results = await embedding_service.search_similar(
            query_text=query,
            sube_id=2,
            limit=5,
            threshold=0.5
        )
        for r in semantic_results:
            print(f"  - {r['product_name']}: similarity={r['similarity']:.2f}")

        # Test fuzzy matching directly
        print("\n[+] Fuzzy matching against all products:")
        menu_items = await db.fetch_all(
            "SELECT id, ad FROM menu WHERE sube_id = 2 AND aktif = TRUE"
        )

        from rapidfuzz import fuzz
        for item in menu_items:
            score = fuzz.ratio(query.lower(), item['ad'].lower()) / 100
            if score > 0.5:
                print(f"  - {item['ad']}: fuzzy_score={score:.2f}")

        await db.disconnect()

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
