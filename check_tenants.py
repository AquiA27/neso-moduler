import asyncio
import asyncpg

async def check_tenants():
    conn = await asyncpg.connect(
        host='localhost',
        port=5433,
        user='neso',
        password='neso123',
        database='neso'
    )

    print("\n=== İşletmeler (isletmeler tablosu) ===")
    rows = await conn.fetch("""
        SELECT id, ad, aktif, created_at
        FROM isletmeler
        ORDER BY id
    """)

    for row in rows:
        print(f"ID: {row['id']}, Ad: {row['ad']}, Aktif: {row['aktif']}, Oluşturulma: {row['created_at']}")

    print(f"\nToplam {len(rows)} işletme bulundu.")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_tenants())
