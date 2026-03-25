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

import contextvars

# Global Context Variable for Tenant Isolation
current_tenant_id = contextvars.ContextVar('current_tenant_id', default=None)

class TenantAwareDatabase(Database):
    """
    Transparently injects Postgres Row-Level Security (RLS) setting.
    When current_tenant_id is set, all queries are wrapped in a transaction
    with SET LOCAL app.current_tenant = X to prevent cross-tenant data leaks.
    """
    async def fetch_all(self, query: str, values=None, **kwargs):
        tid = current_tenant_id.get()
        if tid is not None:
            async with self.transaction():
                await super().execute(f"SET LOCAL app.current_tenant = '{tid}'")
                return await super().fetch_all(query, values, **kwargs)
        return await super().fetch_all(query, values, **kwargs)

    async def fetch_one(self, query: str, values=None, **kwargs):
        tid = current_tenant_id.get()
        if tid is not None:
            async with self.transaction():
                await super().execute(f"SET LOCAL app.current_tenant = '{tid}'")
                return await super().fetch_one(query, values, **kwargs)
        return await super().fetch_one(query, values, **kwargs)

    async def execute(self, query: str, values=None, **kwargs):
        tid = current_tenant_id.get()
        if tid is not None:
            async with self.transaction():
                await super().execute(f"SET LOCAL app.current_tenant = '{tid}'")
                return await super().execute(query, values, **kwargs)
        return await super().execute(query, values, **kwargs)

db = TenantAwareDatabase(
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
