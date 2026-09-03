"""
Reply Keyboards — Asosiy menyu va boshqa reply tugmalar

Foydalanuvchining asosiy navigatsiya tugmalari.
"""

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)


def get_main_menu_kb() -> ReplyKeyboardMarkup:
    """Asosiy menyu klaviaturasi"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🛒 Xizmatlar"),
                KeyboardButton(text="💰 Balans"),
            ],
            [
                KeyboardButton(text="📋 Buyurtmalarim"),
                KeyboardButton(text="👤 Profil"),
            ],
            [
                KeyboardButton(text="🔗 Referal"),
                KeyboardButton(text="ℹ️ Yordam"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Menyudan tanlang...",
    )


def get_admin_menu_kb() -> ReplyKeyboardMarkup:
    """Admin panel klaviaturasi"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="👥 Foydalanuvchilar"),
            ],
            [
                KeyboardButton(text="🛍 Xizmatlar boshqaruvi"),
                KeyboardButton(text="📢 Xabar yuborish"),
            ],
            [
                KeyboardButton(text="🏢 Adminlar Guruhi"),
                KeyboardButton(text="📢 Majburiy Obuna"),
            ],
            [
                KeyboardButton(text="👑 Adminlar"),
                KeyboardButton(text="⚙️ Sozlamalar"),
            ],
            [
                KeyboardButton(text="🔙 Asosiy menyu"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Admin panel",
    )


def get_cancel_kb() -> ReplyKeyboardMarkup:
    """Bekor qilish tugmasi"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )


def get_skip_kb() -> ReplyKeyboardMarkup:
    """O'tkazib yuborish tugmasi"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏩ O'tkazib yuborish")],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )


def get_confirm_kb() -> ReplyKeyboardMarkup:
    """Tasdiqlash tugmalari"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Tasdiqlash"),
                KeyboardButton(text="❌ Bekor qilish"),
            ],
        ],
        resize_keyboard=True,
    )


# ReplyKeyboardRemove
remove_kb = ReplyKeyboardRemove()
