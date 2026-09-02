"""
Admin Filter — faqat adminlar uchun handler

config.py dagi ADMIN_IDS ro'yxatiga qarab tekshiradi.
"""

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from typing import Union

from config import settings


class IsAdmin(BaseFilter):
    """Foydalanuvchi admin ekanligini tekshiruvchi filtr"""

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user_id = event.from_user.id if event.from_user else 0
        return user_id in settings.admin_ids
