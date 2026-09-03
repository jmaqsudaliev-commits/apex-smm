"""
Services Handler — Xizmatlar katalogi va buyurtma berish

Foydalanuvchi kategoriya tanlaydi → xizmat tanlaydi → havola kiritadi →
miqdor kiritadi → tasdiqlaydi → buyurtma yaratiladi → admin guruhga yuboriladi.
"""

from decimal import Decimal

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.dao import CategoryDAO, ServiceDAO, OrderDAO, UserDAO
from keyboards.inline import (
    get_categories_kb, get_services_kb,
    get_order_confirm_kb, get_back_kb,
)
from keyboards.reply import get_cancel_kb, get_main_menu_kb
from states.states import OrderStates
from utils.helpers import format_price, format_number, calculate_price
from services.notification import notify_new_order

router = Router()


# ============================================
# KATEGORIYA VA XIZMATLAR KO'RISH
# ============================================

@router.callback_query(F.data == "back_categories")
async def back_to_categories(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Kategoriyalarga qaytish"""
    await state.clear()
    categories = await CategoryDAO.get_all_active(session)
    await callback.message.edit_text(
        "🛒 <b>Xizmatlar katalogi</b>\n\n"
        "Quyidagi kategoriyalardan birini tanlang 👇",
        parse_mode="HTML",
        reply_markup=get_categories_kb(categories),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_"))
async def show_category_services(callback: CallbackQuery, session: AsyncSession):
    """Kategoriya tanlanganda — xizmatlar ro'yxati"""
    category_id = int(callback.data.split("_")[1])
    category = await CategoryDAO.get_by_id(session, category_id)

    if not category:
        await callback.answer("❌ Kategoriya topilmadi!", show_alert=True)
        return

    services = await ServiceDAO.get_by_category(session, category_id)

    if not services:
        await callback.answer("😔 Bu kategoriyada xizmatlar yo'q", show_alert=True)
        return

    await callback.message.edit_text(
        f"{category.emoji} <b>{category.name.replace(category.emoji, '').strip()}</b>\n\n"
        f"Xizmatni tanlang 👇",
        parse_mode="HTML",
        reply_markup=get_services_kb(services, category_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("svc_"))
async def show_service_detail(callback: CallbackQuery, session: AsyncSession):
    """Xizmat tanlanganda — tafsilotlar"""
    service_id = int(callback.data.split("_")[1])
    service = await ServiceDAO.get_by_id(session, service_id)

    if not service:
        await callback.answer("❌ Xizmat topilmadi!", show_alert=True)
        return

    # Narx formatlash
    if service.min_quantity == 1 and service.max_quantity == 1:
        price_text = format_price(service.price_per_1000)
        qty_text = "1 dona (belgilangan)"
    else:
        price_text = f"{format_price(service.price_per_1000)} / 1000 dona"
        qty_text = f"{format_number(service.min_quantity)} — {format_number(service.max_quantity)}"

    exec_time = service.execution_time or "10 daqiqa - 24 soat"
    text = (
        f"📦 <b>{service.name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
    )
    if service.description:
        text += f"📝 {service.description}\n\n"
    text += (
        f"💰 Narx: <b>{price_text}</b>\n"
        f"📊 Miqdor: {qty_text}\n"
        f"⏱ Bajarilish oralig'i: <b>{exec_time}</b>\n\n"
        f"🛒 Buyurtma berish uchun quyidagi tugmani bosing 👇"
    )

    from keyboards.inline import get_service_detail_kb
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_service_detail_kb(service_id),
    )
    await callback.answer()


@router.callback_query(F.data == "back_services")
async def back_to_services(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Xizmatlar ro'yxatiga qaytish"""
    await state.clear()
    # Kategoriyalarga qaytamiz
    categories = await CategoryDAO.get_all_active(session)
    await callback.message.edit_text(
        "🛒 <b>Xizmatlar katalogi</b>\n\n"
        "Quyidagi kategoriyalardan birini tanlang 👇",
        parse_mode="HTML",
        reply_markup=get_categories_kb(categories),
    )
    await callback.answer()


# ============================================
# BUYURTMA BERISH JARAYONI (FSM)
# ============================================

@router.callback_query(F.data.startswith("order_"))
async def start_order(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Buyurtma berish — 1-qadam: havola so'rash"""
    service_id = int(callback.data.split("_")[1])
    service = await ServiceDAO.get_by_id(session, service_id)

    if not service:
        await callback.answer("❌ Xizmat topilmadi!", show_alert=True)
        return

    # Foydalanuvchi balansini tekshirish
    user = await UserDAO.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
        return

    # Bir martalik xizmat (Premium, NFT, sovg'a va boshqalar)
    if service.min_quantity == 1 and service.max_quantity == 1:
        # Narx = price_per_1000 (to'liq narx)
        total_price = service.price_per_1000

        if user.balance < total_price:
            await callback.answer(
                f"❌ Balansingiz yetarli emas!\n"
                f"Kerak: {format_price(total_price)}\n"
                f"Balans: {format_price(user.balance)}",
                show_alert=True,
            )
            return

        await state.set_state(OrderStates.waiting_for_link)
        await state.update_data(
            service_id=service_id,
            service_name=service.name,
            quantity=1,
            total_price=str(total_price),
            execution_time=service.execution_time or "10 daqiqa - 24 soat",
            is_fixed=True,
        )

        await callback.message.edit_text(
            f"🛒 <b>Buyurtma: {service.name}</b>\n\n"
            f"💰 Narx: <b>{format_price(total_price)}</b>\n"
            f"⏱ Bajarilish oralig'i: <b>{service.execution_time or '10 daqiqa - 24 soat'}</b>\n\n"
            f"🔗 Iltimos, tegishli havola yoki ma'lumotni yuboring:\n"
            f"(Username, telefon raqam, yoki havola)",
            parse_mode="HTML",
        )
        await callback.message.answer(
            "🔗 Havola yoki ma'lumotni kiriting yoki ❌ Bekor qilish:",
            reply_markup=get_cancel_kb(),
        )
    else:
        # Oddiy xizmat — havola va miqdor so'raladi
        await state.set_state(OrderStates.waiting_for_link)
        await state.update_data(
            service_id=service_id,
            service_name=service.name,
            price_per_1000=str(service.price_per_1000),
            min_qty=service.min_quantity,
            max_qty=service.max_quantity,
            execution_time=service.execution_time or "10 daqiqa - 24 soat",
            is_fixed=False,
        )

        await callback.message.edit_text(
            f"🛒 <b>Buyurtma: {service.name}</b>\n\n"
            f"💰 Narx: {format_price(service.price_per_1000)} / 1000 dona\n"
            f"📊 Miqdor: {format_number(service.min_quantity)} — {format_number(service.max_quantity)}\n"
            f"⏱ Bajarilish oralig'i: <b>{service.execution_time or '10 daqiqa - 24 soat'}</b>\n\n"
            f"🔗 Iltimos, havolani yuboring:",
            parse_mode="HTML",
        )
        await callback.message.answer(
            "🔗 Havolani kiriting:", reply_markup=get_cancel_kb()
        )

    await callback.answer()


@router.message(OrderStates.waiting_for_link)
async def process_order_link(message: Message, state: FSMContext, session: AsyncSession):
    """Buyurtma — havola qabul qilish"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Buyurtma bekor qilindi.",
            reply_markup=get_main_menu_kb(),
        )
        return

    link = message.text.strip()
    if len(link) < 3:
        await message.answer("❌ Havola juda qisqa. Qaytadan kiriting:")
        return

    data = await state.get_data()
    await state.update_data(target_link=link)

    if data.get("is_fixed"):
        # Bir martalik xizmat — to'g'ridan-to'g'ri tasdiqlashga
        total_price = Decimal(data["total_price"])
        await state.set_state(OrderStates.waiting_for_confirm)

        text = (
            f"📋 <b>Buyurtma tafsilotlari</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 Xizmat: {data['service_name']}\n"
            f"🔗 Havola: {link}\n"
            f"💰 Narx: <b>{format_price(total_price)}</b>\n"
            f"⏱ Bajarilish oralig'i: <b>{data.get('execution_time', '10 daqiqa - 24 soat')}</b>\n\n"
            f"✅ Tasdiqlaysizmi?"
        )
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_order_confirm_kb(data["service_id"]),
        )
    else:
        # Oddiy xizmat — miqdor so'rash
        await state.set_state(OrderStates.waiting_for_quantity)
        min_qty = data["min_qty"]
        max_qty = data["max_qty"]

        await message.answer(
            f"✅ Havola qabul qilindi!\n\n"
            f"📊 Miqdorni kiriting ({format_number(min_qty)} — {format_number(max_qty)}):",
            parse_mode="HTML",
        )


@router.message(OrderStates.waiting_for_quantity)
async def process_order_quantity(message: Message, state: FSMContext, session: AsyncSession):
    """Buyurtma — miqdor qabul qilish"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Buyurtma bekor qilindi.",
            reply_markup=get_main_menu_kb(),
        )
        return

    try:
        quantity = int(message.text.strip().replace(" ", ""))
    except ValueError:
        await message.answer("❌ Iltimos, faqat raqam kiriting:")
        return

    data = await state.get_data()
    min_qty = data["min_qty"]
    max_qty = data["max_qty"]

    if quantity < min_qty or quantity > max_qty:
        await message.answer(
            f"❌ Miqdor {format_number(min_qty)} — {format_number(max_qty)} orasida bo'lishi kerak!"
        )
        return

    price_per_1000 = Decimal(data["price_per_1000"])
    total_price = calculate_price(price_per_1000, quantity)

    # Balans tekshirish
    user = await UserDAO.get_by_telegram_id(session, message.from_user.id)
    if user.balance < total_price:
        await message.answer(
            f"❌ <b>Balansingiz yetarli emas!</b>\n\n"
            f"💰 Kerak: {format_price(total_price)}\n"
            f"💵 Balans: {format_price(user.balance)}\n\n"
            f"💳 Balansni to'ldiring va qaytadan urinib ko'ring.",
            parse_mode="HTML",
            reply_markup=get_main_menu_kb(),
        )
        await state.clear()
        return

    await state.update_data(quantity=quantity, total_price=str(total_price))
    await state.set_state(OrderStates.waiting_for_confirm)

    text = (
        f"📋 <b>Buyurtma tafsilotlari</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Xizmat: {data['service_name']}\n"
        f"🔗 Havola: {data['target_link']}\n"
        f"📊 Miqdor: {format_number(quantity)}\n"
        f"💰 Narx: <b>{format_price(total_price)}</b>\n"
        f"⏱ Bajarilish oralig'i: <b>{data.get('execution_time', '10 daqiqa - 24 soat')}</b>\n\n"
        f"💵 Balansingiz: {format_price(user.balance)}\n"
        f"💵 Qoldiq: {format_price(user.balance - total_price)}\n\n"
        f"✅ Tasdiqlaysizmi?"
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_order_confirm_kb(data["service_id"]),
    )


# ============================================
# BUYURTMANI TASDIQLASH
# ============================================

@router.callback_query(F.data.startswith("confirm_order_"))
async def confirm_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    """Buyurtmani tasdiqlash va yaratish"""
    data = await state.get_data()

    if not data.get("service_id"):
        await callback.answer("❌ Buyurtma ma'lumotlari topilmadi!", show_alert=True)
        await state.clear()
        return

    user = await UserDAO.get_by_telegram_id(session, callback.from_user.id)
    total_price = Decimal(data["total_price"])

    # Balansni qayta tekshirish
    if user.balance < total_price:
        await callback.answer("❌ Balansingiz yetarli emas!", show_alert=True)
        await state.clear()
        return

    # Buyurtma yaratish
    order = await OrderDAO.create(
        session=session,
        user_id=user.id,
        service_id=data["service_id"],
        target_link=data.get("target_link", ""),
        quantity=data.get("quantity", 1),
        total_price=total_price,
    )

    # Foydalanuvchi balansini yangilangan holatini olish
    await session.refresh(user)

    exec_time = data.get("execution_time", "10 daqiqa - 24 soat")
    order_num = getattr(order, "order_number", None) or str(order.id)

    await state.clear()

    # Admin guruhga / adminlarga bildirishnoma
    await notify_new_order(
        bot=bot,
        order=order,
        user=user,
        service_name=data.get("service_name", ""),
        execution_time=exec_time,
    )

    client_text = (
        f"✅ <b>Buyurtmangiz muvaffaqiyatli qabul qilindi!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 <b>Buyurtma raqami:</b> <code>#{order_num}</code>\n"
        f"📦 <b>Xizmat turi:</b> {data.get('service_name', '')}\n"
        f"💰 <b>Xizmat narxi:</b> {format_price(total_price)}\n"
        f"📊 <b>Miqdor:</b> {format_number(data.get('quantity', 1))}\n"
        f"⏱ <b>Bajarilish oralig'i:</b> {exec_time}\n"
        f"🔗 <b>Havola:</b> {data.get('target_link', '')}\n"
        f"💵 <b>Qoldiq balansingiz:</b> {format_price(user.balance)}\n\n"
        f"🕐 <b>Holati:</b> 🕐 Kutilmoqda\n\n"
        f"ℹ️ <i>Buyurtmangiz tizim tomonidan qabul qilindi va ko'rsatilgan vaqt oralig'ida to'liq bajariladi.</i>\n\n"
        f"📋 Buyurtmangiz holatini istalgan vaqt <b>Buyurtmalarim</b> bo'limidan kuzatib borishingiz mumkin."
    )

    await callback.message.edit_text(
        client_text,
        parse_mode="HTML",
    )

    await callback.message.answer(
        "🏠 Asosiy menyu",
        reply_markup=get_main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    """Buyurtmani bekor qilish"""
    await state.clear()
    await callback.message.edit_text("❌ Buyurtma bekor qilindi.")
    await callback.message.answer(
        "🏠 Asosiy menyu",
        reply_markup=get_main_menu_kb(),
    )
    await callback.answer()
