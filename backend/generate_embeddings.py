"""Generate embeddings for all menu items."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.embedding_service import get_embedding_service


async def main():
    """Generate embeddings for all menu items."""
    try:
        print("[+] Initializing embedding service...")
        service = get_embedding_service()

        # Get all subes
        from app.db.database import db
        await db.connect()

        subes = await db.fetch_all("SELECT id, ad FROM subeler WHERE aktif = TRUE")
        print(f"[+] Found {len(subes)} active branches")

        total_stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

        for sube in subes:
            sube_id = sube["id"]
            sube_name = sube["ad"]

            print(f"\n[+] Processing sube: {sube_name} (id={sube_id})")

            stats = await service.sync_menu_embeddings(sube_id=sube_id, force=False)

            print(f"  [+] Created: {stats['created']}")
            print(f"  [+] Updated: {stats['updated']}")
            print(f"  [+] Skipped: {stats['skipped']}")
            print(f"  [+] Errors: {stats['errors']}")

            for key in total_stats:
                total_stats[key] += stats[key]

        print(f"\n[SUCCESS] Total embeddings:")
        print(f"  Created: {total_stats['created']}")
        print(f"  Updated: {total_stats['updated']}")
        print(f"  Skipped: {total_stats['skipped']}")
        print(f"  Errors: {total_stats['errors']}")

        # Create vector index if enough data
        if total_stats['created'] + total_stats['updated'] >= 10:
            print("\n[+] Creating vector similarity index...")
            success = await service.create_vector_index()
            if success:
                print("[SUCCESS] Vector index created!")
            else:
                print("[!] Vector index creation skipped (need >=100 embeddings for optimal performance)")

        await db.disconnect()

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
