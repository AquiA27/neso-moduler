"""Check users in database."""
import asyncio
import asyncpg


async def main():
    conn = await asyncpg.connect('postgresql://neso:neso123@localhost:5433/neso')
    rows = await conn.fetch('SELECT username, role FROM users LIMIT 10')
    print('Users in database:')
    for r in rows:
        print(f'  - {r["username"]} (role: {r["role"]})')
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
