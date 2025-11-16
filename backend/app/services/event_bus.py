"""Basit event bus ve Postgres LISTEN/NOTIFY entegrasyonu için iskelet."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable, Dict, List

import asyncpg

from ..core.config import settings
from .cache import invalidate_ai_cache_sync

logger = logging.getLogger(__name__)

EventHandler = Callable[[str, Dict[str, object]], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._lock = asyncio.Lock()
        self._listener_task: asyncio.Task | None = None
        self._handler = invalidate_ai_cache_sync

    async def start_listener(self) -> None:
        if self._listener_task and not self._listener_task.done():
            return
        self._listener_task = asyncio.create_task(self._listen_loop())

    async def _listen_loop(self) -> None:
        try:
            conn = await asyncpg.connect(settings.DATABASE_URL)
            await conn.add_listener("ai_cache", self._notify_cb)
            logger.info("Event bus LISTEN başladı: ai_cache")
            while True:
                await asyncio.sleep(3600)
        except Exception:
            logger.exception("Event bus listener hata verdi; 10sn sonra yeniden denenecek")
            await asyncio.sleep(10)
            await self._listen_loop()

    async def _notify_cb(self, connection: asyncpg.Connection, pid: int, channel: str, payload: str) -> None:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Event payload JSON parse edilemedi: %s", payload)
            data = {"raw": payload}
        await self.emit(channel, data)

    async def register(self, channel: str, handler: EventHandler) -> None:
        async with self._lock:
            self._handlers.setdefault(channel, []).append(handler)
            logger.info("Event handler kaydedildi: channel=%s handler=%s", channel, handler)

    async def emit(self, channel: str, payload: Dict[str, object]) -> None:
        handlers = list(self._handlers.get(channel, []))
        if not handlers:
            return

        for handler in handlers:
            try:
                await handler(channel, payload)
            except Exception:  # pragma: no cover - loglar yeterli
                logger.exception("Event handler hata verdi: channel=%s handler=%s", channel, handler)

    async def _handle_cache_event(self, channel: str, payload: Dict[str, object]) -> None:
        logger.info("AI cache invalidation bildirimi: channel=%s payload=%s", channel, payload)
        self._handler()


event_bus = EventBus()
