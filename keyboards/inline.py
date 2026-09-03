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


def get_service_detail_kb(service_id: int, category_id: int = None) -> InlineKeyboardMarkup:
    """Xizmat tafsilotlari — mahsulot haqida ko'rib, tagidan buyurtma berish"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🛍 Buyurtma berish", callback_data=f"order_{service_id}")
    back_data = f"cat_{category_id}" if category_id else "back_categories"
    builder.button(text="🔙 Orqaga", callback_data=back_data)
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


def get_admin_order_group_kb(detected_groups: list = None, active_group_id: int = 0) -> InlineKeyboardMarkup:
    """Adminlar guruhi boshqaruv va tanlash tugmalari"""
    builder = InlineKeyboardBuilder()

    # Aniqlangan guruhlarni tanlash tugmalari qilib chiqarish
    if detected_groups:
        for grp in detected_groups:
            grp_id = grp.get("id")
            title = grp.get("title", "Guruh")[:22]
            is_active = (grp_id == active_group_id)
            icon = "✅" if is_active else "🔘"
            suffix = " (Ulangan)" if is_active else ""
            builder.button(
                text=f"{icon} {title}{suffix}",
                callback_data=f"adm_select_grp_{grp_id}",
            )
        builder.adjust(1)

    # Qo'shimcha amallar
    sub_rows = [
        InlineKeyboardButton(text="🔄 Yangilash", callback_data="adm_refresh_groups"),
        InlineKeyboardButton(text="✏️ ID kiritish", callback_data="adm_set_group_id"),
    ]
    if active_group_id and active_group_id != 0:
        sub_rows.insert(1, InlineKeyboardButton(text="🧪 Test xabar", callback_data="adm_test_group_msg"))
        sub_rows.append(InlineKeyboardButton(text="🗑 Uzish", callback_data="adm_clear_group_id"))

    builder.row(*sub_rows)
    builder.row(InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_admin"))
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


def get_admin_users_list_kb(users, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Admin — foydalanuvchilar to'liq ro'yxati va sahifalash"""
    builder = InlineKeyboardBuilder()
    for u in users:
        ban_ico = "🔴" if u.is_banned else "🟢"
        name = (u.full_name or "Noma'lum")[:16]
        bal = f"{int(u.balance):,} so'm".replace(",", " ")
        builder.button(
            text=f"{ban_ico} {name} | {bal}",
            callback_data=f"adm_view_user_{u.id}",
        )
    builder.adjust(1)

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"adm_users_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page}/{max(total_pages, 1)}", callback_data="adm_noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"adm_users_page_{page + 1}"))

    if nav_row:
        builder.row(*nav_row)

    builder.row(
        InlineKeyboardButton(text="🔍 Qidirish (ID / Username)", callback_data="adm_search_user_start"),
        InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_admin"),
    )
    return builder.as_markup()


def get_admin_user_kb(user_id: int, is_banned: bool, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Admin — tanlangan foydalanuvchi boshqaruvi"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎁 Bonus qo'shish", callback_data=f"adm_bonus_{user_id}")
    builder.button(text="💰 Balans o'rnatish", callback_data=f"adm_set_bal_{user_id}")
    ban_text = "🟢 Blokdan chiqarish" if is_banned else "🚫 Bloklash (Ban)"
    builder.button(text=ban_text, callback_data=f"adm_ban_{user_id}")
    admin_text = "❌ Admindan olish" if is_admin else "👑 Admin qilish"
    builder.button(text=admin_text, callback_data=f"adm_toggle_admin_{user_id}")
    builder.row(
        InlineKeyboardButton(text="👥 Barcha foydalanuvchilar", callback_data="adm_users_page_1"),
        InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_admin"),
    )
    builder.adjust(2, 2, 2)
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


def get_admins_manage_kb(db_admins) -> InlineKeyboardMarkup:
    """Adminlar boshqaruvi klaviaturasi"""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Yangi admin qo'shish", callback_data="adm_add_admin_start")
    for adm in db_admins:
        name = (adm.full_name or "Admin")[:16]
        builder.button(
            text=f"❌ O'chirish: {name}",
            callback_data=f"adm_remove_admin_{adm.id}",
        )
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_admin")
    )
    return builder.as_markup()
