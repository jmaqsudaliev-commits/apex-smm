"""
Throttling Middleware — Spam himoyasi

Foydalanuvchilarning juda tez xabar yuborishini cheklaydi.
1M+ foydalanuvchi uchun muhim — botni himoya qiladi.
"""

import time
from typing import Callable, Dict, Any, Awaitable, MutableMapping
from collections import defaultdict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from config import settings


class ThrottlingMiddleware(BaseMiddleware):
    """Rate limiting middleware — foydalanuvchi tez-tez xabar yuborsa bloklaydi"""

    def __init__(self, rate: float = None):
        self.rate = rate or settings.throttle_rate
        self.user_timestamps: MutableMapping[int, float] = defaultdict(float)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Foydalanuvchini aniqlash
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if not user:
            return await handler(event, data)

        user_id = user.id
        current_time = time.monotonic()
        last_time = self.user_timestamps.get(user_id, 0)

        if current_time - last_time < self.rate:
            # Juda tez — javob bermaymiz
            if isinstance(event, CallbackQuery):
                await event.answer("⏳ Iltimos, biroz kuting...", show_alert=False)
            return  # Handlerni chaqirmaymiz

        self.user_timestamps[user_id] = current_time
        return await handler(event, data)
