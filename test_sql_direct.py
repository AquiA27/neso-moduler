import asyncio
import asyncpg

async def test_sql():
    conn = await asyncpg.connect(
        host='localhost',
        port=5433,
        user='neso',
        password='neso123',
        database='neso'
    )

    # Superadmin endpoint'indeki sorguyu aynen test edelim
    query = """
    SELECT id, ad, vergi_no, telefon, aktif
    FROM isletmeler
    ORDER BY id DESC
    LIMIT 50 OFFSET 0
    """

    print("=== SQL Sorgu Sonucu (Superadmin endpoint ile aynı sorgu) ===")
    rows = await conn.fetch(query)

    print(f"Toplam {len(rows)} kayıt bulundu:\n")
    for row in rows:
        print(f"ID: {row['id']}, Ad: {row['ad']}, Aktif: {row['aktif']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(test_sql())
