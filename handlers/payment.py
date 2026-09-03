"""
Payment Handler — To'lov jarayoni

Foydalanuvchi to'lov usulini tanlaydi → summa kiritadi →
karta ma'lumotlarini ko'radi → screenshot yuboradi → admin guruhga yuboriladi.
Telegram Stars to'lovi ham qo'llab-quvvatlanadi.
"""

from decimal import Decimal

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.dao import UserDAO, PaymentDAO, SettingsDAO
from database.models import PaymentMethod
from keyboards.reply import get_cancel_kb, get_main_menu_kb
from keyboards.inline import get_payment_methods_kb
from states.states import PaymentStates
from utils.helpers import format_price
from services.notification import notify_new_payment

router = Router()


# ============================================
# TO'LOV USULI TANLASH
# ============================================

@router.callback_query(F.data == "topup_balance")
async def show_topup_methods(callback: CallbackQuery):
    """Balansni to'ldirish tugmasi bosilganda to'lov usullarini ko'rsatish"""
    text = (
        "💳 <b>Hisobni to'ldirish</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Quyidagi to'lov usullaridan birini tanlang 👇"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_payment_methods_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_balance")
async def back_to_balance(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Orqaga — balans xabariga qaytish"""
    await state.clear()
    user = await UserDAO.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    text = (
        f"💰 <b>Sizning balansingiz</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💵 Asosiy balans: <b>{format_price(user.balance)}</b>\n"
        f"📊 Jami sarflangan: {format_price(user.total_spent)}\n"
        f"📦 Jami buyurtmalar: {format_number(user.total_orders)}\n\n"
        f"Hisobingizni to'ldirish uchun quyidagi tugmani bosing 👇"
    )
    from keyboards.inline import get_balance_kb
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_balance_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "pay_method_click")
async def pay_click(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Click to'lov"""
    await state.set_state(PaymentStates.waiting_for_amount)
    await state.update_data(payment_method="click")

    min_amount = await SettingsDAO.get_int(session, "min_payment_amount", 5000)

    await callback.message.edit_text(
        f"💳 <b>Click orqali to'lov</b>\n\n"
        f"💰 Minimum summa: {format_price(Decimal(str(min_amount)))}\n\n"
        f"Qancha summa to'lamoqchisiz? (so'mda yozing)",
        parse_mode="HTML",
    )
    await callback.message.answer("💰 Summani kiriting:", reply_markup=get_cancel_kb())
    await callback.answer()


@router.callback_query(F.data == "pay_method_payme")
async def pay_payme(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Payme to'lov"""
    await state.set_state(PaymentStates.waiting_for_amount)
    await state.update_data(payment_method="payme")

    min_amount = await SettingsDAO.get_int(session, "min_payment_amount", 5000)

    await callback.message.edit_text(
        f"💳 <b>Payme orqali to'lov</b>\n\n"
        f"💰 Minimum summa: {format_price(Decimal(str(min_amount)))}\n\n"
        f"Qancha summa to'lamoqchisiz? (so'mda yozing)",
        parse_mode="HTML",
    )
    await callback.message.answer("💰 Summani kiriting:", reply_markup=get_cancel_kb())
    await callback.answer()


@router.callback_query(F.data == "pay_method_stars")
async def pay_stars(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Telegram Stars to'lov"""
    await state.set_state(PaymentStates.waiting_for_amount)
    await state.update_data(payment_method="stars")

    stars_rate = await SettingsDAO.get_int(session, "stars_rate", 1500)
    await callback.message.edit_text(
        f"⭐ <b>Telegram Stars orqali to'lov</b>\n\n"
        f"💱 Kurs: 1 Star = {format_price(Decimal(str(stars_rate)))}\n\n"
        f"Necha Star to'lamoqchisiz? (raqam yozing)\n\n"
        f"📌 Misol: 100 yozsangiz = {format_price(Decimal(str(stars_rate * 100)))}",
        parse_mode="HTML",
    )
    await callback.message.answer(
        "⭐ Stars miqdorini kiriting:", reply_markup=get_cancel_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "pay_method_ton")
async def pay_ton(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """TON orqali to'lov"""
    await state.set_state(PaymentStates.waiting_for_amount)
    await state.update_data(payment_method="ton")

    ton_rate = await SettingsDAO.get_int(session, "ton_rate", 70000)

    await callback.message.edit_text(
        f"💎 <b>TON orqali to'lov</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💱 <b>Kurs:</b> 1 TON = <b>{format_price(Decimal(str(ton_rate)))}</b>\n\n"
        f"Necha TON to'lamoqchisiz? (miqdorni kiriting, masalan: <code>1</code> yoki <code>2.5</code>)\n\n"
        f"📌 Kiritgan miqdoringiz kurs bo'yicha avtomatik so'mga hisoblanadi!",
        parse_mode="HTML",
    )
    await callback.message.answer("💎 TON miqdorini kiriting:", reply_markup=get_cancel_kb())
    await callback.answer()


@router.callback_query(F.data == "pay_method_usdt")
async def pay_usdt(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """USDT orqali to'lov"""
    await state.set_state(PaymentStates.waiting_for_amount)
    await state.update_data(payment_method="usdt")

    usdt_rate = await SettingsDAO.get_int(session, "usdt_rate", 13000)

    await callback.message.edit_text(
        f"💵 <b>USDT orqali to'lov</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💱 <b>Kurs:</b> 1 USDT = <b>{format_price(Decimal(str(usdt_rate)))}</b>\n\n"
        f"Necha USDT to'lamoqchisiz? (miqdorni kiriting, masalan: <code>10</code> yoki <code>25</code>)\n\n"
        f"📌 Kiritgan miqdoringiz kurs bo'yicha avtomatik so'mga hisoblanadi!",
        parse_mode="HTML",
    )
    await callback.message.answer("💵 USDT miqdorini kiriting:", reply_markup=get_cancel_kb())
    await callback.answer()


@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery, state: FSMContext):
    """To'lovni bekor qilish"""
    await state.clear()
    await callback.message.edit_text("❌ To'lov bekor qilindi.")
    await callback.answer()


# ============================================
# SUMMA KIRITISH
# ============================================

@router.message(PaymentStates.waiting_for_amount)
async def process_payment_amount(message: Message, state: FSMContext, session: AsyncSession):
    """To'lov summasini qabul qilish"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ To'lov bekor qilindi.",
            reply_markup=get_main_menu_kb(),
        )
        return

    data = await state.get_data()
    method = data.get("payment_method")

    raw_text = message.text.strip().replace(" ", "").replace(",", ".")

    # 1. Kriptovalyutalar (TON va USDT)
    if method in ("ton", "usdt"):
        try:
            crypto_qty = Decimal(raw_text)
            if crypto_qty <= Decimal("0"):
                raise ValueError()
        except Exception:
            await message.answer("❌ Iltimos, musbat son kiriting (masalan: 2 yoki 2.5):")
            return

        if method == "ton":
            rate = await SettingsDAO.get_int(session, "ton_rate", 70000)
            wallet = await SettingsDAO.get(session, "wallet_ton", "UQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEt5")
            currency = "TON"
            symbol = "💎"
        else:
            rate = await SettingsDAO.get_int(session, "usdt_rate", 13000)
            wallet = await SettingsDAO.get(session, "wallet_usdt", "TXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
            currency = "USDT"
            symbol = "💵"

        amount = (crypto_qty * Decimal(str(rate))).quantize(Decimal("1.00"))

        await state.update_data(
            amount=str(amount),
            crypto_amount=str(crypto_qty),
            crypto_currency=currency,
        )
        await state.set_state(PaymentStates.waiting_for_screenshot)

        text = (
            f"{symbol} <b>{currency} to'lov ma'lumotlari</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 To'lov miqdori: <b>{crypto_qty} {currency}</b>\n"
            f"💵 Balansga qo'shiladi: <b>{format_price(amount)}</b>\n"
            f"💱 Kurs: 1 {currency} = {format_price(Decimal(str(rate)))}\n\n"
            f"📬 <b>Bizning {currency} hamyon manzili:</b>\n"
            f"<code>{wallet}</code>\n"
            f"<i>(Nusxalash uchun ustiga bosing)</i>\n\n"
            f"📸 To'lovni amalga oshirib, <b>screenshot (chek)</b> ni shu yerga rasm ko'rinishida yuboring."
        )
        await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_kb())
        return

    # 2. Telegram Stars
    if method == "stars":
        try:
            stars_count = int(raw_text)
            if stars_count < 1:
                raise ValueError()
        except ValueError:
            await message.answer("❌ Iltimos, butun musbat son kiriting (masalan: 100):")
            return

        stars_rate = await SettingsDAO.get_int(session, "stars_rate", 1500)
        amount = Decimal(str(stars_count * stars_rate))

        await state.update_data(
            amount=str(amount),
            stars_count=stars_count,
        )
        await state.set_state(PaymentStates.waiting_for_screenshot)

        text = (
            f"⭐ <b>Telegram Stars to'lov</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"⭐ Stars: {stars_count}\n"
            f"💰 Summa: <b>{format_price(amount)}</b>\n\n"
            f"📸 To'lovni amalga oshiring va <b>screenshot</b> yuboring.\n\n"
            f"💡 Stars sotib olish uchun Telegram Settings → Stars bo'limiga o'ting."
        )
        await message.answer(
            text, parse_mode="HTML", reply_markup=get_cancel_kb()
        )
        return

    # 3. Click / Payme
    try:
        amount_input = int(raw_text)
    except ValueError:
        await message.answer("❌ Iltimos, faqat raqam kiriting:")
        return

    min_payment = await SettingsDAO.get_int(session, "min_payment_amount", 5000)
    amount = Decimal(str(amount_input))

    if amount < min_payment:
        await message.answer(
            f"❌ Minimum summa: {format_price(Decimal(str(min_payment)))}"
        )
        return

    card_key = "payment_card_click" if method == "click" else "payment_card_payme"
    card = await SettingsDAO.get(session, card_key, "8600 0000 0000 0000")
    card_holder = await SettingsDAO.get(session, "payment_card_holder", "ISM FAMILIYA")
    method_name = "Click" if method == "click" else "Payme"

    await state.update_data(amount=str(amount))
    await state.set_state(PaymentStates.waiting_for_screenshot)

    text = (
        f"💳 <b>{method_name} orqali to'lov</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Summa: <b>{format_price(amount)}</b>\n\n"
        f"💳 Karta raqam:\n"
        f"<code>{card}</code>\n\n"
        f"👤 Karta egasi: <b>{card_holder}</b>\n\n"
        f"📸 To'lovni amalga oshiring va <b>screenshot</b> yuboring.\n"
        f"⚠️ Summa to'liq mos kelishi kerak!"
    )
    await message.answer(
        text, parse_mode="HTML", reply_markup=get_cancel_kb()
    )


# ============================================
# SCREENSHOT QABUL QILISH
# ============================================

@router.message(PaymentStates.waiting_for_screenshot, F.photo)
async def process_payment_screenshot(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
):
    """Screenshot qabul qilish va to'lov yaratish"""
    data = await state.get_data()
    amount = Decimal(data["amount"])
    method = data["payment_method"]

    # Eng katta rasm faylini olish
    photo = message.photo[-1]
    file_id = photo.file_id

    # Foydalanuvchini olish
    user = await UserDAO.get_by_telegram_id(session, message.from_user.id)

    # To'lov yaratish
    payment_method = PaymentMethod(method)
    payment = await PaymentDAO.create(
        session=session,
        user_id=user.id,
        amount=amount,
        payment_method=payment_method,
        screenshot_file_id=file_id,
    )

    await state.clear()

    # Admin guruhga bildirishnoma
    await notify_new_payment(bot=bot, payment=payment, user=user)

    await message.answer(
        f"✅ <b>To'lov #{payment.id} qabul qilindi!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Summa: {format_price(amount)}\n"
        f"📋 Holat: 🕐 Admin tekshirilmoqda\n\n"
        f"⏳ Admin tasdiqlagach, balansingizga qo'shiladi.\n"
        f"Odatda 5-30 daqiqa ichida tasdiqlanadi.",
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(),
    )


@router.message(PaymentStates.waiting_for_screenshot)
async def process_payment_no_photo(message: Message, state: FSMContext):
    """Screenshot yuborilmaganda"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ To'lov bekor qilindi.",
            reply_markup=get_main_menu_kb(),
        )
        return

    await message.answer(
        "📸 Iltimos, to'lov <b>screenshot</b>ini <b>rasm</b> sifatida yuboring!",
        parse_mode="HTML",
    )
