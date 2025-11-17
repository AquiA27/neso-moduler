# backend/app/db/database.py
from databases import Database
from ..core.config import settings
import logging

logger = logging.getLogger(__name__)

# Ana DB (PostgreSQL)
# Cross-region latency için optimize edilmiş connection pool
# Daha fazla persistent connection = daha az connection overhead
# min_size max_size'tan küçük veya eşit olmalı (validasyon)
min_size = min(settings.DB_POOL_MIN_SIZE, settings.DB_POOL_MAX_SIZE)
max_size = max(settings.DB_POOL_MIN_SIZE, settings.DB_POOL_MAX_SIZE)

db = Database(
    settings.DATABASE_URL,
    min_size=min_size,
    max_size=max_size,
    # Command timeout - cross-region latency için artırıldı (saniye)
    command_timeout=settings.DB_COMMAND_TIMEOUT,
)

# İsteğe bağlı ikinci DB (örn. ayrı menü DB'si kullanacaksan)
_menu_url = getattr(settings, "MENU_DATABASE_URL", None) or settings.DATABASE_URL
menu_db = Database(
    _menu_url,
    min_size=min_size,
    max_size=max_size,
    command_timeout=settings.DB_COMMAND_TIMEOUT,
)

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
