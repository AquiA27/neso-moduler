"""Migrate data from old database to new database."""

import asyncio
import asyncpg


async def main():
    """Copy all data from old DB to new DB."""

    # Connect to both databases
    old_db = await asyncpg.connect(
        host="localhost",
        port=5432,
        user="neso",
        password="neso123",
        database="neso"
    )

    new_db = await asyncpg.connect(
        host="localhost",
        port=5433,
        user="neso",
        password="neso123",
        database="neso"
    )

    print("[+] Connected to both databases")

    # Tables to migrate (order matters for foreign keys)
    tables = [
        "isletmeler",
        "subeler",
        "users",
        "user_permissions",
        "user_sube_izinleri",
        "menu",
        "menu_varyasyonlar",
        "stok_kalemleri",
        "receteler",
        "masalar",
        "adisyons",
        "siparisler",
        "odemeler",
        "payments",
        "giderler",
        "iskonto_kayitlari",
        "app_settings",
        "audit_logs",
        "backup_history",
        "notification_history",
        "stock_alert_history",
        "push_subscriptions",
        "subscriptions",
        "tenant_customizations",
    ]

    try:
        for table in tables:
            print(f"\n[+] Migrating table: {table}")

            # Check if table exists in old DB
            exists = await old_db.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=$1)",
                table
            )

            if not exists:
                print(f"  [!] Table {table} does not exist in old DB, skipping")
                continue

            # Get count from old DB
            old_count = await old_db.fetchval(f"SELECT COUNT(*) FROM {table}")
            print(f"  [+] Old DB has {old_count} rows")

            if old_count == 0:
                print(f"  [!] No data to migrate")
                continue

            # Delete existing data from new DB (except menu_embeddings)
            if table != "menu_embeddings":
                await new_db.execute(f"DELETE FROM {table}")
                print(f"  [+] Cleared new DB table")

            # Get all data from old DB
            rows = await old_db.fetch(f"SELECT * FROM {table}")

            if not rows:
                continue

            # Get column names
            columns = list(rows[0].keys())
            cols_str = ", ".join(columns)
            placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))

            # Insert into new DB
            insert_query = f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders})"

            for row in rows:
                values = [row[col] for col in columns]
                try:
                    await new_db.execute(insert_query, *values)
                except Exception as e:
                    print(f"  [ERROR] Failed to insert row: {e}")
                    continue

            # Verify
            new_count = await new_db.fetchval(f"SELECT COUNT(*) FROM {table}")
            print(f"  [SUCCESS] Migrated {new_count} rows")

            # Reset sequences if table has an ID column
            if "id" in columns:
                try:
                    await new_db.execute(
                        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM {table}), 1), true)"
                    )
                    print(f"  [+] Reset sequence for {table}")
                except Exception as e:
                    print(f"  [!] Could not reset sequence: {e}")

        print("\n[SUCCESS] Data migration completed!")

    finally:
        await old_db.close()
        await new_db.close()


if __name__ == "__main__":
    asyncio.run(main())
