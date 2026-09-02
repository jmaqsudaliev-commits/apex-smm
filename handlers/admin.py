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
from decimal import Decimal

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
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
async def admin_users(message: Message, state: FSMContext):
    """Foydalanuvchini qidirish"""
    await state.set_state(AdminStates.search_user)
    await message.answer(
        "🔍 <b>Foydalanuvchini qidirish</b>\n\n"
        "Telegram ID, username yoki ismni kiriting:",
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
        # ID bilan bevosita qidirish
        if query.isdigit():
            user = await UserDAO.get_by_telegram_id(session, int(query))
            if user:
                users = [user]

    if not users:
        await message.answer("❌ Foydalanuvchi topilmadi. Qaytadan qidiring:")
        return

    await state.clear()

    for user in users[:5]:
        ban_status = "🔴 Banlangan" if user.is_banned else "🟢 Faol"
        is_user_adm = user.is_admin or (user.telegram_id in settings.admin_ids)
        role_status = "👑 Admin" if is_user_adm else "👤 Foydalanuvchi"
        text = (
            f"👤 <b>{user.full_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: <code>{user.telegram_id}</code>\n"
        )
        if user.username:
            text += f"📎 @{user.username}\n"
        text += (
            f"💰 Balans: {format_price(user.balance)}\n"
            f"📦 Buyurtmalar: {user.total_orders}\n"
            f"💸 Sarflagan: {format_price(user.total_spent)}\n"
            f"📋 Holat: {ban_status} | <b>{role_status}</b>\n"
            f"📅 Ro'yxatdan: {format_datetime(user.created_at)}\n"
        )
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_admin_user_kb(user.id, user.is_banned, is_user_adm),
        )

    await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())


