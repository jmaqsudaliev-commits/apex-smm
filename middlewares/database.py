"""
Database Middleware — Har bir handlerga DB session beradi

Handler funksiyasiga `session` parametri sifatida uzatiladi.
"""

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from database.engine import async_session


class DatabaseMiddleware(BaseMiddleware):
    """Har bir update uchun DB session yaratadi va handlerga uzatadi"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with async_session() as session:
            data["session"] = session
            return await handler(event, data)
