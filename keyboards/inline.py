"""
Inline Keyboards — Kategoriyalar, xizmatlar, buyurtmalar va admin tugmalari

Barcha callback_data prefikslari:
- cat_  : Kategoriya
- svc_  : Xizmat
- ord_  : Buyurtma
- pay_  : To'lov
- adm_  : Admin
- sub_  : Obuna tekshirish
"""

from decimal import Decimal
from typing import Sequence, Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ============================================
# KATEGORIYALAR
# ============================================

def get_categories_kb(categories) -> InlineKeyboardMarkup:
    """Kategoriyalar inline tugmalari"""
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(
            text=f"{cat.emoji} {cat.name.replace(cat.emoji, '').strip()}",
            callback_data=f"cat_{cat.id}",
        )
    builder.adjust(2)  # 2 ta tugma bir qatorda
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main")
    )
    return builder.as_markup()


# ============================================
# XIZMATLAR
# ============================================

def get_services_kb(services, category_id: int) -> InlineKeyboardMarkup:
    """Xizmatlar ro'yxati (kategoriya ichida)"""
    builder = InlineKeyboardBuilder()
    for svc in services:
        # Narxni formatlash
        if svc.min_quantity == 1 and svc.max_quantity == 1:
            # Bir martalik xizmat (Premium, NFT, sovg'a)
            price_text = f"{int(svc.price_per_1000):,} so'm".replace(",", ".")
        else:
            price_text = f"{int(svc.price_per_1000):,}/1K".replace(",", ".")

        builder.button(
            text=f"{svc.name} — {price_text}",
            callback_data=f"svc_{svc.id}",
        )
    builder.adjust(1)  # Har biri alohida qatorda
    builder.row(
        InlineKeyboardButton(text="🔙 Kategoriyalarga", callback_data="back_categories")
    )
    return builder.as_markup()


def get_service_detail_kb(service_id: int) -> InlineKeyboardMarkup:
    """Xizmat tafsilotlari — buyurtma berish"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Buyurtma berish", callback_data=f"order_{service_id}")
    builder.button(text="🔙 Orqaga", callback_data="back_services")
    builder.adjust(1)
    return builder.as_markup()


# ============================================
# BUYURTMA
# ============================================

def get_order_confirm_kb(service_id: int) -> InlineKeyboardMarkup:
    """Buyurtmani tasdiqlash"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"confirm_order_{service_id}")
    builder.button(text="❌ Bekor qilish", callback_data="cancel_order")
    builder.adjust(2)
    return builder.as_markup()


def get_order_status_kb(order_id: int) -> InlineKeyboardMarkup:
    """Buyurtma holati"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Yangilash", callback_data=f"refresh_order_{order_id}")
    return builder.as_markup()


# ============================================
# ADMIN — BUYURTMALAR BOSHQARUVI
# ============================================

def get_admin_orders_menu_kb() -> InlineKeyboardMarkup:
    """Admin buyurtmalar asosiy menyusi"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Kutilayotgan buyurtmalar", callback_data="adm_orders_pending")
    builder.button(text="🔍 Buyurtma raqami orqali boshqarish", callback_data="adm_orders_search")
    builder.adjust(1)
    return builder.as_markup()


def get_admin_order_kb(order_id: int) -> InlineKeyboardMarkup:
    """Admin guruhda va xabarlarda buyurtma tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Bajarildi", callback_data=f"adm_complete_{order_id}")
    builder.button(text="🔄 Jarayonda", callback_data=f"adm_progress_{order_id}")
    builder.button(text="❌ Atmen / Bekor qilish", callback_data=f"adm_cancel_{order_id}")
    builder.adjust(3)
    return builder.as_markup()


def get_admin_order_manage_kb(order_id: int) -> InlineKeyboardMarkup:
    """Admin buyurtma raqami bilan qidirgandagi boshqaruv tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Bajarildi", callback_data=f"adm_complete_{order_id}")
    builder.button(text="❌ Atmen (Bekor qilish)", callback_data=f"adm_cancel_{order_id}")
    builder.button(text="🔄 Jarayonda", callback_data=f"adm_progress_{order_id}")
    builder.button(text="🔍 Boshqa buyurtma qidirish", callback_data="adm_orders_search")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


# ============================================
# BALANS VA TO'LOV
# ============================================

