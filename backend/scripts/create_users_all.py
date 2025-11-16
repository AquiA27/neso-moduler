#!/usr/bin/env python3
"""Create all default users: admin, kasiyer, barista"""
import asyncio
import os
from databases import Database
from dotenv import load_dotenv
from app.core.security import hash_password

load_dotenv()

async def create_all_users():
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://neso:neso123@localhost:5432/neso")
    db = Database(db_url)
    await db.connect()

    try:
        users = [
            {"username": "super", "password": "super123", "role": "super_admin"},
            {"username": "admin", "password": "admin123", "role": "admin"},
            {"username": "kasiyer", "password": "kasiyer123", "role": "operator"},
            {"username": "barista", "password": "barista123", "role": "barista"},
        ]

        print("=" * 60)
        print("Creating users...")
        print("=" * 60)

        for user_info in users:
            username = user_info["username"]
            password = user_info["password"]
            role = user_info["role"]

            # Hash password
            hashed = hash_password(password)

            # Delete existing user if exists
            await db.execute('DELETE FROM users WHERE username = :u', {'u': username})
            print(f"Cleared existing user: {username}")

            # Create new user
            result = await db.fetch_one('''
                INSERT INTO users (username, sifre_hash, role, aktif)
                VALUES (:u, :h, :r, TRUE)
                RETURNING id, username, role
            ''', {'u': username, 'h': hashed, 'r': role})

            print(f"[OK] Created: {result['username']} (role: {result['role']})")

        print("\n" + "=" * 60)
        print("SUCCESS! All users created")
        print("=" * 60)
        print("\nGiriş Bilgileri:")
        print("-" * 60)
        for user_info in users:
            print(f"  {user_info['username']:12} / {user_info['password']:15} (role: {user_info['role']})")
        print("=" * 60)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(create_all_users())
