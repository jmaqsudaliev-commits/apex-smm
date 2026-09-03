"""
Helper funksiyalar — Yordamchi utillar

Narx formatlash, sana formatlash, buyurtma matni yaratish va boshqalar.
"""

from decimal import Decimal
from datetime import datetime
from typing import Optional


def format_price(amount: Decimal) -> str:
    """Narxni chiroyli formatlash: 15,000 so'm"""
    amount_int = int(amount)
    formatted = f"{amount_int:,}".replace(",", " ")
    return f"{formatted} so'm"


def format_number(num: int) -> str:
    """Sonni formatlash: 1 000 000"""
    return f"{num:,}".replace(",", " ")


def calculate_price(price_per_1000: Decimal, quantity: int) -> Decimal:
    """Umumiy narxni hisoblash"""
    return (price_per_1000 * Decimal(str(quantity))) / Decimal("1000")


def format_datetime(dt: datetime) -> str:
    """Sanani formatlash: 02.09.2026 22:15"""
    if dt:
        return dt.strftime("%d.%m.%Y %H:%M")
    return "—"


def get_status_emoji(status: str) -> str:
    """Buyurtma holatiga mos emoji"""
    status_map = {
        "pending": "🕐",
        "processing": "⏳",
        "in_progress": "🔄",
        "completed": "✅",
        "partial": "⚠️",
        "cancelled": "❌",
        "failed": "💔",
    }
    return status_map.get(status, "❓")


def get_status_text(status: str) -> str:
    """Buyurtma holatining o'zbek tilidagi matni"""
    status_map = {
        "pending": "Kutilmoqda",
        "processing": "Qayta ishlanmoqda",
        "in_progress": "Jarayonda",
        "completed": "Bajarildi",
        "partial": "Qisman bajarildi",
        "cancelled": "Bekor qilindi",
        "failed": "Muvaffaqiyatsiz",
    }
    return status_map.get(status, "Noma'lum")


def get_payment_status_text(status: str) -> str:
    """To'lov holatining matni"""
    status_map = {
        "pending": "🕐 Kutilmoqda",
        "approved": "✅ Tasdiqlandi",
        "rejected": "❌ Rad etildi",
    }
    return status_map.get(status, "❓ Noma'lum")


def get_payment_method_text(method: str) -> str:
    """To'lov usulining matni"""
    method_map = {
        "click": "💳 Click",
        "payme": "💳 Payme",
        "cash": "💵 Naqd pul",
        "stars": "⭐ Telegram Stars",
        "ton": "💎 TON (Kriptovalyuta)",
        "usdt": "💵 USDT (TRC-20 / TON)",
    }
    return method_map.get(method, method)


def truncate_text(text: str, max_length: int = 50) -> str:
    """Matnni qisqartirish"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_order_text(order, service_name: str = "", execution_time: str = "") -> str:
    """Buyurtma ma'lumotlarini formatlash"""
    status_emoji = get_status_emoji(order.status.value if hasattr(order.status, 'value') else order.status)
    status_text = get_status_text(order.status.value if hasattr(order.status, 'value') else order.status)
    order_num = getattr(order, "order_number", None) or str(order.id)

    text = (
        f"{status_emoji} <b>Buyurtma #{order_num}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )
    if service_name:
        text += f"📦 Xizmat: {service_name}\n"
    text += (
        f"🔗 Havola: {truncate_text(order.target_link)}\n"
        f"📊 Miqdor: {format_number(order.quantity)}\n"
        f"💰 Narx: {format_price(order.total_price)}\n"
    )
    if execution_time:
        text += f"⏱ Bajarilish vaqti: {execution_time}\n"
    text += (
        f"📋 Holat: {status_text}\n"
        f"📅 Sana: {format_datetime(order.created_at)}\n"
    )
    return text


def format_order_for_group(order, user, service_name: str = "", execution_time: str = "") -> str:
    """Buyurtma ma'lumotlarini admin guruh uchun formatlash"""
    order_num = getattr(order, "order_number", None) or str(order.id)
    text = (
        f"📦 <b>YANGI BUYURTMA #{order_num}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 Mijoz: {user.full_name}"
    )
    if user.username:
        text += f" (@{user.username})"
    text += (
        f"\n🆔 ID: <code>{user.telegram_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )
    if service_name:
        text += f"🛍 Xizmat: <b>{service_name}</b>\n"
    text += (
        f"🔗 Havola: {order.target_link}\n"
        f"📊 Miqdor: {format_number(order.quantity)}\n"
        f"💰 Narx: {format_price(order.total_price)}\n"
    )
    if execution_time:
        text += f"⏱ Bajarilish oralig'i: <b>{execution_time}</b>\n"
    text += (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📅 {format_datetime(order.created_at)}\n"
    )
    return text
