"""Initialize database and run pgvector migration."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import db
from app.db.schema import create_tables


async def main():
    """Initialize database and prepare for pgvector migration."""
    try:
        print("[+] Connecting to database...")
        await db.connect()

        print("[+] Creating/updating tables...")
        await create_tables(db)

        print("[SUCCESS] Database schema created successfully!")
        print("\n[NEXT STEPS]")
        print("1. Run: cd backend")
        print("2. Run: alembic stamp initial_schema")
        print("3. Run: alembic stamp 2025_01_02_0000")
        print("4. Run: alembic upgrade head")
        print("\nThis will apply the pgvector migration.")

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.disconnect()
        print("\n[+] Database connection closed.")


if __name__ == "__main__":
    asyncio.run(main())
