"""
Notification Service — Admin guruhga buyurtma va to'lov bildirishnomalari

Yangi buyurtma yoki to'lov kelganda admin guruhga xabar yuboradi.
Admin guruhda ✅/❌ tugmalari bilan buyurtmani boshqarish mumkin.
"""

from aiogram import Bot
from loguru import logger

from config import settings
from database.models import Order, User, Payment
from keyboards.inline import get_admin_order_kb, get_admin_payment_kb
from utils.helpers import (
    format_order_for_group, format_price, format_number,
    get_payment_method_text, format_datetime,
)


from database.engine import async_session
from database.dao import SettingsDAO


async def get_order_group_id() -> int:
    """Buyurtmalar guruhi ID sini olish (avval DB dan, keyin config dan)"""
    try:
        async with async_session() as session:
            db_val = await SettingsDAO.get(session, "order_group_id", "0")
            if db_val and db_val.strip() not in ("0", ""):
                return int(db_val.strip())
    except Exception:
        pass
    return settings.order_group_id


async def notify_new_order(
    bot: Bot,
    order: Order,
    user: User,
    service_name: str = "",
) -> bool:
    """Yangi buyurtma haqida admin guruhga xabar yuborish"""
    group_id = await get_order_group_id()
    if not group_id:
        logger.warning("ORDER_GROUP_ID sozlanmagan — xabar yuborilmadi")
        return False

    try:
        text = format_order_for_group(order, user, service_name)
        kb = get_admin_order_kb(order.id)

        await bot.send_message(
            chat_id=group_id,
            text=text,
            parse_mode="HTML",
            reply_markup=kb,
        )
        logger.info(f"Buyurtma #{order.id} admin guruhga ({group_id}) yuborildi")
        return True
    except Exception as e:
        logger.error(f"Admin guruhga xabar yuborishda xato: {e}")
        return False


async def notify_new_payment(
    bot: Bot,
    payment: Payment,
    user: User,
) -> bool:
    """Yangi to'lov haqida admin guruhga xabar yuborish"""
    group_id = await get_order_group_id()
    if not group_id:
        logger.warning("ORDER_GROUP_ID sozlanmagan — xabar yuborilmadi")
        return False

    try:
        text = (
            f"💳 <b>YANGI TO'LOV #{payment.id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 Mijoz: {user.full_name}"
        )
        if user.username:
            text += f" (@{user.username})"
        text += (
            f"\n🆔 ID: <code>{user.telegram_id}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Summa: <b>{format_price(payment.amount)}</b>\n"
            f"💳 Usul: {get_payment_method_text(payment.payment_method.value)}\n"
            f"📅 {format_datetime(payment.created_at)}\n"
        )

        kb = get_admin_payment_kb(payment.id)

        # Agar screenshot bo'lsa — rasm bilan yuborish
        if payment.screenshot_file_id:
            await bot.send_photo(
                chat_id=group_id,
                photo=payment.screenshot_file_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            await bot.send_message(
                chat_id=group_id,
                text=text,
                parse_mode="HTML",
                reply_markup=kb,
            )

        logger.info(f"To'lov #{payment.id} admin guruhga ({group_id}) yuborildi")
        return True
    except Exception as e:
        logger.error(f"Admin guruhga to'lov xabari yuborishda xato: {e}")
        return False


async def notify_user(
    bot: Bot,
    user_telegram_id: int,
    text: str,
) -> bool:
    """Foydalanuvchiga shaxsiy xabar yuborish"""
    try:
        await bot.send_message(
            chat_id=user_telegram_id,
            text=text,
            parse_mode="HTML",
        )
        return True
    except Exception as e:
        logger.error(f"Foydalanuvchiga xabar yuborishda xato: {e}")
        return False