def get_balance_kb() -> InlineKeyboardMarkup:
    """Balans ko'rsatilgandagi tugma"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Balansni to'ldirish", callback_data="topup_balance")
    return builder.as_markup()


def get_payment_methods_kb() -> InlineKeyboardMarkup:
    """To'lov usullari"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Click", callback_data="pay_method_click")
    builder.button(text="💳 Payme", callback_data="pay_method_payme")
    builder.button(text="⭐ Telegram Stars", callback_data="pay_method_stars")
    builder.button(text="💎 TON", callback_data="pay_method_ton")
    builder.button(text="💵 USDT", callback_data="pay_method_usdt")
    builder.button(text="🔙 Orqaga", callback_data="back_to_balance")
    builder.adjust(2, 1, 2, 1)
    return builder.as_markup()


def get_admin_order_group_kb(has_group: bool = False) -> InlineKeyboardMarkup:
    """Adminlar guruhi boshqaruv tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Guruh ID sini o'rnatish", callback_data="adm_set_group_id")
    if has_group:
        builder.button(text="🧪 Guruhga test xabar yuborish", callback_data="adm_test_group_msg")
        builder.button(text="❌ Guruhni o'chirish", callback_data="adm_clear_group_id")
    builder.button(text="🔙 Admin panel", callback_data="back_admin")
    builder.adjust(1)
    return builder.as_markup()


def get_admin_payment_kb(payment_id: int) -> InlineKeyboardMarkup:
    """Admin to'lovni tasdiqlash/rad etish"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"adm_pay_approve_{payment_id}")
    builder.button(text="❌ Rad etish", callback_data=f"adm_pay_reject_{payment_id}")
    builder.adjust(2)
    return builder.as_markup()


# ============================================
# MAJBURIY OBUNA
# ============================================

def get_subscription_kb(channels: list, bot_username: str = "") -> InlineKeyboardMarkup:
    """Majburiy obuna tekshirish tugmalari"""
    builder = InlineKeyboardBuilder()
    for i, channel in enumerate(channels):
        channel_clean = channel.replace("@", "")
        builder.button(
            text=f"📢 {channel} ga obuna bo'lish",
            url=f"https://t.me/{channel_clean}",
        )
    builder.row(
        InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription")
    )
    return builder.as_markup()


# ============================================
# ADMIN PANEL
# ============================================

def get_admin_services_kb(categories) -> InlineKeyboardMarkup:
    """Admin — kategoriyalar boshqaruvi"""
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(
            text=f"{cat.emoji} {cat.name.replace(cat.emoji, '').strip()}",
            callback_data=f"adm_cat_{cat.id}",
        )
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="➕ Kategoriya qo'shish", callback_data="adm_add_category")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_admin")
    )
    return builder.as_markup()


def get_admin_service_list_kb(services, category_id: int) -> InlineKeyboardMarkup:
    """Admin — xizmatlar ro'yxati (tahrirlash uchun)"""
    builder = InlineKeyboardBuilder()
    for svc in services:
        status = "✅" if svc.is_active else "❌"
        builder.button(
            text=f"{status} {svc.name}",
            callback_data=f"adm_svc_{svc.id}",
        )
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(
            text="➕ Xizmat qo'shish",
            callback_data=f"adm_add_svc_{category_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Kategoriyalarga", callback_data="adm_back_cats")
    )
    return builder.as_markup()


def get_admin_service_edit_kb(service_id: int) -> InlineKeyboardMarkup:
    """Admin — xizmatni tahrirlash"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Narxni o'zgartirish", callback_data=f"adm_edit_price_{service_id}")
    builder.button(text="📝 Nomni o'zgartirish", callback_data=f"adm_edit_name_{service_id}")
    builder.button(text="🔄 Holat (yoqish/o'chirish)", callback_data=f"adm_toggle_{service_id}")
    builder.button(text="🗑 O'chirish", callback_data=f"adm_del_svc_{service_id}")
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back_services")
    )
    return builder.as_markup()


def get_admin_user_kb(user_id: int, is_banned: bool, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Admin — foydalanuvchi boshqaruvi"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Balans o'zgartirish", callback_data=f"adm_set_bal_{user_id}")
    ban_text = "🔓 Ban olish" if is_banned else "🔒 Ban berish"
    builder.button(text=ban_text, callback_data=f"adm_ban_{user_id}")
    admin_text = "❌ Admindan olish" if is_admin else "👑 Admin qilish"
    builder.button(text=admin_text, callback_data=f"adm_toggle_admin_{user_id}")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_broadcast_confirm_kb() -> InlineKeyboardMarkup:
    """Broadcast tasdiqlash"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Yuborish", callback_data="adm_broadcast_send")
    builder.button(text="❌ Bekor qilish", callback_data="adm_broadcast_cancel")
    builder.adjust(2)
    return builder.as_markup()


def get_back_kb(callback_data: str = "back_main") -> InlineKeyboardMarkup:
    """Oddiy orqaga tugma"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data=callback_data)]
        ]
    )
