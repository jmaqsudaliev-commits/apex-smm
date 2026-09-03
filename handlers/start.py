"""
Start Handler — /start buyrug'i va majburiy obuna tekshirish

Foydalanuvchini ro'yxatdan o'tkazadi va asosiy menyuni ko'rsatadi.
Referal tizimini qo'llab-quvvatlaydi (/start ref_CODE).
"""

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatMemberStatus
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.dao import UserDAO, SettingsDAO
from keyboards.reply import get_main_menu_kb
from keyboards.inline import get_subscription_kb

router = Router()


async def get_mandatory_channels(session: AsyncSession) -> list:
    """Majburiy obuna kanallarini olish (DB dan yoki config dan)"""
    db_channels = await SettingsDAO.get(session, "mandatory_channels", "")
    if db_channels.strip():
        return [ch.strip() for ch in db_channels.split(",") if ch.strip()]
    return settings.mandatory_channels


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    bot: Bot,
    state: FSMContext,
):
    """
    /start — Boshlash
    /start ref_CODE — Referal orqali boshlash
    """
    await state.clear()
    telegram_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username

    # Referal kodni olish
    referral_code = None
    if command.args and command.args.startswith("ref_"):
        referral_code = command.args[4:]

    # Foydalanuvchini ro'yxatdan o'tkazish yoki olish
    user, is_new = await UserDAO.get_or_create(
        session=session,
        telegram_id=telegram_id,
        full_name=full_name,
        username=username,
        referral_code_from=referral_code,
    )

    # Adminlarni obuna tekshiruvidan ozod qilish
    is_admin = telegram_id in settings.admin_ids or user.is_admin

    # Majburiy obuna tekshirish
    channels = await get_mandatory_channels(session)
    if channels and not is_admin:
        not_subscribed = []
        for channel in channels:
            if not channel:
                continue
            try:
                channel_id = channel if channel.startswith("-") else f"@{channel.replace('@', '')}"
                member = await bot.get_chat_member(
                    chat_id=channel_id, user_id=telegram_id
                )
                if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
                    not_subscribed.append(channel)
            except Exception:
                pass

        if not_subscribed:
            text = (
                f"👋 <b>Assalomu alaykum, {full_name}!</b>\n\n"
                f"Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'ling:\n\n"
            )
            for ch in not_subscribed:
                text += f"📢 @{ch.replace('@', '')}\n"
            text += "\n✅ Obuna bo'lgandan so'ng <b>Tekshirish</b> tugmasini bosing."

            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=get_subscription_kb(not_subscribed),
            )
            return

    # Xush kelibsiz xabari
    if is_new:
        welcome_text = (
            f"🎉 <b>Xush kelibsiz, {full_name}!</b>\n\n"
            f"🛒 Bu bot orqali siz quyidagi xizmatlardan foydalanishingiz mumkin:\n\n"
            f"📸 Instagram — followers, likes, views\n"
            f"🎵 TikTok — followers, likes, views\n"
            f"📺 YouTube — subscribers, views, likes\n"
            f"✈️ Telegram — members, views, reactions\n"
            f"⭐ Telegram Stars\n"
            f"💎 Telegram Premium\n"
            f"🖼 NFT & Collectibles\n"
            f"🎁 Sovg'alar\n"
            f"💠 TON Coin\n"
            f"💵 USDT\n\n"
            f"💰 Balansni to'ldirib, buyurtma bering!\n"
            f"📢 Yordam: @{settings.support_username}"
        )
    else:
        welcome_text = (
            f"👋 <b>Qaytib kelganingizdan xursandmiz, {full_name}!</b>\n\n"
            f"💰 Balans: <b>{int(user.balance):,} so'm</b>\n\n"
            f"Quyidagi menyudan tanlang 👇"
        )

    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(),
    )


@router.callback_query(F.data == "check_subscription")
async def check_subscription(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Majburiy obuna tekshirish tugmasi bosilganda"""
    telegram_id = callback.from_user.id

    channels = await get_mandatory_channels(session)
    if not channels:
        await callback.answer("✅ Obuna talab qilinmaydi!", show_alert=False)
        return

    not_subscribed = []
    for channel in channels:
        if not channel:
            continue
        try:
            channel_id = channel if channel.startswith("-") else f"@{channel.replace('@', '')}"
            member = await bot.get_chat_member(
                chat_id=channel_id, user_id=telegram_id
            )
            if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
                not_subscribed.append(channel)
        except Exception:
            pass

    if not_subscribed:
        await callback.answer(
            "❌ Siz hali barcha kanallarga obuna bo'lmadingiz!",
            show_alert=True,
        )
        return

    # Obuna tasdiqlandi — menyuni ko'rsatish
    user = await UserDAO.get_by_telegram_id(session, telegram_id)

    await callback.message.edit_text(
        f"✅ <b>Obuna tasdiqlandi!</b>\n\n"
        f"Botdan foydalanishingiz mumkin 👇",
        parse_mode="HTML",
    )

    welcome_text = (
        f"🎉 <b>Xush kelibsiz!</b>\n\n"
        f"Quyidagi menyudan tanlang 👇"
    )
    await callback.message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(),
    )