@router.callback_query(F.data.startswith("adm_set_bal_"), IsAdmin())
async def admin_set_balance_start(callback: CallbackQuery, state: FSMContext):
    """Balans o'zgartirish — boshlanish"""
    user_id = int(callback.data.split("_")[-1])
    await state.set_state(AdminStates.set_user_balance)
    await state.update_data(target_user_id=user_id)

    await callback.message.answer(
        "💰 Yangi balansni kiriting (so'mda):\n"
        "Yoki +10000 (qo'shish) / -5000 (ayirish)",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()


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
            # Qo'shish/ayirish
            amount = Decimal(text)
            user = await UserDAO.update_balance(session, user_id, amount)
            action = "qo'shildi" if amount > 0 else "ayirildi"
        else:
            # To'g'ridan-to'g'ri o'rnatish
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
async def admin_ban_user(callback: CallbackQuery, session: AsyncSession):
    """Foydalanuvchini ban/unban qilish"""
    user_id = int(callback.data.split("_")[-1])
    user = await UserDAO.get_by_id(session, user_id)

    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
        return

    new_status = not user.is_banned
    await UserDAO.ban_user(session, user_id, new_status)

    status_text = "🔴 Banlandi" if new_status else "🟢 Ban olib tashlandi"
    await callback.answer(f"{status_text}: {user.full_name}", show_alert=True)

    is_user_adm = user.is_admin or (user.telegram_id in settings.admin_ids)
    await callback.message.edit_reply_markup(
        reply_markup=get_admin_user_kb(user_id, new_status, is_user_adm)
    )


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
async def admin_add_service_max(message: Message, state: FSMContext, session: AsyncSession):
    """Yangi xizmat — maximum va saqlash"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🔐 Admin Panel", reply_markup=get_admin_menu_kb())
        return

    try:
        max_qty = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return

    data = await state.get_data()
    await state.clear()

    service = await ServiceDAO.create(
        session=session,
        category_id=data["new_service_category_id"],
        name=data["new_service_name"],
        price_per_1000=Decimal(data["new_service_price"]),
        min_quantity=data["new_service_min"],
        max_quantity=max_qty,
    )

    await message.answer(
        f"✅ Xizmat qo'shildi!\n\n"
        f"📦 {service.name}\n"
        f"💰 Narx: {format_price(service.price_per_1000)} / 1000\n"
        f"📊 Miqdor: {format_number(service.min_quantity)} — {format_number(service.max_quantity)}",
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

@router.message(F.text == "📦 Buyurtmalar", IsAdmin())
async def admin_orders(message: Message, session: AsyncSession):
    """Kutilayotgan buyurtmalar"""
    from utils.helpers import format_order_text

    pending = await OrderDAO.get_pending_orders(session)

    if not pending:
        await message.answer(
            "📦 <b>Buyurtmalar</b>\n\n✅ Kutilayotgan buyurtmalar yo'q.",
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"📦 <b>Kutilayotgan buyurtmalar: {len(pending)} ta</b>",
        parse_mode="HTML",
    )

    for order in pending[:10]:
        service_name = order.service.name if order.service else "—"
        user = await UserDAO.get_by_id(session, order.user_id)
        user_info = f"{user.full_name} ({user.telegram_id})" if user else "Noma'lum"

        text = (
            f"📦 <b>Buyurtma #{order.id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 Mijoz: {user_info}\n"
            f"📦 Xizmat: {service_name}\n"
            f"🔗 Havola: {order.target_link}\n"
            f"📊 Miqdor: {format_number(order.quantity)}\n"
            f"💰 Narx: {format_price(order.total_price)}\n"
            f"📅 {format_datetime(order.created_at)}\n"
        )

        from keyboards.inline import get_admin_order_kb
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_admin_order_kb(order.id),
        )


@router.callback_query(F.data.startswith("adm_complete_"), IsAdmin())
async def admin_complete_order(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Buyurtmani bajarildi deb belgilash"""
    order_id = int(callback.data.split("_")[-1])
    order = await OrderDAO.update_status(session, order_id, OrderStatus.COMPLETED)

    if not order:
        await callback.answer("❌ Buyurtma topilmadi!", show_alert=True)
        return

    user = await UserDAO.get_by_id(session, order.user_id)
    service_name = order.service.name if order.service else "—"

    # Foydalanuvchiga xabar
    if user:
        await notify_user(
            bot=bot,
            user_telegram_id=user.telegram_id,
            text=(
                f"✅ <b>Buyurtmangiz bajarildi!</b>\n\n"
                f"📦 #{order.id} — {service_name}\n"
                f"🔗 {order.target_link}\n"
                f"📊 Miqdor: {format_number(order.quantity)}\n\n"
                f"Xizmatimizdan foydalanganingiz uchun rahmat! 🙏"
            ),
        )

    await callback.message.edit_text(
        f"✅ <b>BUYURTMA BAJARILDI</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 #{order_id} — {service_name}\n"
        f"👤 Admin: {callback.from_user.full_name}\n"
        f"📅 {format_datetime(order.updated_at)}",
        parse_mode="HTML",
    )
    await callback.answer("✅ Bajarildi!", show_alert=True)


@router.callback_query(F.data.startswith("adm_progress_"), IsAdmin())
async def admin_progress_order(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Buyurtmani jarayonda deb belgilash"""
    order_id = int(callback.data.split("_")[-1])
    order = await OrderDAO.update_status(session, order_id, OrderStatus.IN_PROGRESS)

    if not order:
        await callback.answer("❌ Buyurtma topilmadi!", show_alert=True)
        return

    user = await UserDAO.get_by_id(session, order.user_id)
    if user:
        await notify_user(
            bot=bot,
            user_telegram_id=user.telegram_id,
            text=(
                f"🔄 <b>Buyurtmangiz jarayonda!</b>\n\n"
                f"📦 #{order.id}\n"
                f"Tez orada bajariladi. Kuting..."
            ),
        )

    await callback.answer("🔄 Jarayonga o'tkazildi!", show_alert=True)


@router.callback_query(F.data.startswith("adm_cancel_"), IsAdmin())
async def admin_cancel_order(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Buyurtmani bekor qilish va pulni qaytarish"""
    order_id = int(callback.data.split("_")[-1])
    order = await OrderDAO.get_by_id(session, order_id)

    if not order:
        await callback.answer("❌ Buyurtma topilmadi!", show_alert=True)
        return

    # Buyurtmani bekor qilish
    await OrderDAO.update_status(session, order_id, OrderStatus.CANCELLED)

    # Pulni qaytarish
    user = await UserDAO.update_balance(session, order.user_id, order.total_price)

    service_name = order.service.name if order.service else "—"

    # Foydalanuvchiga xabar
    if user:
        await notify_user(
            bot=bot,
            user_telegram_id=user.telegram_id,
            text=(
                f"❌ <b>Buyurtmangiz bekor qilindi!</b>\n\n"
                f"📦 #{order.id} — {service_name}\n"
                f"💰 {format_price(order.total_price)} balansingizga qaytarildi.\n"
                f"💵 Yangi balans: {format_price(user.balance)}"
            ),
        )

    await callback.message.edit_text(
        f"❌ <b>BUYURTMA BEKOR QILINDI</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 #{order_id} — {service_name}\n"
        f"💰 {format_price(order.total_price)} qaytarildi\n"
        f"👤 Admin: {callback.from_user.full_name}",
        parse_mode="HTML",
    )
    await callback.answer("❌ Bekor qilindi, pul qaytarildi!", show_alert=True)


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
        "referral_bonus_percent": "🔗 Referal bonus",
        "min_payment_amount": "💰 Min to'lov summasi",
        "stars_rate": "⭐ Stars kursi",
        "payment_card_click": "💳 Click karta",
        "payment_card_payme": "💳 Payme karta",
        "payment_card_holder": "👤 Karta egasi",
        "support_username": "📞 Support",
        "mandatory_channels": "📢 Majburiy kanallar",
        "order_group_id": "📦 Buyurtmalar guruhi",
        "welcome_bonus": "🎁 Xush kelibsiz bonusi",
    }

    for key, label in settings_display.items():
        val = all_settings.get(key, {}).get("value", "—")
        if key == "referral_bonus_percent":
            val = f"{val}%"
        elif key in ("min_payment_amount", "stars_rate", "welcome_bonus"):
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
        "referral_bonus_percent": "Referal bonus foizini kiriting (masalan: 5)",
        "min_payment_amount": "Minimum to'lov summasini kiriting so'mda (masalan: 5000)",
        "stars_rate": "1 Telegram Star = necha so'm (masalan: 1500)",
        "payment_card_click": "Click karta raqamini kiriting (masalan: 8600 1234 5678 9012)",
        "payment_card_payme": "Payme karta raqamini kiriting",
        "payment_card_holder": "Karta egasining to'liq ismini kiriting",
        "support_username": "Support username kiriting (@ siz)",
        "mandatory_channels": "Kanallarni vergul bilan kiriting (masalan: kanal1,kanal2)\nBo'sh qoldiring = majburiy obuna o'chiriladi",
        "order_group_id": "Buyurtmalar guruhi ID sini kiriting\nGuruhga botni qo'shing va /id buyrug'ini yuboring",
        "welcome_bonus": "Yangi foydalanuvchiga beriladigan bonus (so'mda, 0 = yo'q)",
    }

    await state.set_state(AdminStates.broadcast_message)  # reuse state
    await state.update_data(editing_setting_key=key)

    from states.states import AdminStates as AS
    # Maxsus state ishlatamiz
    await state.set_data({"editing_setting_key": key})

    hint = hints.get(key, "Yangi qiymatni kiriting:")
    await callback.message.answer(
        f"✏️ <b>{key}</b>\n\n{hint}",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()

    # Custom state o'rnatamiz
    from aiogram.fsm.state import State
    await state.set_state(State("edit_bot_setting"))


@router.message(F.text != "❌ Bekor qilish", IsAdmin())
async def admin_save_setting(message: Message, state: FSMContext, session: AsyncSession):
    """Sozlamani saqlash (catch-all for settings edit)"""
    data = await state.get_data()
    key = data.get("editing_setting_key")

    if not key:
        return  # Bu handler faqat sozlama tahrirlashda ishlaydi

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
