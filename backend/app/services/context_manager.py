"""Conversation context storage for customer assistant."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

_CONTEXT_TTL = timedelta(hours=2)


@dataclass
class ConversationContext:
    conversation_id: str
    sube_id: Optional[int] = None
    masa: Optional[str] = None
    last_intent: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)
    extra: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.last_updated = datetime.utcnow()


class ContextManager:
    def __init__(self) -> None:
        self._store: Dict[str, ConversationContext] = {}
        self._lock = asyncio.Lock()

    async def get(self, conversation_id: str) -> ConversationContext:
        async with self._lock:
            ctx = self._store.get(conversation_id)
            if ctx and datetime.utcnow() - ctx.last_updated > _CONTEXT_TTL:
                self._store.pop(conversation_id, None)
                ctx = None
            if ctx is None:
                ctx = ConversationContext(conversation_id=conversation_id)
                self._store[conversation_id] = ctx
            ctx.touch()
            return ctx

    async def update(self, conversation_id: str, **kwargs: Any) -> ConversationContext:
        ctx = await self.get(conversation_id)
        for key, value in kwargs.items():
            if hasattr(ctx, key):
                setattr(ctx, key, value)
            else:
                ctx.extra[key] = value
        ctx.touch()
        return ctx

    async def set_last_intent(self, conversation_id: str, intent: Optional[str]) -> None:
        await self.update(conversation_id, last_intent=intent)


context_manager = ContextManager()



