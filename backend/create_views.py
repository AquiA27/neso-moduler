"""Create AI views in database."""

import asyncio
from pathlib import Path
from app.db.database import db


async def main():
    """Create all AI views."""
    await db.connect()

    views_dir = Path(__file__).parent / "app" / "db" / "views"
    view_files = [
        "vw_ai_menu_stock.sql",
        "vw_ai_active_sessions.sql",
        "vw_ai_sales_summary.sql"
    ]

    for view_file in view_files:
        view_path = views_dir / view_file
        if not view_path.exists():
            print(f"[!] View file not found: {view_file}")
            continue

        print(f"[+] Creating view: {view_file}")

        # Read SQL content
        sql_content = view_path.read_text(encoding="utf-8")

        # Split by semicolons and execute each statement separately
        statements = [s.strip() for s in sql_content.split(";") if s.strip()]

        for stmt in statements:
            if stmt:
                try:
                    await db.execute(stmt)
                    print(f"  [+] Executed statement successfully")
                except Exception as e:
                    print(f"  [ERROR] {e}")

    await db.disconnect()
    print("\n[SUCCESS] All views created!")


if __name__ == "__main__":
    asyncio.run(main())
