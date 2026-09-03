"""
Subscription Middleware — Majburiy obuna tekshirish

Foydalanuvchi majburiy kanallarga obuna bo'lmasdan botdan foydalana olmaydi.
Admin lar va /start buyrug'i bundan mustasno.
"""

from typing import Callable, Dict, Any, Awaitable, List

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.enums import ChatMemberStatus

from config import settings
from keyboards.inline import get_subscription_kb


class SubscriptionMiddleware(BaseMiddleware):
    """Majburiy obuna tekshirish middleware"""

    ALLOWED_CALLBACKS = {"check_subscription"}

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
            # /start buyrug'ini o'tkazib yuborish
            if event.text and event.text.startswith("/start"):
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            # check_subscription callback ni o'tkazib yuborish
            if event.data in self.ALLOWED_CALLBACKS:
                return await handler(event, data)

        if not user:
            return await handler(event, data)

        # Adminlarni o'tkazib yuborish (.env va bazadagi barcha adminlar)
        if user.id in settings.admin_ids:
            return await handler(event, data)

        session = data.get("session")

        # Ban (bloklash) tekshiruvi
        if session:
            from database.dao import UserDAO
            try:
                db_user = await UserDAO.get_by_telegram_id(session, user.id)
                if db_user and db_user.is_banned:
                    ban_msg = (
                        "🚫 <b>Sizning hisobingiz bot ma'murlari tomonidan bloklangan!</b>\n\n"
                        "Savollaringiz bo'lsa, qo'llab-quvvatlash xizmati bilan bog'laning."
                    )
                    if isinstance(event, Message):
                        await event.answer(ban_msg, parse_mode="HTML")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("🚫 Siz botdan bloklangansiz!", show_alert=True)
                    return
            except Exception:
                pass
        if session:
            from database.dao import UserDAO
            try:
                if await UserDAO.is_admin(session, user.id):
                    return await handler(event, data)
            except Exception:
                pass

        # Kanallarni olish (Avval DB dan, bo'lmasa config dan)
        channels_list = []
        session = data.get("session")
        if session:
            from database.dao import SettingsDAO
            db_channels = await SettingsDAO.get(session, "mandatory_channels", "")
            if db_channels.strip():
                channels_list = [ch.strip() for ch in db_channels.split(",") if ch.strip()]

        if not channels_list and settings.mandatory_channels:
            channels_list = settings.mandatory_channels

        # Majburiy kanallar bo'lmasa — o'tkazib yuborish
        if not channels_list:
            return await handler(event, data)

        # Obuna tekshirish
        bot: Bot = data["bot"]
        not_subscribed = []

        for channel in channels_list:
            if not channel:
                continue
            try:
                channel_id = channel if channel.startswith("-") else f"@{channel.replace('@', '')}"
                member = await bot.get_chat_member(chat_id=channel_id, user_id=user.id)
                if member.status in (
                    ChatMemberStatus.LEFT,
                    ChatMemberStatus.KICKED,
                ):
                    not_subscribed.append(channel)
            except Exception:
                # Kanalga kira olmasa — o'tkazib yuborish
                pass

        if not_subscribed:
            text = (
                "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
            )
            for ch in not_subscribed:
                text += f"📢 @{ch.replace('@', '')}\n"
            text += "\n✅ Obuna bo'lgandan so'ng <b>Tekshirish</b> tugmasini bosing."

            kb = get_subscription_kb(not_subscribed)

            if isinstance(event, Message):
                await event.answer(text, parse_mode="HTML", reply_markup=kb)
            elif isinstance(event, CallbackQuery):
                await event.message.answer(text, parse_mode="HTML", reply_markup=kb)
                await event.answer()
            return  # Handlerni chaqirmaymiz

        return await handler(event, data)
