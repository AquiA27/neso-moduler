# backend/app/db/database.py
from databases import Database
from ..core.config import settings

# Ana DB (PostgreSQL)
db = Database(settings.DATABASE_URL, min_size=1, max_size=5)

# İsteğe bağlı ikinci DB (örn. ayrı menü DB'si kullanacaksan)
_menu_url = getattr(settings, "MENU_DATABASE_URL", None) or settings.DATABASE_URL
menu_db = Database(_menu_url, min_size=1, max_size=5)

async def connect_all():
    if not db.is_connected:
        await db.connect()
    if (menu_db is not db) and (not menu_db.is_connected):
        await menu_db.connect()

async def disconnect_all():
    if (menu_db is not db) and menu_db.is_connected:
        await menu_db.disconnect()
    if db.is_connected:
        await db.disconnect()
