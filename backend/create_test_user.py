"""Create test user for testing customer assistant."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import db
from app.core.security import hash_password


async def main():
    """Create test user."""
    try:
        print("[+] Connecting to database...")
        await db.connect()

        # Check if admin user exists
        existing = await db.fetch_one(
            "SELECT id FROM users WHERE username = :username",
            {"username": "admin"}
        )

        if existing:
            print("[!] Admin user already exists")
        else:
            # Create admin user
            password_hash = hash_password("admin123")
            await db.execute(
                """
                INSERT INTO users (username, sifre_hash, role, aktif)
                VALUES (:username, :sifre_hash, :role, TRUE)
                """,
                {
                    "username": "admin",
                    "sifre_hash": password_hash,
                    "role": "super_admin"
                }
            )
            print("[SUCCESS] Admin user created: username=admin, password=admin123")

        await db.disconnect()

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
