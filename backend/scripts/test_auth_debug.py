#!/usr/bin/env python3
"""Debug authentication"""
import asyncio
import os
from databases import Database
from dotenv import load_dotenv
from app.core.security import verify_password

load_dotenv()

async def debug_auth():
    db_url = os.getenv("DATABASE_URL")
    db = Database(db_url)
    await db.connect()

    try:
        print("=" * 60)
        print("DEBUG: Testing admin login")
        print("=" * 60)

        # Fetch user
        user = await db.fetch_one(
            "SELECT id, username, sifre_hash, role, aktif FROM users WHERE username = :u",
            {"u": "admin"}
        )

        if not user:
            print("ERROR: User 'admin' not found in database!")
            return

        print(f"✓ User found:")
        print(f"  ID: {user['id']}")
        print(f"  Username: {user['username']}")
        print(f"  Role: {user['role']}")
        print(f"  Active: {user['aktif']}")
        print(f"  Has hash: {bool(user['sifre_hash'])}")
        print(f"  Hash length: {len(user['sifre_hash']) if user['sifre_hash'] else 0}")

        # Test password
        test_password = "admin123"
        print(f"\n✓ Testing password: '{test_password}'")

        result = verify_password(test_password, user['sifre_hash'])
        print(f"  Password verification: {result}")

        if result:
            print("\n✅ SUCCESS! Password is correct")
            print("   Login should work with:")
            print("   Username: admin")
            print("   Password: admin123")
        else:
            print("\n❌ FAILED! Password does not match")
            print("   Need to reset password")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(debug_auth())
