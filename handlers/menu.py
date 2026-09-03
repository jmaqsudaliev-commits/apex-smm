"""
Menu Handler — Asosiy menyu tugmalarini boshqarish

Reply keyboard tugmalari bosilganda tegishli handlerga yo'naltiradi.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.dao import UserDAO, CategoryDAO, SettingsDAO
from keyboards.reply import get_main_menu_kb, get_admin_menu_kb
from keyboards.inline import get_categories_kb, get_back_kb
from filters.admin import IsAdmin
from utils.helpers import format_price, format_number

router = Router()


@router.message(F.text == "🛒 Xizmatlar")
async def show_services(message: Message, session: AsyncSession):
    """Xizmatlar katalogi"""
    categories = await CategoryDAO.get_all_active(session)

    if not categories:
        await message.answer(
            "😔 Hozircha xizmatlar mavjud emas. Tez orada qo'shiladi!",
            parse_mode="HTML",
        )
        return

    await message.answer(
        "🛒 <b>Xizmatlar katalogi</b>\n\n"
        "Quyidagi kategoriyalardan birini tanlang 👇",
        parse_mode="HTML",
        reply_markup=get_categories_kb(categories),
    )


@router.message(F.text == "💰 Balans")
async def show_balance(message: Message, session: AsyncSession):
    """Balans ko'rsatish"""
    user = await UserDAO.get_by_telegram_id(session, message.from_user.id)
    if not user:
        return

    text = (
        f"💰 <b>Sizning balansingiz</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💵 Balans: <b>{format_price(user.balance)}</b>\n"
        f"📊 Jami sarflangan: {format_price(user.total_spent)}\n"
        f"📦 Jami buyurtmalar: {format_number(user.total_orders)}\n\n"
        f"💳 Balansni to'ldirish uchun quyidagi tugmani bosing 👇"
    )

    from keyboards.inline import get_balance_kb
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_balance_kb(),
    )


@router.message(F.text == "📋 Buyurtmalarim")
async def show_my_orders(message: Message, session: AsyncSession):
    """Buyurtmalarim"""
    from database.dao import OrderDAO
    from utils.helpers import format_order_text

    user = await UserDAO.get_by_telegram_id(session, message.from_user.id)
    if not user:
        return

    orders = await OrderDAO.get_user_orders(session, user.id, limit=10)

    if not orders:
        await message.answer(
            "📋 <b>Buyurtmalarim</b>\n\n"
            "Sizda hali buyurtmalar yo'q.\n"
            "🛒 <b>Xizmatlar</b> bo'limidan buyurtma bering!",
            parse_mode="HTML",
        )
        return

    text = f"📋 <b>Buyurtmalarim</b> (oxirgi {len(orders)} ta)\n\n"

    for order in orders:
        service_name = ""
        exec_time = ""
        if order.service:
            service_name = order.service.name
            exec_time = order.service.execution_time or ""
        text += format_order_text(order, service_name, exec_time) + "\n"

    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "👤 Profil")
async def show_profile(message: Message, session: AsyncSession):
    """Profil"""
    user = await UserDAO.get_by_telegram_id(session, message.from_user.id)
    if not user:
        return

    referral_count = await UserDAO.get_referral_count(session, user.id)
    referral_earnings = await UserDAO.get_referral_earnings(session, user.id)

    text = (
        f"👤 <b>Sizning profilingiz</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n"
        f"👤 Ism: {user.full_name}\n"
    )
    if user.username:
        text += f"📎 Username: @{user.username}\n"
    text += (
        f"\n💰 Balans: <b>{format_price(user.balance)}</b>\n"
        f"📊 Jami sarflangan: {format_price(user.total_spent)}\n"
        f"📦 Jami buyurtmalar: {format_number(user.total_orders)}\n\n"
        f"🔗 Referallar: {referral_count} ta\n"
        f"💸 Referal daromad: {format_price(referral_earnings)}\n\n"
        f"📅 Ro'yxatdan o'tgan: {user.created_at.strftime('%d.%m.%Y')}"
    )

    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🔗 Referal")
async def show_referral(message: Message, session: AsyncSession):
    """Referal tizimi"""
    user = await UserDAO.get_by_telegram_id(session, message.from_user.id)
    if not user:
        return

    referral_count = await UserDAO.get_referral_count(session, user.id)
    referral_earnings = await UserDAO.get_referral_earnings(session, user.id)
    ref_percent = await SettingsDAO.get_int(session, "referral_bonus_percent", 5)

    referral_link = f"https://t.me/{settings.bot_username}?start=ref_{user.referral_code}"

    text = (
        f"🔗 <b>Referal tizimi</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Do'stlaringizni taklif qiling va har bir to'lovdan "
        f"<b>{ref_percent}%</b> bonus oling!\n\n"
        f"📎 Sizning referal havolangiz:\n"
        f"<code>{referral_link}</code>\n\n"
        f"👥 Taklif qilganlar: <b>{referral_count}</b> ta\n"
        f"💰 Jami daromad: <b>{format_price(referral_earnings)}</b>\n\n"
        f"💡 Havolani do'stlaringizga yuboring — ular ro'yxatdan o'tgandan "
        f"so'ng har bir to'lovdan bonus olasiz!"
    )

    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "ℹ️ Yordam")
async def show_help(message: Message, session: AsyncSession):
    """Yordam"""
    support_user = await SettingsDAO.get(session, "support_username", settings.support_username)
    text = (
        f"ℹ️ <b>Yordam markazi</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 <b>Bot qanday ishlaydi?</b>\n\n"
        f"1️⃣ 💰 <b>Balansni to'ldiring</b>\n"
        f"   Click, Payme yoki Stars orqali to'lang va screenshot yuboring.\n"
        f"   Admin tasdiqlagach, balans to'ldiriladi.\n\n"
        f"2️⃣ 🛒 <b>Xizmatni tanlang</b>\n"
        f"   Kategoriya → Xizmat → Havola → Miqdor\n\n"
        f"3️⃣ ✅ <b>Buyurtmani tasdiqlang</b>\n"
        f"   Balansdan avtomatik yechib olinadi.\n\n"
        f"4️⃣ 📋 <b>Buyurtmani kuzating</b>\n"
        f"   Buyurtmalarim bo'limidan holatni ko'ring.\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 <b>Mavjud xizmatlar:</b>\n"
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
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"❓ Savol yoki muammo bo'lsa:\n"
        f"📞 Admin: @{support_user}\n"
    )

    await message.answer(text, parse_mode="HTML")


# ============================================
# ADMIN MENYU
# ============================================

@router.message(F.text == "🔙 Asosiy menyu")
async def back_to_main_menu(message: Message, state: FSMContext):
    """Admin paneldan asosiy menyuga qaytish"""
    await state.clear()
    await message.answer(
        "🏠 Asosiy menyu",
        reply_markup=get_main_menu_kb(),
    )


@router.callback_query(F.data == "back_main")
async def callback_back_main(callback: CallbackQuery, state: FSMContext):
    """Inline orqaga — asosiy menyu"""
    await state.clear()
    await callback.message.edit_text(
        "🏠 Asosiy menyu\n\nQuyidagi menyudan tanlang 👇",
        parse_mode="HTML",
    )
    await callback.answer()
