"""
FSM States — Finite State Machine holatlari

Foydalanuvchining qaysi bosqichda ekanligini kuzatish uchun.
"""

from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    """Buyurtma berish jarayoni"""
    waiting_for_link = State()        # Havola kutilmoqda
    waiting_for_quantity = State()    # Miqdor kutilmoqda
    waiting_for_confirm = State()     # Tasdiqlash kutilmoqda


class PaymentStates(StatesGroup):
    """To'lov jarayoni"""
    waiting_for_amount = State()      # Summa kutilmoqda
    waiting_for_method = State()      # To'lov usuli kutilmoqda
    waiting_for_screenshot = State()  # Screenshot kutilmoqda


class AdminStates(StatesGroup):
    """Admin panel holatlari"""
    # Xizmat qo'shish
    add_category_name = State()
    add_category_emoji = State()
    add_service_name = State()
    add_service_price = State()
    add_service_min = State()
    add_service_max = State()
    add_service_desc = State()

    # Foydalanuvchi boshqaruvi
    search_user = State()
    set_user_balance = State()

    # Broadcast
    broadcast_message = State()
    broadcast_confirm = State()

    # Xizmat tahrirlash
    edit_service_price = State()
    edit_service_name = State()

    # To'lovni rad etish sababi
    reject_reason = State()
