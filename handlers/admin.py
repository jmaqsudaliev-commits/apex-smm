"""
Admin Handler — Admin panel va guruhdan buyurtma boshqarish

Funksiyalar:
- Statistika ko'rish
- Foydalanuvchilarni boshqarish (qidirish, ban, balans)
- Xizmatlarni boshqarish (qo'shish, o'chirish, narx o'zgartirish)
- To'lovlarni tasdiqlash/rad etish
- Buyurtmalarni bajarish (guruhdan)
- Broadcast (barcha foydalanuvchilarga xabar)
"""

import asyncio
import json
from decimal import Decimal

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, ChatMemberUpdated
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from config import settings
from database.dao import (
    UserDAO, CategoryDAO, ServiceDAO, OrderDAO, PaymentDAO, SettingsDAO,
)
from database.models import OrderStatus, PaymentStatus
from keyboards.reply import (
    get_admin_menu_kb, get_main_menu_kb, get_cancel_kb,
)
from keyboards.inline import (
    get_admin_services_kb, get_admin_service_list_kb,
    get_admin_service_edit_kb, get_admin_user_kb,
    get_broadcast_confirm_kb,
)
from filters.admin import IsAdmin
from states.states import AdminStates
from utils.helpers import (
    format_price, format_number, format_datetime,
    get_status_text, get_status_emoji, get_payment_method_text,
)
from services.notification import notify_user

router = Router()


# ============================================
# ADMIN PANEL KIRISH
# ============================================

@router.message(F.text == "/admin", IsAdmin())
async def admin_panel(message: Message):
    """Admin panel"""
    await message.answer(
        "🔐 <b>Admin Panel</b>\n\n"
        "Quyidagi menyudan tanlang 👇",
        parse_mode="HTML",
        reply_markup=get_admin_menu_kb(),
    )


# ============================================
# STATISTIKA
# ============================================

@router.message(F.text == "📊 Statistika", IsAdmin())
async def admin_stats(message: Message, session: AsyncSession):
    """Umumiy statistika"""
    total_users = await UserDAO.get_total_count(session)
    total_orders = await OrderDAO.get_total_count(session)
    total_revenue = await OrderDAO.get_total_revenue(session)
    total_services = await ServiceDAO.get_total_count(session)
    total_payments = await PaymentDAO.get_total_approved(session)

    text = (
        f"📊 <b>Umumiy Statistika</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Foydalanuvchilar: <b>{format_number(total_users)}</b>\n"
        f"📦 Buyurtmalar: <b>{format_number(total_orders)}</b>\n"
        f"🛍 Faol xizmatlar: <b>{format_number(total_services)}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Jami buyurtmalar summasi: <b>{format_price(total_revenue)}</b>\n"
        f"💳 Jami tasdiqlangan to'lovlar: <b>{format_price(total_payments)}</b>\n"
    )
    await message.answer(text, parse_mode="HTML")


# ============================================
# FOYDALANUVCHILAR BOSHQARUVI
# ============================================

@router.message(F.text == "👥 Foydalanuvchilar", IsAdmin())
async def admin_users(message: Message, session: AsyncSession):
    """Foydalanuvchilar boshqaruvi — to'liq ro'yxat va statistika"""
    await show_users_page(message, session, page=1)


async def show_users_page(message_or_callback_msg, session: AsyncSession, page: int = 1, is_edit: bool = False):
    """Foydalanuvchilar sahifasini chiqarish"""
    import math
    from keyboards.inline import get_admin_users_list_kb

    total_users = await UserDAO.get_total_count(session)
    banned_count = await UserDAO.get_banned_count(session)
    active_count = max(0, total_users - banned_count)
    page_size = 8
    total_pages = max(1, math.ceil(total_users / page_size))
    page = max(1, min(page, total_pages))

    users = await UserDAO.get_users_paginated(session, page=page, page_size=page_size)

    text = (
        f"👥 <b>Foydalanuvchilar boshqaruvi</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Jami foydalanuvchilar: <b>{format_number(total_users)} ta</b>\n"
        f"🟢 Faol: <b>{format_number(active_count)} ta</b>  |  🔴 Bloklangan: <b>{format_number(banned_count)} ta</b>\n"
        f"📄 Sahifa: <b>{page} / {total_pages}</b>\n\n"
        f"Foydalanuvchini boshqarish yoki bonus berish uchun uning ustiga bosing 👇"
    )
    kb = get_admin_users_list_kb(users, page, total_pages)

    if is_edit:
        try:
            await message_or_callback_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await message_or_callback_msg.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message_or_callback_msg.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("adm_users_page_"), IsAdmin())
async def admin_users_page_cb(callback: CallbackQuery, session: AsyncSession):
    """Sahifalash tugmalari"""
    await callback.answer()
    page = int(callback.data.split("_")[-1])
    await show_users_page(callback.message, session, page=page, is_edit=True)


@router.callback_query(F.data == "adm_noop")
async def admin_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("adm_view_user_"), IsAdmin())
async def admin_view_user_card(callback: CallbackQuery, session: AsyncSession):
    """Foydalanuvchi to'liq ma'lumotlar kartasi"""
    await callback.answer()
    user_id = int(callback.data.split("_")[-1])
    user = await UserDAO.get_by_id(session, user_id)

    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
        return

    from keyboards.inline import get_admin_user_kb
    ban_status = "🔴 Bloklangan (Ban)" if user.is_banned else "🟢 Faol"
    is_user_adm = user.is_admin or (user.telegram_id in settings.admin_ids)
    role_status = "👑 Admin" if is_user_adm else "👤 Foydalanuvchi"

    text = (
        f"👤 <b>Foydalanuvchi ma'lumotlari</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Ismi: <b>{user.full_name}</b>\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
    )
    if user.username:
        text += f"📎 Username: @{user.username}\n"
    text += (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Joriy balans: <b>{format_price(user.balance)}</b>\n"
        f"💸 Jami xarajat: <b>{format_price(user.total_spent)}</b>\n"
        f"📦 Buyurtmalar: <b>{user.total_orders} ta</b>\n"
        f"📋 Holati: <b>{ban_status}</b>\n"
        f"👑 Roli: <b>{role_status}</b>\n"
        f"📅 Ro'yxatdan o'tgan: {format_datetime(user.created_at)}\n\n"
        f"Boshqarish buyrug'ini tanlang 👇"
    )
    kb = get_admin_user_kb(user.id, user.is_banned, is_user_adm)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "adm_search_user_start", IsAdmin())
async def admin_search_user_start_cb(callback: CallbackQuery, state: FSMContext):
    """Foydalanuvchini qidirish boshlanishi"""
    await callback.answer()
    await state.set_state(AdminStates.search_user)
    await callback.message.answer(
        "🔍 <b>Foydalanuvchini qidirish</b>\n\n"
        "Telegram ID, @username yoki ismni kiriting:",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )


