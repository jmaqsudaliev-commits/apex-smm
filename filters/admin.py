from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from typing import Union, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.dao import UserDAO


class IsAdmin(BaseFilter):
    """Foydalanuvchi admin ekanligini tekshiruvchi filtr"""

    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        session: Optional[AsyncSession] = None,
    ) -> bool:
        user = event.from_user
        if not user:
            return False

        user_id = user.id

        # 1. Asosiy super adminlar (.env dan)
        if user_id in settings.admin_ids:
            return True

        # 2. Bazadan admin huquqini tekshirish
        if session:
            return await UserDAO.is_admin(session, user_id)

        # Agar session berilmagan bo'lsa
        from database.engine import async_session
        async with async_session() as sess:
            return await UserDAO.is_admin(sess, user_id)
