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
    execution_time: str = "",
) -> bool:
    """Yangi buyurtma haqida admin guruhga va adminlarga xabar yuborish"""
    group_id = await get_order_group_id()
    text = format_order_for_group(order, user, service_name, execution_time)
    kb = get_admin_order_kb(order.id)
    sent_any = False

    # 1. Guruhga yuborish (agar sozlangan bo'lsa)
    if group_id and group_id != 0:
        try:
            await bot.send_message(
                chat_id=group_id,
                text=text,
                parse_mode="HTML",
                reply_markup=kb,
            )
            order_num = getattr(order, "order_number", None) or str(order.id)
            logger.info(f"Buyurtma #{order_num} admin guruhga ({group_id}) yuborildi")
            sent_any = True
        except Exception as e:
            logger.error(f"Admin guruhga ({group_id}) xabar yuborishda xato: {e}")

    # 2. Har bir adminga shaxsiy bot chatida ham yuborish
    for admin_id in settings.admin_ids:
        if admin_id != group_id:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
                sent_any = True
            except Exception as e:
                logger.error(f"Admin {admin_id} ga shaxsiy chatda xabar yuborishda xato: {e}")

    return sent_any


async def notify_new_payment(
    bot: Bot,
    payment: Payment,
    user: User,
) -> bool:
    """Yangi to'lov haqida admin guruhga va adminlarga xabar yuborish"""
    group_id = await get_order_group_id()

    try:
        text = (
            f"💳 <b>YANGI TO'LOV #{payment.id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 Mijoz: <b>{user.full_name}</b>"
        )
        if user.username:
            text += f" (@{user.username})"
        text += (
            f"\n🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Qo'shiladigan summa: <b>{format_price(payment.amount)}</b>\n"
            f"💳 To'lov usuli: <b>{get_payment_method_text(payment.payment_method.value)}</b>\n"
            f"📅 {format_datetime(payment.created_at)}\n"
        )

        kb = get_admin_payment_kb(payment.id)

        target_chat_ids = set()
        if group_id and group_id != 0:
            target_chat_ids.add(group_id)
        for adm_id in settings.admin_ids:
            target_chat_ids.add(adm_id)

        for target_id in target_chat_ids:
            try:
                if payment.screenshot_file_id:
                    await bot.send_photo(
                        chat_id=target_id,
                        photo=payment.screenshot_file_id,
                        caption=text,
                        parse_mode="HTML",
                        reply_markup=kb,
                    )
                else:
                    await bot.send_message(
                        chat_id=target_id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=kb,
                    )
            except Exception as e:
                logger.error(f"To'lov xabarini {target_id} ga yuborishda xato: {e}")

        logger.info(f"To'lov #{payment.id} yuborildi ({target_chat_ids})")
        return True
    except Exception as e:
        logger.error(f"Adminlarga to'lov xabari yuborishda umumiy xato: {e}")
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
