"""
SQLAlchemy modellar — SMM Panel Bot

Barcha jadvallar:
- User: Foydalanuvchilar
- Category: Xizmat kategoriyalari
- Service: Xizmatlar (follower, like, view va boshqalar)
- Order: Buyurtmalar
- Payment: To'lovlar
- Referral: Referal tizimi
"""

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    BigInteger, String, Text, Numeric, Boolean, Integer,
    ForeignKey, DateTime, Enum, func, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Asosiy model"""
    pass


# ============================================
# Enumlar
# ============================================

class OrderStatus(str, enum.Enum):
    """Buyurtma holatlari"""
    PENDING = "pending"              # Kutilmoqda
    PROCESSING = "processing"        # Qayta ishlanmoqda
    IN_PROGRESS = "in_progress"      # Jarayonda
    COMPLETED = "completed"          # Bajarildi
    PARTIAL = "partial"              # Qisman bajarildi
    CANCELLED = "cancelled"          # Bekor qilindi
    FAILED = "failed"                # Muvaffaqiyatsiz


class PaymentStatus(str, enum.Enum):
    """To'lov holatlari"""
    PENDING = "pending"              # Kutilmoqda
    APPROVED = "approved"            # Tasdiqlandi
    REJECTED = "rejected"            # Rad etildi


class PaymentMethod(str, enum.Enum):
    """To'lov usullari"""
    CLICK = "click"
    PAYME = "payme"
    CASH = "cash"
    STARS = "stars"


# ============================================
# Modellar
# ============================================

class User(Base):
    """Foydalanuvchi modeli"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    referral_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    referred_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    total_spent: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    referred_by: Mapped[Optional["User"]] = relationship(
        "User", remote_side="User.id", foreign_keys=[referred_by_id]
    )
    orders: Mapped[List["Order"]] = relationship(
        "Order", back_populates="user", lazy="selectin"
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment", back_populates="user", foreign_keys="Payment.user_id", lazy="selectin"
    )

    # Indexlar — tez qidirish uchun
    __table_args__ = (
        Index("ix_users_telegram_id", "telegram_id"),
        Index("ix_users_referral_code", "referral_code"),
    )

    def __repr__(self):
        return f"<User id={self.id} tg_id={self.telegram_id} name={self.full_name}>"


class Category(Base):
    """Xizmat kategoriyasi (Instagram, TikTok, YouTube, Telegram)"""
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    emoji: Mapped[str] = mapped_column(String(10), default="📦")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    services: Mapped[List["Service"]] = relationship(
        "Service", back_populates="category", lazy="selectin"
    )

    def __repr__(self):
        return f"<Category id={self.id} name={self.name}>"


class Service(Base):
    """Xizmat modeli (Instagram Followers, TikTok Likes va boshqalar)"""
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_per_1000: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="1000 dona uchun narx (so'm)"
    )
    min_quantity: Mapped[int] = mapped_column(Integer, default=100)
    max_quantity: Mapped[int] = mapped_column(Integer, default=100000)
    api_service_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Tashqi SMM API dagi service ID"
    )
    execution_time: Mapped[Optional[str]] = mapped_column(
        String(100), default="10 daqiqa - 24 soat", nullable=True, comment="Bajarilish vaqt oralig'i"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="services")
    orders: Mapped[List["Order"]] = relationship(
        "Order", back_populates="service", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_services_category", "category_id"),
    )

    def __repr__(self):
        return f"<Service id={self.id} name={self.name} price={self.price_per_1000}>"


class Order(Base):
    """Buyurtma modeli"""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_number: Mapped[Optional[str]] = mapped_column(
        String(50), unique=True, nullable=True, comment="Takrorlanmas unikal buyurtma raqami"
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="SET NULL"), nullable=True
    )
    target_link: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.PENDING
    )
    api_order_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Tashqi API dagi buyurtma ID"
    )
    remains: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Qolgan miqdor"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="orders")
    service: Mapped[Optional["Service"]] = relationship("Service", back_populates="orders")

    __table_args__ = (
        Index("ix_orders_order_number", "order_number"),
        Index("ix_orders_user", "user_id"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_created", "created_at"),
    )

    def __repr__(self):
        return f"<Order id={self.id} num={self.order_number} user={self.user_id} status={self.status}>"


class Payment(Base):
    """To'lov modeli"""
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod), nullable=False
    )
    screenshot_file_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Telegram file ID (screenshot)"
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.PENDING
    )
    admin_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User", back_populates="payments", foreign_keys=[user_id]
    )

    __table_args__ = (
        Index("ix_payments_user", "user_id"),
        Index("ix_payments_status", "status"),
    )

    def __repr__(self):
        return f"<Payment id={self.id} user={self.user_id} amount={self.amount} status={self.status}>"


class Referral(Base):
    """Referal tizimi"""
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        comment="Taklif qilgan foydalanuvchi"
    )
    referred_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True,
        comment="Taklif qilingan foydalanuvchi"
    )
    bonus_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"),
        comment="Berilgan bonus summasi"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_referrals_referrer", "referrer_id"),
    )

    def __repr__(self):
        return f"<Referral referrer={self.referrer_id} referred={self.referred_id}>"


class BotSettings(Base):
    """
    Bot sozlamalari — admin paneldan boshqariladigan parametrlar

    key-value formatda saqlaydi. Barcha narxlar, foizlar, kartalar
    shu jadvalda saqlanadi va admin paneldan o'zgartiriladi.
    """
    __tablename__ = "bot_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<BotSettings key={self.key} value={self.value}>"