@router.message(AdminStates.search_user, IsAdmin())
async def admin_search_user(message: Message, state: FSMContext, session: AsyncSession):
    """Foydalanuvchini qidirish natijalari"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    query = message.text.strip()
    users = await UserDAO.search_users(session, query)

    if not users:
        if query.isdigit():
            user = await UserDAO.get_by_telegram_id(session, int(query))
            if user:
                users = [user]

    if not users:
        await message.answer("❌ Foydalanuvchi topilmadi. Qaytadan qidiring yoki ❌ Bekor qilish ni bosing:")
        return

    await state.clear()
    from keyboards.inline import get_admin_user_kb

    for user in users[:5]:
        ban_status = "🔴 Bloklangan (Ban)" if user.is_banned else "🟢 Faol"
        is_user_adm = user.is_admin or (user.telegram_id in settings.admin_ids)
        role_status = "👑 Admin" if is_user_adm else "👤 Foydalanuvchi"
        text = (
            f"👤 <b>{user.full_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        )
        if user.username:
            text += f"📎 @{user.username}\n"
        text += (
            f"💰 Balans: <b>{format_price(user.balance)}</b>\n"
            f"📦 Buyurtmalar: {user.total_orders} ta\n"
            f"💸 Sarflagan: {format_price(user.total_spent)}\n"
            f"📋 Holat: <b>{ban_status}</b> | <b>{role_status}</b>\n"
            f"📅 Ro'yxatdan: {format_datetime(user.created_at)}\n"
        )
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_admin_user_kb(user.id, user.is_banned, is_user_adm),
        )

    await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())


@router.callback_query(F.data.startswith("adm_bonus_"), IsAdmin())
async def admin_add_bonus_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Foydalanuvchi balansiga bonus qo'shish"""
    await callback.answer()
    user_id = int(callback.data.split("_")[-1])
    user = await UserDAO.get_by_id(session, user_id)

    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
        return

    await state.set_state(AdminStates.add_user_bonus)
    await state.update_data(target_user_id=user_id, target_user_name=user.full_name)

    await callback.message.answer(
        f"🎁 <b>{user.full_name} balansiga bonus qo'shish</b>\n\n"
        f"Qo'shmoqchi bo'lgan summa miqdorini so'mda kiriting:\n"
        f"Masalan: <code>10000</code> yoki <code>50000</code>\n\n"
        f"ℹ️ <i>Ushbu summa mijoz hisobiga bonus sifatida qo'shiladi va unga tabrik xabari yuboriladi.</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )


@router.message(AdminStates.add_user_bonus, IsAdmin())
async def admin_add_bonus_save(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    """Bonus summasi qabul qilindi va qo'shildi"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    data = await state.get_data()
    user_id = data.get("target_user_id")

    text_val = message.text.strip().replace(" ", "").replace("+", "").replace(",", "")
    try:
        bonus_amount = Decimal(text_val)
        if bonus_amount <= 0:
            raise ValueError()
    except Exception:
        await message.answer("❌ Iltimos, faqat musbat raqam kiriting (masalan: 10000):")
        return

    user = await UserDAO.update_balance(session, user_id, bonus_amount)
    await state.clear()

    if user:
        # Mijozga chiroyli tabrik xabari
        try:
            await notify_user(
                bot=bot,
                user_telegram_id=user.telegram_id,
                text=(
                    f"🎁 <b>Tabriklaymiz! Balansingizga bonus qo'shildi!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                    f"💰 Qo'shilgan bonus: <b>+{format_price(bonus_amount)}</b>\n"
                    f"💵 Yangi balansingiz: <b>{format_price(user.balance)}</b>\n\n"
                    f"Xizmatlarimizdan unumli foydalanishingizni tilaymiz! ✨"
                ),
            )
        except Exception as e:
            logger.error(f"Mijozga bonus xabarini yuborishda xato: {e}")

        await message.answer(
            f"✅ <b>Bonus muvaffaqiyatli qo'shildi!</b>\n\n"
            f"👤 Mijoz: <b>{user.full_name}</b>\n"
            f"🎁 Qo'shildi: <b>+{format_price(bonus_amount)}</b>\n"
            f"💵 Yangi balans: <b>{format_price(user.balance)}</b>\n\n"
            f"Mijozga tabrik bildirishnomasi yetkazildi. ✅",
            parse_mode="HTML",
            reply_markup=get_admin_menu_kb(),
        )


@router.callback_query(F.data.startswith("adm_set_bal_"), IsAdmin())
async def admin_set_balance_start(callback: CallbackQuery, state: FSMContext):
    """Balans o'zgartirish — boshlanish"""
    await callback.answer()
    user_id = int(callback.data.split("_")[-1])
    await state.set_state(AdminStates.set_user_balance)
    await state.update_data(target_user_id=user_id)

    await callback.message.answer(
        "💰 Yangi balansni kiriting (so'mda):\n"
        "Yoki +10000 (qo'shish) / -5000 (ayirish)",
        reply_markup=get_cancel_kb(),
    )


@router.message(AdminStates.set_user_balance, IsAdmin())
async def admin_set_balance(message: Message, state: FSMContext, session: AsyncSession):
    """Balans o'zgartirish"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    data = await state.get_data()
    user_id = data["target_user_id"]

    text = message.text.strip().replace(" ", "")

    try:
        if text.startswith("+") or text.startswith("-"):
            amount = Decimal(text)
            user = await UserDAO.update_balance(session, user_id, amount)
            action = "qo'shildi" if amount > 0 else "ayirildi"
        else:
            amount = Decimal(text)
            await UserDAO.set_balance(session, user_id, amount)
            user = await UserDAO.get_by_id(session, user_id)
            action = "o'rnatildi"
    except Exception:
        await message.answer("❌ Noto'g'ri format. Raqam kiriting:")
        return

    await state.clear()

    if user:
        await message.answer(
            f"✅ Balans {action}!\n"
            f"👤 {user.full_name}\n"
            f"💰 Yangi balans: {format_price(user.balance)}",
            reply_markup=get_admin_menu_kb(),
        )


@router.callback_query(F.data.startswith("adm_ban_"), IsAdmin())
async def admin_ban_user(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Foydalanuvchini bloklash (Ban) yoki blokdan chiqarish (Unban)"""
    await callback.answer()
    user_id = int(callback.data.split("_")[-1])
    user = await UserDAO.get_by_id(session, user_id)

    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
        return

    if user.telegram_id in settings.admin_ids:
        await callback.answer("⚠️ Super Adminni bloklab bo'lmaydi!", show_alert=True)
        return

    new_status = not user.is_banned
    await UserDAO.ban_user(session, user_id, new_status)

    status_text = "🔴 Bloklandi (Ban)" if new_status else "🟢 Blokdan chiqarildi"
    await callback.answer(f"{status_text}: {user.full_name}", show_alert=True)

    # Foydalanuvchini xabardor qilish
    try:
        if new_status:
            await notify_user(
                bot=bot,
                user_telegram_id=user.telegram_id,
                text="🚫 <b>Sizning hisobingiz bot ma'murlari tomonidan bloklandi.</b>",
            )
        else:
            await notify_user(
                bot=bot,
                user_telegram_id=user.telegram_id,
                text="🟢 <b>Sizning hisobingiz blokdan chiqarildi!</b> Botdan yana to'liq foydalanishingiz mumkin.",
            )
    except Exception:
        pass

    is_user_adm = user.is_admin or (user.telegram_id in settings.admin_ids)
    from keyboards.inline import get_admin_user_kb
    ban_label = "🔴 Bloklangan (Ban)" if new_status else "🟢 Faol"
    role_status = "👑 Admin" if is_user_adm else "👤 Foydalanuvchi"

    text = (
        f"👤 <b>Foydalanuvchi ma'lumotlari</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Ismi: <b>{user.full_name}</b>\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
    )
    if user.username:
        text += f"📎 Username: @{user.username}\n"
    text += (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Joriy balans: <b>{format_price(user.balance)}</b>\n"
        f"💸 Jami xarajat: <b>{format_price(user.total_spent)}</b>\n"
        f"📦 Buyurtmalar: <b>{user.total_orders} ta</b>\n"
        f"📋 Holati: <b>{ban_label}</b>\n"
        f"👑 Roli: <b>{role_status}</b>\n"
        f"📅 Ro'yxatdan o'tgan: {format_datetime(user.created_at)}\n\n"
        f"Boshqarish buyrug'ini tanlang 👇"
    )

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_admin_user_kb(user_id, new_status, is_user_adm),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_toggle_admin_"), IsAdmin())
async def admin_toggle_admin(callback: CallbackQuery, session: AsyncSession):
    """Foydalanuvchiga admin huquqini berish / olish"""
    user_id = int(callback.data.split("_")[-1])
    user = await UserDAO.get_by_id(session, user_id)

    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
        return

    # Asosiy .env dagi adminni o'zgartirib bo'lmaydi
    if user.telegram_id in settings.admin_ids:
        await callback.answer("⚠️ Bu asosiy Super Admin (.env), uni o'zgartirib bo'lmaydi!", show_alert=True)
        return

    new_admin_status = not user.is_admin
    await UserDAO.set_admin(session, user_id, new_admin_status)

    status_text = "👑 Admin etib tayinlandi!" if new_admin_status else "❌ Adminlikdan olindi!"
    await callback.answer(f"{status_text} ({user.full_name})", show_alert=True)

    await callback.message.edit_reply_markup(
        reply_markup=get_admin_user_kb(user_id, user.is_banned, new_admin_status)
    )


# ============================================
# XIZMATLAR BOSHQARUVI
# ============================================

@router.message(F.text == "🛍 Xizmatlar boshqaruvi", IsAdmin())
async def admin_services(message: Message, session: AsyncSession):
    """Xizmatlar boshqaruvi"""
    categories = await CategoryDAO.get_all_active(session)
    await message.answer(
        "🛍 <b>Xizmatlar boshqaruvi</b>\n\n"
        "Kategoriyani tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_services_kb(categories),
    )


@router.callback_query(F.data.startswith("adm_cat_"), IsAdmin())
async def admin_category_services(callback: CallbackQuery, session: AsyncSession):
    """Admin — kategoriya ichidagi xizmatlar"""
    category_id = int(callback.data.split("_")[-1])
    services = await ServiceDAO.get_by_category(session, category_id)
    category = await CategoryDAO.get_by_id(session, category_id)

    # Faol bo'lmaganlarni ham ko'rsatish
    from sqlalchemy import select
    from database.models import Service
    from database.engine import async_session
    async with async_session() as sess:
        stmt = select(Service).where(Service.category_id == category_id).order_by(Service.sort_order)
        result = await sess.execute(stmt)
        all_services = result.scalars().all()

    cat_name = category.name if category else "Noma'lum"

    await callback.message.edit_text(
        f"🛍 <b>{cat_name}</b> — xizmatlar\n\n"
        f"Tahrirlash uchun xizmatni tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_service_list_kb(all_services, category_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_svc_"), IsAdmin())
async def admin_edit_service(callback: CallbackQuery, session: AsyncSession):
    """Xizmatni tahrirlash"""
    service_id = int(callback.data.split("_")[-1])
    service = await ServiceDAO.get_by_id(session, service_id)

    if not service:
        await callback.answer("❌ Xizmat topilmadi!", show_alert=True)
        return

    status = "✅ Faol" if service.is_active else "❌ O'chirilgan"

    text = (
        f"📦 <b>{service.name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Narx: {format_price(service.price_per_1000)} / 1000\n"
        f"📊 Min: {format_number(service.min_quantity)}\n"
        f"📊 Max: {format_number(service.max_quantity)}\n"
        f"📋 Holat: {status}\n"
    )
    if service.description:
        text += f"📝 Tavsif: {service.description}\n"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_admin_service_edit_kb(service_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_edit_price_"), IsAdmin())
async def admin_edit_price_start(callback: CallbackQuery, state: FSMContext):
    """Narx o'zgartirish — boshlanish"""
    service_id = int(callback.data.split("_")[-1])
    await state.set_state(AdminStates.edit_service_price)
    await state.update_data(edit_service_id=service_id)

    await callback.message.answer(
        "💰 Yangi narxni kiriting (1000 dona uchun, so'mda):",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.edit_service_price, IsAdmin())
async def admin_edit_price(message: Message, state: FSMContext, session: AsyncSession):
    """Narx o'zgartirish"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    try:
        price = Decimal(message.text.strip().replace(" ", ""))
    except Exception:
        await message.answer("❌ Noto'g'ri format. Raqam kiriting:")
        return

    data = await state.get_data()
    service_id = data["edit_service_id"]

    await ServiceDAO.update(session, service_id, price_per_1000=price)
    await state.clear()

    await message.answer(
        f"✅ Narx yangilandi: {format_price(price)} / 1000",
        reply_markup=get_admin_menu_kb(),
    )


@router.callback_query(F.data.startswith("adm_edit_name_"), IsAdmin())
async def admin_edit_name_start(callback: CallbackQuery, state: FSMContext):
    """Nom o'zgartirish — boshlanish"""
    service_id = int(callback.data.split("_")[-1])
    await state.set_state(AdminStates.edit_service_name)
    await state.update_data(edit_service_id=service_id)

    await callback.message.answer(
        "📝 Yangi nomni kiriting:",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.edit_service_name, IsAdmin())
async def admin_edit_name(message: Message, state: FSMContext, session: AsyncSession):
    """Nom o'zgartirish"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    data = await state.get_data()
    service_id = data["edit_service_id"]

    await ServiceDAO.update(session, service_id, name=message.text.strip())
    await state.clear()

    await message.answer(
        f"✅ Nom yangilandi: {message.text.strip()}",
        reply_markup=get_admin_menu_kb(),
    )


@router.callback_query(F.data.startswith("adm_toggle_"), IsAdmin())
async def admin_toggle_service(callback: CallbackQuery, session: AsyncSession):
    """Xizmatni yoqish/o'chirish"""
    service_id = int(callback.data.split("_")[-1])
    service = await ServiceDAO.get_by_id(session, service_id)

    if not service:
        await callback.answer("❌ Xizmat topilmadi!", show_alert=True)
        return

    new_status = not service.is_active
    await ServiceDAO.update(session, service_id, is_active=new_status)

    status_text = "✅ Yoqildi" if new_status else "❌ O'chirildi"
    await callback.answer(f"{status_text}", show_alert=True)

    # Tugmalarni yangilash
    await callback.message.edit_reply_markup(
        reply_markup=get_admin_service_edit_kb(service_id)
    )


@router.callback_query(F.data.startswith("adm_del_svc_"), IsAdmin())
async def admin_delete_service(callback: CallbackQuery, session: AsyncSession):
    """Xizmatni o'chirish"""
    service_id = int(callback.data.split("_")[-1])
    deleted = await ServiceDAO.delete(session, service_id)

    if deleted:
        await callback.answer("🗑 Xizmat o'chirildi!", show_alert=True)
        await callback.message.edit_text("🗑 Xizmat o'chirildi.")
    else:
        await callback.answer("❌ O'chirishda xato!", show_alert=True)


@router.callback_query(F.data.startswith("adm_add_svc_"), IsAdmin())
async def admin_add_service_start(callback: CallbackQuery, state: FSMContext):
    """Yangi xizmat qo'shish — boshlanish"""
    category_id = int(callback.data.split("_")[-1])
    await state.set_state(AdminStates.add_service_name)
    await state.update_data(new_service_category_id=category_id)

    await callback.message.answer(
        "➕ <b>Yangi xizmat qo'shish</b>\n\n"
        "📝 Xizmat nomini kiriting:",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.add_service_name, IsAdmin())
async def admin_add_service_name(message: Message, state: FSMContext):
    """Yangi xizmat — nom"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    await state.update_data(new_service_name=message.text.strip())
    await state.set_state(AdminStates.add_service_price)
    await message.answer("💰 Narxni kiriting (1000 dona uchun, so'mda):")


@router.message(AdminStates.add_service_price, IsAdmin())
async def admin_add_service_price(message: Message, state: FSMContext):
    """Yangi xizmat — narx"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    try:
        price = Decimal(message.text.strip().replace(" ", ""))
    except Exception:
        await message.answer("❌ Noto'g'ri format. Raqam kiriting:")
        return

    await state.update_data(new_service_price=str(price))
    await state.set_state(AdminStates.add_service_min)
    await message.answer(
        "📊 Minimum miqdorni kiriting (masalan: 100):\n"
        "Bir martalik xizmat bo'lsa 1 yozing."
    )


@router.message(AdminStates.add_service_min, IsAdmin())
async def admin_add_service_min(message: Message, state: FSMContext):
    """Yangi xizmat — minimum"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    try:
        min_qty = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return

    await state.update_data(new_service_min=min_qty)
    await state.set_state(AdminStates.add_service_max)
    await message.answer(
        "📊 Maximum miqdorni kiriting (masalan: 100000):\n"
        "Bir martalik xizmat bo'lsa 1 yozing."
    )


@router.message(AdminStates.add_service_max, IsAdmin())
async def admin_add_service_max(message: Message, state: FSMContext):
    """Yangi xizmat — maximum va vaqt oralig'i so'rash"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    try:
        max_qty = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return

    await state.update_data(new_service_max=max_qty)
    await state.set_state(AdminStates.add_service_execution_time)

    from keyboards.reply import get_skip_kb
    await message.answer(
        "⏱ <b>Bajarilish vaqti oralig'ini kiriting:</b>\n"
        "Masalan: <code>15 daqiqa - 24 soat</code> yoki <code>1-3 soat</code>\n\n"
        "Standart qiymat (10 daqiqa - 24 soat) qoldirish uchun ⏩ O'tkazib yuborish ni bosing:",
        parse_mode="HTML",
        reply_markup=get_skip_kb(),
    )


@router.message(AdminStates.add_service_execution_time, IsAdmin())
async def admin_add_service_time(message: Message, state: FSMContext, session: AsyncSession):
    """Yangi xizmat — vaqt oralig'i va saqlash"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    if message.text == "⏩ O'tkazib yuborish":
        exec_time = "10 daqiqa - 24 soat"
    else:
        exec_time = message.text.strip()

    data = await state.get_data()
    await state.clear()

    service = await ServiceDAO.create(
        session=session,
        category_id=data["new_service_category_id"],
        name=data["new_service_name"],
        price_per_1000=Decimal(data["new_service_price"]),
        min_quantity=data["new_service_min"],
        max_quantity=data["new_service_max"],
        execution_time=exec_time,
    )

    await message.answer(
        f"✅ <b>Xizmat muvaffaqiyatli qo'shildi!</b>\n\n"
        f"📦 {service.name}\n"
        f"💰 Narx: {format_price(service.price_per_1000)} / 1000\n"
        f"📊 Miqdor: {format_number(service.min_quantity)} — {format_number(service.max_quantity)}\n"
        f"⏱ Bajarilish oralig'i: <b>{service.execution_time}</b>",
        parse_mode="HTML",
        reply_markup=get_admin_menu_kb(),
    )


@router.callback_query(F.data == "adm_add_category", IsAdmin())
async def admin_add_category_start(callback: CallbackQuery, state: FSMContext):
    """Yangi kategoriya qo'shish"""
    await state.set_state(AdminStates.add_category_name)
    await callback.message.answer(
        "➕ Kategoriya nomini kiriting:",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.add_category_name, IsAdmin())
async def admin_add_category_name(message: Message, state: FSMContext):
    """Kategoriya nomi"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    await state.update_data(new_cat_name=message.text.strip())
    await state.set_state(AdminStates.add_category_emoji)
    await message.answer("Emoji kiriting (masalan: 📸):")


@router.message(AdminStates.add_category_emoji, IsAdmin())
async def admin_add_category_emoji(message: Message, state: FSMContext, session: AsyncSession):
    """Kategoriya emoji va saqlash"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    data = await state.get_data()
    await state.clear()

    category = await CategoryDAO.create(
        session=session,
        name=data["new_cat_name"],
        emoji=message.text.strip(),
    )

    await message.answer(
        f"✅ Kategoriya qo'shildi!\n"
        f"{category.emoji} {category.name}",
        reply_markup=get_admin_menu_kb(),
    )


@router.callback_query(F.data == "adm_back_cats", IsAdmin())
async def admin_back_to_cats(callback: CallbackQuery, session: AsyncSession):
    """Kategoriyalarga qaytish"""
    categories = await CategoryDAO.get_all_active(session)
    await callback.message.edit_text(
        "🛍 <b>Xizmatlar boshqaruvi</b>\n\nKategoriyani tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_services_kb(categories),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_back_services", IsAdmin())
async def admin_back_services(callback: CallbackQuery, session: AsyncSession):
    """Kategoriyalarga qaytish (xizmat tahrirlashdan)"""
    categories = await CategoryDAO.get_all_active(session)
    await callback.message.edit_text(
        "🛍 <b>Xizmatlar boshqaruvi</b>\n\nKategoriyani tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_services_kb(categories),
    )
    await callback.answer()


# ============================================
# TO'LOVLAR BOSHQARUVI
# ============================================

@router.message(F.text == "💳 To'lovlar", IsAdmin())
async def admin_payments(message: Message, session: AsyncSession):
    """Kutilayotgan to'lovlar ro'yxati"""
    pending = await PaymentDAO.get_pending(session)

    if not pending:
        await message.answer(
            "💳 <b>To'lovlar</b>\n\n✅ Kutilayotgan to'lovlar yo'q.",
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"💳 <b>Kutilayotgan to'lovlar: {len(pending)} ta</b>",
        parse_mode="HTML",
    )

    for payment in pending[:10]:
        user = await UserDAO.get_by_id(session, payment.user_id)
        user_name = user.full_name if user else "Noma'lum"
        user_tg = user.telegram_id if user else 0

        text = (
            f"💳 <b>To'lov #{payment.id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 {user_name} (<code>{user_tg}</code>)\n"
            f"💰 Summa: <b>{format_price(payment.amount)}</b>\n"
            f"💳 Usul: {get_payment_method_text(payment.payment_method.value)}\n"
            f"📅 {format_datetime(payment.created_at)}\n"
        )

        from keyboards.inline import get_admin_payment_kb
        if payment.screenshot_file_id:
            await message.answer_photo(
                photo=payment.screenshot_file_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=get_admin_payment_kb(payment.id),
            )
        else:
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=get_admin_payment_kb(payment.id),
            )


@router.callback_query(F.data.startswith("adm_pay_approve_"), IsAdmin())
async def admin_approve_payment(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """To'lovni tasdiqlash"""
    payment_id = int(callback.data.split("_")[-1])

    admin_user = await UserDAO.get_by_telegram_id(session, callback.from_user.id)
    admin_id = admin_user.id if admin_user else 0

    payment = await PaymentDAO.approve(session, payment_id, admin_id)

    if not payment:
        await callback.answer("❌ To'lov topilmadi yoki allaqachon ko'rib chiqilgan!", show_alert=True)
        return

    user = await UserDAO.get_by_id(session, payment.user_id)

    # Foydalanuvchiga xabar
    if user:
        await notify_user(
            bot=bot,
            user_telegram_id=user.telegram_id,
            text=(
                f"✅ <b>To'lovingiz tasdiqlandi!</b>\n\n"
                f"💰 Summa: {format_price(payment.amount)}\n"
                f"💵 Yangi balans: {format_price(user.balance)}\n\n"
                f"🛒 Endi xizmatlardan foydalanishingiz mumkin!"
            ),
        )

    await callback.message.edit_caption(
        caption=(
            f"✅ <b>TO'LOV TASDIQLANDI</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💳 #{payment_id}\n"
            f"💰 {format_price(payment.amount)}\n"
            f"👤 Admin: {callback.from_user.full_name}"
        ),
        parse_mode="HTML",
    )
    await callback.answer("✅ Tasdiqlandi!", show_alert=True)


@router.callback_query(F.data.startswith("adm_pay_reject_"), IsAdmin())
async def admin_reject_payment(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """To'lovni rad etish"""
    payment_id = int(callback.data.split("_")[-1])

    admin_user = await UserDAO.get_by_telegram_id(session, callback.from_user.id)
    admin_id = admin_user.id if admin_user else 0

    payment = await PaymentDAO.reject(session, payment_id, admin_id)

    if not payment:
        await callback.answer("❌ To'lov topilmadi yoki allaqachon ko'rib chiqilgan!", show_alert=True)
        return

    user = await UserDAO.get_by_id(session, payment.user_id)

    # Foydalanuvchiga xabar
    if user:
        await notify_user(
            bot=bot,
            user_telegram_id=user.telegram_id,
            text=(
                f"❌ <b>To'lovingiz rad etildi!</b>\n\n"
                f"💰 Summa: {format_price(payment.amount)}\n\n"
                f"Sabab bo'lishi mumkin:\n"
                f"• Screenshot noto'g'ri\n"
                f"• Summa mos emas\n"
                f"• Boshqa sabab\n\n"
                f"📞 Muammo bo'lsa: @{settings.support_username}"
            ),
        )

    try:
        await callback.message.edit_caption(
            caption=(
                f"❌ <b>TO'LOV RAD ETILDI</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💳 #{payment_id}\n"
                f"💰 {format_price(payment.amount)}\n"
                f"👤 Admin: {callback.from_user.full_name}"
            ),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.edit_text(
            f"❌ <b>TO'LOV RAD ETILDI</b> #{payment_id}",
            parse_mode="HTML",
        )
    await callback.answer("❌ Rad etildi!", show_alert=True)


# ============================================
# BUYURTMALAR BOSHQARUVI (GURUHDAN)
# ============================================

# ============================================
# BUYURTMALAR BOSHQARUVI
# ============================================

@router.message(F.text == "📦 Buyurtmalar", IsAdmin())
async def admin_orders(message: Message, session: AsyncSession):
    """Buyurtmalar boshqaruvi menyusi"""
    from keyboards.inline import get_admin_orders_menu_kb

    pending = await OrderDAO.get_pending_orders(session)
    total_orders = await OrderDAO.get_total_count(session)

    text = (
        "📦 <b>Buyurtmalar boshqaruvi</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"⏳ Kutilayotgan buyurtmalar: <b>{len(pending)} ta</b>\n"
        f"📊 Jami barcha buyurtmalar: <b>{total_orders} ta</b>\n\n"
        "Kerakli bo'limni tanlang 👇"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_admin_orders_menu_kb())


@router.callback_query(F.data == "adm_orders_menu", IsAdmin())
async def admin_orders_menu_callback(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Buyurtmalar menyusiga qaytish"""
    await state.clear()
    from keyboards.inline import get_admin_orders_menu_kb

    pending = await OrderDAO.get_pending_orders(session)
    total_orders = await OrderDAO.get_total_count(session)

    text = (
        "📦 <b>Buyurtmalar boshqaruvi</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"⏳ Kutilayotgan buyurtmalar: <b>{len(pending)} ta</b>\n"
        f"📊 Jami barcha buyurtmalar: <b>{total_orders} ta</b>\n\n"
        "Kerakli bo'limni tanlang 👇"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_orders_menu_kb())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=get_admin_orders_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "adm_orders_pending", IsAdmin())
async def admin_orders_pending_list(callback: CallbackQuery, session: AsyncSession):
    """Kutilayotgan buyurtmalar ro'yxati"""
    pending = await OrderDAO.get_pending_orders(session)

    if not pending:
        await callback.answer("✅ Kutilayotgan buyurtmalar yo'q!", show_alert=True)
        return

    await callback.message.answer(
        f"📦 <b>Kutilayotgan buyurtmalar: {len(pending)} ta</b> (oxirgi 10 ta ko'rsatiladi):",
        parse_mode="HTML",
    )

    for order in pending[:10]:
        service_name = order.service.name if order.service else "—"
        exec_time = order.service.execution_time if order.service else "—"
        user = await UserDAO.get_by_id(session, order.user_id)
        user_info = f"{user.full_name} ({user.telegram_id})" if user else "Noma'lum"
        order_num = getattr(order, "order_number", None) or str(order.id)

        text = (
            f"📦 <b>Buyurtma #{order_num}</b> (ID: {order.id})\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 Mijoz: {user_info}\n"
            f"📦 Xizmat: {service_name}\n"
            f"🔗 Havola: {order.target_link}\n"
            f"📊 Miqdor: {format_number(order.quantity)}\n"
            f"💰 Narx: {format_price(order.total_price)}\n"
            f"⏱ Bajarilish oralig'i: {exec_time}\n"
            f"📅 {format_datetime(order.created_at)}\n"
        )

        from keyboards.inline import get_admin_order_kb
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_admin_order_kb(order.id),
        )
    await callback.answer()


@router.callback_query(F.data == "adm_orders_search", IsAdmin())
async def admin_orders_search_start(callback: CallbackQuery, state: FSMContext):
    """Buyurtma raqamini kiritib boshqarish"""
    await state.set_state(AdminStates.manage_order_by_id)
    await callback.message.answer(
        "🔍 <b>Buyurtma raqamini kiriting:</b>\n\n"
        "Masalan: <code>749201</code> yoki <code>#749201</code> yoki tartib raqami (masalan: <code>15</code>)\n\n"
        "Buyurtma topilgach, uni bitta tugma bilan <b>Bajarildi</b> yoki <b>Atmen</b> qilishingiz mumkin.",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.manage_order_by_id, IsAdmin())
async def admin_process_order_search(message: Message, state: FSMContext, session: AsyncSession):
    """Buyurtma raqamini qidirish va boshqaruv kartasini ko'rsatish"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    query = message.text.strip()
    order = await OrderDAO.get_by_order_number_or_id(session, query)

    if not order:
        await message.answer(
            f"❌ <b>'{query}' raqamli buyurtma topilmadi!</b>\n\n"
            "Iltimos, buyurtma raqamini tekshirib qaytadan kiriting yoki ❌ Bekor qilish ni bosing:",
            parse_mode="HTML",
            reply_markup=get_cancel_kb(),
        )
        return

    await state.clear()

    user = await UserDAO.get_by_id(session, order.user_id)
    service = await ServiceDAO.get_by_id(session, order.service_id)
    service_name = service.name if service else "—"
    exec_time = service.execution_time if service else "10 daqiqa - 24 soat"
    order_num = getattr(order, "order_number", None) or str(order.id)

    status_val = order.status.value if hasattr(order.status, 'value') else order.status
    status_emoji = get_status_emoji(status_val)
    status_text = get_status_text(status_val)

    text = (
        f"📦 <b>Buyurtma #{order_num}</b> (Baza ID: {order.id})\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 Mijoz: <b>{user.full_name if user else 'Noma’lum'}</b>\n"
        f"🆔 Telegram ID: <code>{user.telegram_id if user else '—'}</code>\n"
    )
    if user and user.username:
        text += f"📎 Username: @{user.username}\n"
    text += (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🛍 Xizmat: <b>{service_name}</b>\n"
        f"🔗 Havola: {order.target_link}\n"
        f"📊 Miqdor: {format_number(order.quantity)}\n"
        f"💰 Narx: <b>{format_price(order.total_price)}</b>\n"
        f"⏱ Bajarilish oralig'i: <b>{exec_time}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📋 Hozirgi holat: {status_emoji} <b>{status_text}</b>\n"
        f"📅 Yaratilgan: {format_datetime(order.created_at)}\n"
        f"🔄 Yangilangan: {format_datetime(order.updated_at)}\n\n"
        f"Quyidagi tugmalar orqali buyurtmaga buyruq bering 👇"
    )

    from keyboards.inline import get_admin_order_manage_kb
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_admin_order_manage_kb(order.id),
    )


@router.callback_query(F.data.startswith("adm_complete_"), IsAdmin())
async def admin_complete_order(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Buyurtmani bajarildi deb belgilash (qotishlarsiz tezkor javob)"""
    await callback.answer("✅ Bajarilmoqda...")
    order_id = int(callback.data.split("_")[-1])
    order = await OrderDAO.update_status(session, order_id, OrderStatus.COMPLETED)

    if not order:
        await callback.message.answer("❌ Buyurtma topilmadi!")
        return

    user = await UserDAO.get_by_id(session, order.user_id)
    service = await ServiceDAO.get_by_id(session, order.service_id)
    service_name = service.name if service else "—"
    order_num = getattr(order, "order_number", None) or str(order.id)

    # Foydalanuvchiga xabar
    if user:
        try:
            await notify_user(
                bot=bot,
                user_telegram_id=user.telegram_id,
                text=(
                    f"✅ <b>Buyurtmangiz muvaffaqiyatli bajarildi!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                    f"🆔 Buyurtma raqami: <b>#{order_num}</b>\n"
                    f"📦 Xizmat: {service_name}\n"
                    f"🔗 {order.target_link}\n"
                    f"📊 Miqdor: {format_number(order.quantity)}\n\n"
                    f"Xizmatimizdan foydalanganingiz uchun rahmat! 🙏"
                ),
            )
        except Exception as e:
            logger.error(f"Foydalanuvchiga bajarildi xabarini yuborishda xato: {e}")

    try:
        await callback.message.edit_text(
            f"✅ <b>BUYURTMA BAJARILDI</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 #{order_num} — {service_name}\n"
            f"👤 Admin: {callback.from_user.full_name}\n"
            f"📅 {format_datetime(order.updated_at)}",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_progress_"), IsAdmin())
async def admin_progress_order(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Buyurtmani jarayonda deb belgilash"""
    await callback.answer("🔄 Jarayonga o'tkazildi!")
    order_id = int(callback.data.split("_")[-1])
    order = await OrderDAO.update_status(session, order_id, OrderStatus.IN_PROGRESS)

    if not order:
        return

    user = await UserDAO.get_by_id(session, order.user_id)
    order_num = getattr(order, "order_number", None) or str(order.id)
    if user:
        try:
            await notify_user(
                bot=bot,
                user_telegram_id=user.telegram_id,
                text=(
                    f"🔄 <b>Buyurtmangiz jarayonda!</b>\n\n"
                    f"📦 #{order_num}\n"
                    f"Tez orada bajariladi. Kuting..."
                ),
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("adm_cancel_"), IsAdmin())
async def admin_cancel_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Buyurtmani bekor qilish — avval sababini so'rash"""
    await callback.answer()
    order_id = int(callback.data.split("_")[-1])
    order = await OrderDAO.get_by_id(session, order_id)

    if not order:
        await callback.answer("❌ Buyurtma topilmadi!", show_alert=True)
        return

    order_num = getattr(order, "order_number", None) or str(order.id)
    await state.set_state(AdminStates.cancel_order_reason)
    await state.update_data(
        cancelling_order_id=order_id,
        cancelling_order_number=order_num,
        cancelling_message_id=callback.message.message_id,
        cancelling_chat_id=callback.message.chat.id,
    )

    await callback.message.reply(
        f"❌ <b>Buyurtma #{order_num} ni bekor qilish (Atmen)</b>\n\n"
        f"Iltimos, bekor qilish <b>sababini yozing</b>:\n"
        f"<i>(Ushbu sabab mijozga balansi qaytarilgani haqidagi xabarda ko'rsatiladi)</i>\n\n"
        f"📌 Misol uchun:\n"
        f"• <code>Havola noto'g'ri kiritilgan</code>\n"
        f"• <code>Profil yopiq (privat) holatda</code>\n"
        f"• <code>Telegram username topilmadi</code>\n\n"
        f"Sababni kiriting yoki pastdagi ❌ Bekor qilish tugmasini bosing 👇",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )


@router.message(AdminStates.cancel_order_reason, IsAdmin())
async def admin_save_cancel_reason(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    """Bekor qilish sababi qabul qilindi — pulni qaytarish va mijozga sababi bilan xabar berish"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Buyurtmani bekor qilish jarayoni to'xtatildi.", reply_markup=get_admin_menu_kb())
        return

    reason = message.text.strip()
    data = await state.get_data()
    order_id = data.get("cancelling_order_id")

    if not order_id:
        await state.clear()
        await message.answer("❌ Buyurtma ma'lumotlari topilmadi!", reply_markup=get_admin_menu_kb())
        return

    order = await OrderDAO.get_by_id(session, order_id)
    if not order:
        await state.clear()
        await message.answer("❌ Buyurtma topilmadi!", reply_markup=get_admin_menu_kb())
        return

    # Buyurtmani bekor qilish
    await OrderDAO.update_status(session, order_id, OrderStatus.CANCELLED)

    # Pulni qaytarish
    user = await UserDAO.update_balance(session, order.user_id, order.total_price)
    service = await ServiceDAO.get_by_id(session, order.service_id)
    service_name = service.name if service else "—"
    order_num = getattr(order, "order_number", None) or str(order.id)

    await state.clear()

    # Foydalanuvchiga sababi bilan xabar
    if user:
        try:
            await notify_user(
                bot=bot,
                user_telegram_id=user.telegram_id,
                text=(
                    f"❌ <b>Buyurtmangiz bekor qilindi (Atmen)!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                    f"🆔 Buyurtma raqami: <b>#{order_num}</b>\n"
                    f"📦 Xizmat: <b>{service_name}</b>\n"
                    f"💰 Qaytarilgan summa: <b>{format_price(order.total_price)}</b>\n"
                    f"💵 Yangi balansingiz: <b>{format_price(user.balance)}</b>\n\n"
                    f"⚠️ <b>Bekor qilish sababi:</b>\n"
                    f"<i>{reason}</i>\n\n"
                    f"To'langan summa balansingizga to'liq qaytarildi."
                ),
            )
        except Exception as e:
            logger.error(f"Mijozga bekor qilish xabarini yuborishda xato: {e}")

    # Asl xabarni tahrirlash (agar mumkin bo'lsa)
    orig_msg_id = data.get("cancelling_message_id")
    orig_chat_id = data.get("cancelling_chat_id")
    if orig_msg_id and orig_chat_id:
        try:
            await bot.edit_message_text(
                chat_id=orig_chat_id,
                message_id=orig_msg_id,
                text=(
                    f"❌ <b>BUYURTMA BEKOR QILINDI (ATMEN)</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                    f"📦 #{order_num} — {service_name}\n"
                    f"👤 Admin: {message.from_user.full_name}\n"
                    f"📝 Sabab: <i>{reason}</i>\n"
                    f"💰 Qaytarildi: {format_price(order.total_price)}"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

    await message.answer(
        f"✅ <b>Buyurtma #{order_num} bekor qilindi!</b>\n\n"
        f"👤 Mijoz: <b>{user.full_name if user else '—'}</b>\n"
        f"💰 Qaytarildi: <b>{format_price(order.total_price)}</b>\n"
        f"📝 Ko'rsatilgan sabab: <i>{reason}</i>\n\n"
        f"Mijozga bekor qilish sababi va qaytarilgan balans haqida bildirishnoma yuborildi. ✅",
        parse_mode="HTML",
        reply_markup=get_admin_menu_kb(),
    )


# ============================================
# BROADCAST
# ============================================

@router.message(F.text == "📢 Xabar yuborish", IsAdmin())
async def admin_broadcast_start(message: Message, state: FSMContext):
    """Broadcast — boshlanish"""
    await state.set_state(AdminStates.broadcast_message)
    await message.answer(
        "📢 <b>Broadcast xabar</b>\n\n"
        "Barcha foydalanuvchilarga yuboriladigan xabarni yozing.\n"
        "Rasm, video va matn qo'llab-quvvatlanadi.",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )


@router.message(AdminStates.broadcast_message, IsAdmin())
async def admin_broadcast_preview(message: Message, state: FSMContext):
    """Broadcast — preview"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    # Xabar ma'lumotlarini saqlash
    broadcast_data = {
        "text": message.text or message.caption,
        "photo_id": message.photo[-1].file_id if message.photo else None,
        "video_id": message.video.file_id if message.video else None,
    }
    await state.update_data(broadcast=broadcast_data)
    await state.set_state(AdminStates.broadcast_confirm)

    await message.answer(
        "📢 Xabar tayyor. Yuborilsinmi?",
        reply_markup=get_broadcast_confirm_kb(),
    )


@router.callback_query(F.data == "adm_broadcast_send", IsAdmin())
async def admin_broadcast_send(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    """Broadcast yuborish"""
    data = await state.get_data()
    broadcast = data.get("broadcast", {})
    await state.clear()

    user_ids = await UserDAO.get_all_ids(session)
    total = len(user_ids)
    sent = 0
    failed = 0

    status_msg = await callback.message.edit_text(
        f"📢 Yuborilmoqda... 0/{total}",
    )

    for i, user_id in enumerate(user_ids):
        try:
            if broadcast.get("photo_id"):
                await bot.send_photo(
                    chat_id=user_id,
                    photo=broadcast["photo_id"],
                    caption=broadcast.get("text", ""),
                    parse_mode="HTML",
                )
            elif broadcast.get("video_id"):
                await bot.send_video(
                    chat_id=user_id,
                    video=broadcast["video_id"],
                    caption=broadcast.get("text", ""),
                    parse_mode="HTML",
                )
            elif broadcast.get("text"):
                await bot.send_message(
                    chat_id=user_id,
                    text=broadcast["text"],
                    parse_mode="HTML",
                )
            sent += 1
        except Exception:
            failed += 1

        # Har 50 ta xabardan keyin progress yangilash
        if (i + 1) % 50 == 0:
            try:
                await status_msg.edit_text(
                    f"📢 Yuborilmoqda... {i + 1}/{total}\n"
                    f"✅ {sent} | ❌ {failed}"
                )
            except Exception:
                pass

        # Telegram limitlari — sekundiga 30 ta xabar
        await asyncio.sleep(0.035)

    try:
        await status_msg.edit_text(
            f"✅ <b>Broadcast yakunlandi!</b>\n\n"
            f"📊 Jami: {total}\n"
            f"✅ Yuborildi: {sent}\n"
            f"❌ Xato: {failed}",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await callback.message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())


@router.callback_query(F.data == "adm_broadcast_cancel", IsAdmin())
async def admin_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    """Broadcast bekor qilish"""
    await state.clear()
    await callback.message.edit_text("❌ Broadcast bekor qilindi.")
    await callback.message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
    await callback.answer()


# ============================================
# SOZLAMALAR BOSHQARUVI
# ============================================

@router.message(F.text == "⚙️ Sozlamalar", IsAdmin())
async def admin_settings(message: Message, session: AsyncSession):
    """Barcha sozlamalarni ko'rsatish"""
    all_settings = await SettingsDAO.get_all(session)

    text = (
        "⚙️ <b>Bot Sozlamalari</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
    )

    settings_display = {
        "ton_rate": "💎 1 TON kursi",
        "usdt_rate": "💵 1 USDT kursi",
        "wallet_ton": "📬 TON hamyon",
        "wallet_usdt": "📬 USDT hamyon",
        "stars_rate": "⭐ Stars kursi",
        "payment_card_click": "💳 Click karta",
        "payment_card_payme": "💳 Payme karta",
        "payment_card_holder": "👤 Karta egasi",
        "min_payment_amount": "💰 Min to'lov summasi",
        "referral_bonus_percent": "🔗 Referal bonus",
        "support_username": "📞 Support",
        "welcome_bonus": "🎁 Xush kelibsiz bonusi",
    }

    for key, label in settings_display.items():
        val = all_settings.get(key, {}).get("value", "—")
        if key == "referral_bonus_percent":
            val = f"{val}%"
        elif key in ("min_payment_amount", "stars_rate", "welcome_bonus", "ton_rate", "usdt_rate"):
            try:
                val = f"{int(val):,} so'm".replace(",", " ")
            except Exception:
                pass
        text += f"{label}: <b>{val}</b>\n"

    text += (
        "\n━━━━━━━━━━━━━━━━━━\n"
        "O'zgartirish uchun quyidagilardan birini tanlang 👇"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for key, label in settings_display.items():
        builder.button(text=f"✏️ {label}", callback_data=f"adm_setting_{key}")
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_admin")
    )

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("adm_setting_"), IsAdmin())
async def admin_edit_setting(callback: CallbackQuery, state: FSMContext):
    """Sozlamani tahrirlash — boshlanish"""
    key = callback.data.replace("adm_setting_", "")

    hints = {
        "ton_rate": "1 TON narxini so'mda kiriting (masalan: 70000)\nKlient TON kiritganda shu narx bo'yicha avtomatik so'mga hisoblanadi!",
        "usdt_rate": "1 USDT narxini so'mda kiriting (masalan: 13000)\nKlient USDT kiritganda shu narx bo'yicha avtomatik so'mga hisoblanadi!",
        "wallet_ton": "Admin TON hamyon manzilini kiriting (masalan: UQ...):",
        "wallet_usdt": "Admin USDT (TRC-20 / TON) hamyon manzilini kiriting (masalan: TX...):",
        "referral_bonus_percent": "Referal bonus foizini kiriting (masalan: 5)",
        "min_payment_amount": "Minimum to'lov summasini kiriting so'mda (masalan: 5000)",
        "stars_rate": "1 Telegram Star = necha so'm (masalan: 1500)",
        "payment_card_click": "Click karta raqamini kiriting (masalan: 8600 1234 5678 9012)",
        "payment_card_payme": "Payme karta raqamini kiriting",
        "payment_card_holder": "Karta egasining to'liq ismini kiriting",
        "support_username": "Support username kiriting (@ siz)",
        "welcome_bonus": "Yangi foydalanuvchiga beriladigan bonus (so'mda, 0 = yo'q)",
    }

    await state.set_state(AdminStates.edit_bot_setting)
    await state.update_data(editing_setting_key=key)

    hint = hints.get(key, "Yangi qiymatni kiriting:")
    await callback.message.answer(
        f"✏️ <b>{key}</b>\n\n{hint}",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.edit_bot_setting, IsAdmin())
async def admin_save_setting(message: Message, state: FSMContext, session: AsyncSession):
    """Sozlamani saqlash"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    data = await state.get_data()
    key = data.get("editing_setting_key")

    if not key:
        await state.clear()
        return

    value = message.text.strip()
    await SettingsDAO.set(session, key, value)
    await state.clear()

    await message.answer(
        f"✅ <b>{key}</b> yangilandi!\n\n"
        f"Yangi qiymat: <code>{value}</code>",
        parse_mode="HTML",
        reply_markup=get_admin_menu_kb(),
    )


@router.callback_query(F.data == "back_admin", IsAdmin())
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    """Admin panelga qaytish"""
    await state.clear()
    await callback.message.edit_text(
        "🔐 <b>Admin Panel</b>\n\nQuyidagi menyudan tanlang 👇",
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================
# ADMINLAR BOSHQARUVI
# ============================================

@router.message(F.text == "👑 Adminlar", IsAdmin())
async def admin_list_manage(message: Message, session: AsyncSession):
    """Barcha adminlarni ko'rish va boshqarish"""
    db_admins = await UserDAO.get_all_admins(session)

    text = (
        "👑 <b>Bot Adminlari Ro'yxati</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "⭐ <b>Asosiy Super Adminlar (.env):</b>\n"
    )
    for tg_id in settings.admin_ids:
        text += f"• <code>{tg_id}</code> (Super Admin)\n"

    text += "\n👥 <b>Tayinlangan Adminlar:</b>\n"
    if db_admins:
        for adm in db_admins:
            uname = f" (@{adm.username})" if adm.username else ""
            text += f"• {adm.full_name}{uname} — <code>{adm.telegram_id}</code>\n"
    else:
        text += "<i>Hozircha qo'shimcha adminlar yo'q.</i>\n"

    text += (
        "\n━━━━━━━━━━━━━━━━━━\n"
        "Yangi admin qo'shish uchun quyidagi tugmani bosing 👇"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Yangi Admin qo'shish (ID orqali)", callback_data="adm_add_admin_start")

    # Mavjud DB adminlarini o'chirish tugmalari
    for adm in db_admins:
        if adm.telegram_id not in settings.admin_ids:
            builder.button(
                text=f"❌ O'chirish: {adm.full_name[:12]}",
                callback_data=f"adm_remove_admin_{adm.id}",
            )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_admin"))

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data == "adm_add_admin_start", IsAdmin())
async def admin_add_admin_start(callback: CallbackQuery, state: FSMContext):
    """Yangi admin qo'shish — ID kiritish"""
    await state.set_state(AdminStates.add_admin_id)
    await callback.message.answer(
        "👑 <b>Yangi Admin qo'shish</b>\n\n"
        "Foydalanuvchining Telegram ID raqamini kiriting:\n"
        "(Foydalanuvchi o'z ID sini @userinfobot dan bilib olishi mumkin)",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.add_admin_id, IsAdmin())
async def admin_add_admin_save(message: Message, state: FSMContext, session: AsyncSession):
    """Yangi adminni saqlash"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Iltimos, faqat raqamli Telegram ID kiriting (masalan: 123456789):")
        return

    target_tg_id = int(text)

    # Foydalanuvchini olish yoki yaratish
    user = await UserDAO.get_by_telegram_id(session, target_tg_id)
    if not user:
        user, _ = await UserDAO.get_or_create(
            session=session,
            telegram_id=target_tg_id,
            full_name=f"Admin {target_tg_id}",
        )

    await UserDAO.set_admin(session, user.id, True)
    await state.clear()

    await message.answer(
        f"✅ <b>Muvaffaqiyatli!</b>\n\n"
        f"👤 {user.full_name} (ID: <code>{target_tg_id}</code>) bot administratori etib tayinlandi!\n\n"
        f"U endi botda /admin buyrug'idan foydalana oladi.",
        parse_mode="HTML",
        reply_markup=get_admin_menu_kb(),
    )


@router.callback_query(F.data.startswith("adm_remove_admin_"), IsAdmin())
async def admin_remove_admin(callback: CallbackQuery, session: AsyncSession):
    """Adminlikdan olish"""
    user_id = int(callback.data.split("_")[-1])
    user = await UserDAO.get_by_id(session, user_id)

    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
        return

    if user.telegram_id in settings.admin_ids:
        await callback.answer("⚠️ Bu asosiy Super Admin (.env), uni o'chirib bo'lmaydi!", show_alert=True)
        return

    await UserDAO.set_admin(session, user_id, False)
    await callback.answer(f"❌ {user.full_name} adminlikdan olindi!", show_alert=True)
    await callback.message.edit_text("❌ Admin olib tashlandi.")


# ============================================
# ADMINLAR GURUHI (ANIQLASH, TANLASH VA BOSHQARISH)
# ============================================

async def register_detected_group(session: AsyncSession, group_id: int, title: str, username: str = None):
    """Bot a'zo bo'lgan guruhni xotiraga saqlash"""
    raw = await SettingsDAO.get(session, "known_admin_groups", "[]")
    try:
        groups = json.loads(raw)
        if not isinstance(groups, list):
            groups = []
    except Exception:
        groups = []

    updated = False
    for g in groups:
        if g.get("id") == group_id:
            g["title"] = title or g.get("title", f"Guruh {group_id}")
            if username:
                g["username"] = username
            updated = True
            break

    if not updated:
        groups.append({
            "id": group_id,
            "title": title or f"Guruh {group_id}",
            "username": username or "",
        })

    await SettingsDAO.set(session, "known_admin_groups", json.dumps(groups, ensure_ascii=False), "Bot ulangan guruhlar ro'yxati")


async def get_detected_groups(session: AsyncSession) -> list:
    """Bot aniqlagan guruhlar ro'yxatini olish"""
    raw = await SettingsDAO.get(session, "known_admin_groups", "[]")
    try:
        groups = json.loads(raw)
        return groups if isinstance(groups, list) else []
    except Exception:
        return []


@router.my_chat_member()
async def bot_group_membership_update(update: ChatMemberUpdated, session: AsyncSession):
    """Bot guruhga a'zo yoki admin bo'lib qo'shilganda avtomatik guruhni saqlash"""
    chat = update.chat
    if chat.type in ("group", "supergroup"):
        if update.new_chat_member.status in ("administrator", "member"):
            await register_detected_group(session, chat.id, chat.title, chat.username)
            try:
                await update.bot.send_message(
                    chat_id=chat.id,
                    text=(
                        f"🔔 <b>SMM Bot guruhga muvaffaqiyatli ulandi!</b>\n\n"
                        f"🏢 Guruh: <b>{chat.title}</b>\n"
                        f"ID: <code>{chat.id}</code>\n\n"
                        f"Ushbu guruhni buyurtmalar va to'lovlar uchun asosiy qilish uchun:\n"
                        f"Guruhda <code>/setgroup</code> deb yozing yoki botdagi Admin Panel -> <b>'🏢 Adminlar Guruhi'</b> bo'limidan bitta bosish bilan tanlang! ✅"
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass


@router.message(F.chat.type.in_({"group", "supergroup"}), F.text.startswith("/setgroup"))
async def group_setgroup_command(message: Message, session: AsyncSession):
    """Guruhda /setgroup buyrug'i yuborilganda uni darhol buyurtmalar guruhi etib belgilash"""
    chat = message.chat
    await register_detected_group(session, chat.id, chat.title, chat.username)
    await SettingsDAO.set(session, "order_group_id", str(chat.id), "Buyurtmalar guruhi ID si")

    await message.reply(
        f"✅ <b>Ushbu guruh Buyurtmalar va To'lovlar guruhi etib belgilandi!</b>\n\n"
        f"🏢 Guruh: <b>{chat.title}</b>\n"
        f"ID: <code>{chat.id}</code>\n\n"
        f"Barcha yangi buyurtmalar va to'lov bildirishnomalari endi shu yerga yuboriladi! 🚀",
        parse_mode="HTML",
    )


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def group_auto_detect_message(message: Message, session: AsyncSession):
    """Guruhda yozilgan har qanday xabardan guruhni avtomatik xotiraga olish"""
    chat = message.chat
    if chat and chat.type in ("group", "supergroup"):
        await register_detected_group(session, chat.id, chat.title, chat.username)


async def _render_order_group_panel(target_msg, session: AsyncSession, is_edit: bool = False):
    from keyboards.inline import get_admin_order_group_kb
    from services.notification import get_order_group_id

    active_group_id = await get_order_group_id()
    detected_groups = await get_detected_groups(session)

    active_title = "Belgilanmagan (Xabarlar shaxsiy chatga boradi)"
    for g in detected_groups:
        if g.get("id") == active_group_id:
            active_title = g.get("title", f"Guruh {active_group_id}")
            break
    if active_group_id and active_group_id != 0 and active_title.startswith("Belgilanmagan"):
        active_title = f"Guruh ID: {active_group_id}"

    status_icon = "✅" if (active_group_id and active_group_id != 0) else "⚠️"

    text = (
        "🏢 <b>Buyurtmalar va To'lovlar Guruhi</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"📌 <b>Hozirgi ulangan guruh:</b>\n"
        f"{status_icon} <b>{active_title}</b> (<code>{active_group_id or 0}</code>)\n\n"
    )

    if detected_groups:
        text += (
            "📋 <b>Bot a'zo bo'lgan guruhlar ro'yxati:</b>\n"
            "Buyurtmalar tushishi kerak bo'lgan guruh ustiga bosing 👇\n"
        )
    else:
        text += (
            "ℹ️ <b>Guruhni ulash juda oson:</b>\n"
            "1. Botni adminlar guruhingizga qo'shing va <b>ADMIN</b> qiling.\n"
            "2. Guruhda <code>/setgroup</code> deb yozing yoki istalgan xabar yuboring.\n"
            "3. Bot guruhni darhol tanib oladi va bu yerda tanlash tugmasi paydo bo'ladi!\n"
        )

    kb = get_admin_order_group_kb(detected_groups=detected_groups, active_group_id=active_group_id)

    if is_edit:
        try:
            await target_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await target_msg.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target_msg.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(F.text == "🏢 Adminlar Guruhi", IsAdmin())
async def admin_group_manage(message: Message, session: AsyncSession):
    """Adminlar / Buyurtmalar guruhini tanlash va boshqarish"""
    await _render_order_group_panel(message, session, is_edit=False)


@router.callback_query(F.data.startswith("adm_select_grp_"), IsAdmin())
async def admin_select_group_cb(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Aniqlangan guruhlar ro'yxatidan guruhni tanlash"""
    await callback.answer()
    group_id = int(callback.data.replace("adm_select_grp_", ""))

    await SettingsDAO.set(session, "order_group_id", str(group_id), "Buyurtmalar guruhi ID si")

    grp_title = ""
    try:
        chat = await bot.get_chat(group_id)
        grp_title = chat.title or ""
        await bot.send_message(
            chat_id=group_id,
            text="🔔 <b>SMM Bot bildirishnomasi:</b>\nUshbu guruh muvaffaqiyatli asosiy Buyurtmalar va To'lovlar guruhi etib tanlandi! ✅",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await callback.answer(f"✅ Guruh tanlandi: {grp_title or group_id}!", show_alert=True)
    await _render_order_group_panel(callback.message, session, is_edit=True)


@router.callback_query(F.data == "adm_refresh_groups", IsAdmin())
async def admin_refresh_groups_cb(callback: CallbackQuery, session: AsyncSession):
    """Guruhlar ro'yxatini yangilash"""
    await callback.answer("🔄 Guruhlar ro'yxati yangilandi!")
    await _render_order_group_panel(callback.message, session, is_edit=True)


@router.callback_query(F.data == "adm_set_group_id", IsAdmin())
async def admin_set_group_id_start(callback: CallbackQuery, state: FSMContext):
    """Guruh ID sini qo'lda kiritish — boshlanish"""
    await state.set_state(AdminStates.set_order_group_id)
    await callback.message.answer(
        "🏢 <b>Guruh ID sini kiriting:</b>\n\n"
        "Masalan: <code>-1001234567890</code>\n\n"
        "Yoki oddiygina bot bor guruhda <code>/setgroup</code> buyrug'ini yuborsangiz o'zi ulanadi!",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.set_order_group_id, IsAdmin())
async def admin_save_group_id(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    """Guruh ID sini qo'lda saqlash"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    text_val = message.text.strip()
    try:
        group_id = int(text_val)
    except ValueError:
        await message.answer("❌ Iltimos, faqat to'g'ri sonli ID kiriting (masalan: <code>-1001234567890</code>):", parse_mode="HTML")
        return

    await SettingsDAO.set(session, "order_group_id", str(group_id), "Buyurtmalar guruhi ID si")
    await state.clear()

    test_ok = False
    try:
        chat = await bot.get_chat(group_id)
        await register_detected_group(session, group_id, chat.title, chat.username)
        await bot.send_message(
            chat_id=group_id,
            text="🔔 <b>SMM Bot bildirishnomasi:</b>\nUshbu guruh buyurtmalar va to'lovlar uchun muvaffaqiyatli ulandi! ✅",
            parse_mode="HTML",
        )
        test_ok = True
    except Exception:
        pass

    result_text = f"✅ <b>Admin guruhi muvaffaqiyatli saqlandi!</b>\n\n🏢 Guruh ID: <code>{group_id}</code>\n"
    if test_ok:
        result_text += "📬 Guruhga test xabari muvaffaqiyatli yuborildi! ✅"
    else:
        result_text += "⚠️ <i>Eslatma: Guruhga test xabar yuborilmadi. Bot guruhga admin qilib qo'shilganini tekshiring!</i>"

    await message.answer(result_text, parse_mode="HTML", reply_markup=get_admin_menu_kb())


@router.callback_query(F.data == "adm_test_group_msg", IsAdmin())
async def admin_test_group_msg(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Guruhga test xabar yuborish"""
    from services.notification import get_order_group_id
    group_id = await get_order_group_id()

    if not group_id or group_id == 0:
        await callback.answer("⚠️ Guruh sozlanmagan!", show_alert=True)
        return

    try:
        await bot.send_message(
            chat_id=group_id,
            text="🔔 <b>Test xabari:</b>\nSMM Bot admin guruhi bilan aloqa to'liq ishlayapti! ✅",
            parse_mode="HTML",
        )
        await callback.answer("✅ Guruhga test xabari muvaffaqiyatli bordi!", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Xato: Bot guruhda admin emas yoki ID noto'g'ri ({e})", show_alert=True)


@router.callback_query(F.data == "adm_clear_group_id", IsAdmin())
async def admin_clear_group_id(callback: CallbackQuery, session: AsyncSession):
    """Guruhni o'chirish"""
    await SettingsDAO.set(session, "order_group_id", "0", "Buyurtmalar guruhi ID si")
    await callback.answer("🗑 Guruh sozlamasi o'chirildi! Endi xabarlar shaxsiy adminlarga boradi.", show_alert=True)
    await _render_order_group_panel(callback.message, session, is_edit=True)


# ============================================
# MAJBURIY OBUNA BOSHQARUVI
# ============================================

async def _get_current_channels(session: AsyncSession) -> list:
    db_channels = await SettingsDAO.get(session, "mandatory_channels", "")
    if db_channels.strip():
        return [ch.strip() for ch in db_channels.split(",") if ch.strip()]
    return list(settings.mandatory_channels)


@router.message(F.text == "📢 Majburiy Obuna", IsAdmin())
async def admin_subscription_manage(message: Message, session: AsyncSession):
    """Majburiy obuna kanallarini boshqarish"""
    channels = await _get_current_channels(session)

    text = (
        "📢 <b>Majburiy Obuna Sozlamalari</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Foydalanuvchilar botdan foydalanishdan oldin quyidagi kanallarga a'zo bo'lishi shart:\n\n"
    )

    if channels:
        for i, ch in enumerate(channels, 1):
            text += f"{i}. 📢 <b>{ch}</b>\n"
    else:
        text += "<i>Hozircha majburiy kanallar belgilanmagan (Obuna talab qilinmaydi).</i>\n"

    text += (
        "\n━━━━━━━━━━━━━━━━━━\n"
        "Kanal qo'shish yoki o'chirish uchun quyidagilardan foydalaning 👇"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Yangi kanal qo'shish", callback_data="adm_add_channel_start")

    # Har bir kanalni o'chirish tugmasi
    for i, ch in enumerate(channels):
        builder.button(
            text=f"❌ O'chirish: {ch}",
            callback_data=f"adm_del_chan_{i}",
        )

    if channels:
        builder.button(text="🗑 Barcha kanallarni tozalash", callback_data="adm_clear_channels")

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_admin"))

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data == "adm_add_channel_start", IsAdmin())
async def admin_add_channel_start(callback: CallbackQuery, state: FSMContext):
    """Kanal qo'shish — boshlanish"""
    await state.set_state(AdminStates.add_mandatory_channel)
    await callback.message.answer(
        "📢 <b>Yangi majburiy kanal qo'shish</b>\n\n"
        "Kanalning username ini (@ bilan) yoki havolasini yuboring:\n"
        "Masalan: <code>@mening_kanalim</code> yoki <code>-1001234567890</code>\n\n"
        "⚠️ <b>Muhim:</b> Bot ushbu kanalda <b>ADMIN</b> bo'lishi kerak, aks holda obunani tekshira olmaydi!",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.add_mandatory_channel, IsAdmin())
async def admin_add_channel_save(message: Message, state: FSMContext, session: AsyncSession):
    """Kanalni saqlash"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    raw_input = message.text.strip()
    # Tozalash
    if raw_input.startswith("https://t.me/"):
        channel = "@" + raw_input.replace("https://t.me/", "").replace("/", "").strip()
    elif raw_input.startswith("t.me/"):
        channel = "@" + raw_input.replace("t.me/", "").replace("/", "").strip()
    elif not raw_input.startswith("@") and not raw_input.startswith("-"):
        channel = "@" + raw_input
    else:
        channel = raw_input

    channels = await _get_current_channels(session)
    if channel not in channels:
        channels.append(channel)

    new_val = ",".join(channels)
    await SettingsDAO.set(session, "mandatory_channels", new_val, "Majburiy obuna kanallari")
    await state.clear()

    await message.answer(
        f"✅ <b>Kanal muvaffaqiyatli qo'shildi!</b>\n\n"
        f"📢 {channel}\n\n"
        f"Endi yangi foydalanuvchilar botdan foydalanishdan oldin ushbu kanalga a'zo bo'lishi kerak bo'ladi.\n"
        f"(Eslatma: Bot kanalda admin bo'lishi shart!)",
        parse_mode="HTML",
        reply_markup=get_admin_menu_kb(),
    )


@router.callback_query(F.data.startswith("adm_del_chan_"), IsAdmin())
async def admin_delete_channel(callback: CallbackQuery, session: AsyncSession):
    """Kanalni o'chirish"""
    idx = int(callback.data.split("_")[-1])
    channels = await _get_current_channels(session)

    if 0 <= idx < len(channels):
        removed = channels.pop(idx)
        new_val = ",".join(channels)
        await SettingsDAO.set(session, "mandatory_channels", new_val, "Majburiy obuna kanallari")
        await callback.answer(f"❌ {removed} kanali o'chirildi!", show_alert=True)
    else:
        await callback.answer("❌ Kanal topilmadi!", show_alert=True)

    await callback.message.edit_text("✅ Kanal ro'yxatdan olib tashlandi.")


@router.callback_query(F.data == "adm_clear_channels", IsAdmin())
async def admin_clear_channels(callback: CallbackQuery, session: AsyncSession):
    """Barcha kanallarni tozalash"""
    await SettingsDAO.set(session, "mandatory_channels", "", "Majburiy obuna kanallari")
    await callback.answer("🗑 Barcha majburiy kanallar tozalandi! Obuna o'chirildi.", show_alert=True)
    await callback.message.edit_text("🗑 Barcha majburiy kanallar tozalandi. Obuna talab qilinmaydi.")


# ============================================
# ADMINLAR BOSHQARUVI (QO'SHISH / CHIQARISH)
# ============================================

async def _render_admins_panel(target_msg, session: AsyncSession, is_edit: bool = False):
    from keyboards.inline import get_admins_manage_kb

    db_admins = await UserDAO.get_all_admins(session)
    super_admins_text = "\n".join([f"• 👑 <code>{adm_id}</code> (Super Admin)" for adm_id in settings.admin_ids])

    text = (
        "👑 <b>Adminlar Boshqaruvi</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "⭐ <b>Asosiy Super Adminlar (.env):</b>\n"
        f"{super_admins_text}\n\n"
        "👥 <b>Qo'shimcha Adminlar (Bazadagi):</b>\n"
    )

    if db_admins:
        for i, adm in enumerate(db_admins, 1):
            username_part = f" (@{adm.username})" if adm.username else ""
            text += f"{i}. 👑 <b>{adm.full_name}</b>{username_part} — ID: <code>{adm.telegram_id}</code>\n"
    else:
        text += "<i>Hozircha qo'shimcha adminlar tayinlanmagan.</i>\n"

    text += (
        "\n━━━━━━━━━━━━━━━━━━\n"
        "Yangi admin tayinlash yoki adminlikdan chiqarish uchun quyidagi tugmalardan foydalaning 👇"
    )

    kb = get_admins_manage_kb(db_admins)
    if is_edit:
        try:
            await target_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await target_msg.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target_msg.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(F.text == "👑 Adminlar", IsAdmin())
async def admin_admins_manage(message: Message, session: AsyncSession):
    """Adminlar ro'yxati va boshqaruvi"""
    await _render_admins_panel(message, session, is_edit=False)


@router.callback_query(F.data == "adm_admins_manage", IsAdmin())
async def admin_admins_manage_cb(callback: CallbackQuery, session: AsyncSession):
    """Adminlar ro'yxati callback"""
    await callback.answer()
    await _render_admins_panel(callback.message, session, is_edit=True)


@router.callback_query(F.data == "adm_add_admin_start", IsAdmin())
async def admin_add_admin_start(callback: CallbackQuery, state: FSMContext):
    """Yangi admin qo'shish — boshlanish"""
    await callback.answer()
    await state.set_state(AdminStates.add_admin_id)
    await callback.message.answer(
        "👑 <b>Yangi admin tayinlash</b>\n\n"
        "Admin qilmoqchi bo'lgan foydalanuvchining:\n"
        "• <b>Telegram ID</b> raqamini (masalan: <code>123456789</code>)\n"
        "• Yoki <b>@username</b>ini kiriting:\n\n"
        "ℹ️ <i>Eslatma: Foydalanuvchi avval ushbu botga kirib /start bosgan bo'lishi shart.</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )


@router.message(AdminStates.add_admin_id, IsAdmin())
async def admin_add_admin_save(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    """Yangi adminni saqlash"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    query = message.text.strip().replace("https://t.me/", "").replace("t.me/", "")
    user = None

    if query.isdigit():
        user = await UserDAO.get_by_telegram_id(session, int(query))
        if not user:
            user = await UserDAO.get_by_id(session, int(query))
    else:
        clean_username = query.replace("@", "").strip()
        users = await UserDAO.search_users(session, clean_username)
        if users:
            user = users[0]

    if not user:
        await message.answer(
            "❌ <b>Foydalanuvchi topilmadi!</b>\n\n"
            "U avval botga kirib /start bosgan bo'lishi kerak. Tekshirib qaytadan kiriting yoki ❌ Bekor qilish ni bosing:",
            parse_mode="HTML",
            reply_markup=get_cancel_kb(),
        )
        return

    if user.is_admin or (user.telegram_id in settings.admin_ids):
        await state.clear()
        await message.answer(
            f"⚠️ <b>{user.full_name}</b> allaqachon bot administratori hisoblanadi!",
            parse_mode="HTML",
            reply_markup=get_admin_menu_kb(),
        )
        return

    await UserDAO.set_admin(session, user.id, True)
    await state.clear()

    # Yangi adminga bildirishnoma
    try:
        await notify_user(
            bot=bot,
            user_telegram_id=user.telegram_id,
            text=(
                f"👑 <b>Tabriklaymiz! Sizga botda ADMIN huquqi berildi!</b>\n\n"
                f"Endi siz /admin buyrug'i orqali admin boshqaruv paneliga kirishingiz va botni boshqarishingiz mumkin."
            ),
        )
    except Exception as e:
        logger.error(f"Yangi adminga xabar yuborishda xato: {e}")

    await message.answer(
        f"✅ <b>{user.full_name}</b> muvaffaqiyatli ADMIN etib tayinlandi!\n\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Unga adminlik huquqi berildi va bildirishnoma yuborildi. ✅",
        parse_mode="HTML",
        reply_markup=get_admin_menu_kb(),
    )


@router.callback_query(F.data.startswith("adm_remove_admin_"), IsAdmin())
async def admin_remove_admin_cb(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Adminlikdan chiqarish"""
    await callback.answer()
    user_id = int(callback.data.split("_")[-1])
    user = await UserDAO.get_by_id(session, user_id)

    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
        return

    if user.telegram_id in settings.admin_ids:
        await callback.answer("⚠️ Super Adminni (.env) adminlikdan chiqarib bo'lmaydi!", show_alert=True)
        return

    await UserDAO.set_admin(session, user_id, False)

    # Foydalanuvchiga xabar
    try:
        await notify_user(
            bot=bot,
            user_telegram_id=user.telegram_id,
            text="⚠️ <b>Sizning botdagi adminlik huquqingiz to'xtatildi.</b>",
        )
    except Exception:
        pass

    await callback.answer(f"❌ {user.full_name} adminlikdan chiqarildi!", show_alert=True)
    await _render_admins_panel(callback.message, session, is_edit=True)
