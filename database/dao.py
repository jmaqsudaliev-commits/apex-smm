"""
Data Access Objects (DAO) — Database bilan ishlash funksiyalari

Barcha CRUD operatsiyalar shu yerda.
Handlerlar to'g'ridan-to'g'ri SQL yozmaydi, faqat DAO orqali ishlaydi.
"""

import secrets
from decimal import Decimal
from typing import Optional, List, Sequence

from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    User, Category, Service, Order, Payment, Referral,
    BotSettings, OrderStatus, PaymentStatus, PaymentMethod,
)


# ============================================
# USER DAO
# ============================================

class UserDAO:
    """Foydalanuvchi operatsiyalari"""

    @staticmethod
    async def get_or_create(
        session: AsyncSession,
        telegram_id: int,
        full_name: str,
        username: Optional[str] = None,
        referral_code_from: Optional[str] = None,
    ) -> tuple["User", bool]:
        """Foydalanuvchini olish yoki yaratish. (user, is_new) qaytaradi."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Username yangilash
            if username and user.username != username:
                user.username = username
                user.full_name = full_name
                await session.commit()
            return user, False

        # Yangi foydalanuvchi
        ref_code = secrets.token_urlsafe(8)[:10].upper()

        # Referal tekshirish
        referred_by_id = None
        if referral_code_from:
            referrer = await UserDAO.get_by_referral_code(session, referral_code_from)
            if referrer and referrer.telegram_id != telegram_id:
                referred_by_id = referrer.id

        new_user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            referral_code=ref_code,
            referred_by_id=referred_by_id,
        )
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        # Referal bonusini qo'shish
        if referred_by_id:
            referral = Referral(
                referrer_id=referred_by_id,
                referred_id=new_user.id,
            )
            session.add(referral)
            await session.commit()

        return new_user, True

    @staticmethod
    async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_referral_code(session: AsyncSession, code: str) -> Optional[User]:
        stmt = select(User).where(User.referral_code == code)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_balance(
        session: AsyncSession, user_id: int, amount: Decimal
    ) -> Optional[User]:
        """Balansga qo'shish yoki ayirish"""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(balance=User.balance + amount)
            .returning(User)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.scalar_one_or_none()

    @staticmethod
    async def set_balance(
        session: AsyncSession, user_id: int, amount: Decimal
    ) -> None:
        """Balansni to'g'ridan-to'g'ri o'rnatish"""
        stmt = update(User).where(User.id == user_id).values(balance=amount)
        await session.execute(stmt)
        await session.commit()

    @staticmethod
    async def ban_user(session: AsyncSession, user_id: int, banned: bool = True) -> None:
        stmt = update(User).where(User.id == user_id).values(is_banned=banned)
        await session.execute(stmt)
        await session.commit()

    @staticmethod
    async def get_total_count(session: AsyncSession) -> int:
        stmt = select(func.count(User.id))
        result = await session.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    async def get_all_ids(session: AsyncSession) -> List[int]:
        """Barcha foydalanuvchilarning Telegram ID lari (broadcast uchun)"""
        stmt = select(User.telegram_id).where(User.is_banned == False)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def search_users(
        session: AsyncSession, query: str, limit: int = 20
    ) -> Sequence[User]:
        """Foydalanuvchini qidirish (ID, username yoki ism bo'yicha)"""
        stmt = select(User).where(
            (User.username.ilike(f"%{query}%")) |
            (User.full_name.ilike(f"%{query}%")) |
            (User.telegram_id == int(query) if query.isdigit() else False)
        ).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_referral_count(session: AsyncSession, user_id: int) -> int:
        stmt = select(func.count(Referral.id)).where(Referral.referrer_id == user_id)
        result = await session.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    async def get_referral_earnings(session: AsyncSession, user_id: int) -> Decimal:
        stmt = select(func.coalesce(func.sum(Referral.bonus_amount), 0)).where(
            Referral.referrer_id == user_id
        )
        result = await session.execute(stmt)
        return Decimal(str(result.scalar() or 0))


# ============================================
# CATEGORY DAO
# ============================================

class CategoryDAO:
    """Kategoriya operatsiyalari"""

    @staticmethod
    async def get_all_active(session: AsyncSession) -> Sequence[Category]:
        stmt = (
            select(Category)
            .where(Category.is_active == True)
            .order_by(Category.sort_order, Category.id)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_by_id(session: AsyncSession, category_id: int) -> Optional[Category]:
        stmt = select(Category).where(Category.id == category_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        session: AsyncSession,
        name: str,
        emoji: str = "📦",
        description: Optional[str] = None,
        sort_order: int = 0,
    ) -> Category:
        category = Category(
            name=name, emoji=emoji,
            description=description, sort_order=sort_order,
        )
        session.add(category)
        await session.commit()
        await session.refresh(category)
        return category

    @staticmethod
    async def delete(session: AsyncSession, category_id: int) -> bool:
        stmt = delete(Category).where(Category.id == category_id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


# ============================================
# SERVICE DAO
# ============================================

class ServiceDAO:
    """Xizmat operatsiyalari"""

    @staticmethod
    async def get_by_category(
        session: AsyncSession, category_id: int
    ) -> Sequence[Service]:
        stmt = (
            select(Service)
            .where(Service.category_id == category_id, Service.is_active == True)
            .order_by(Service.sort_order, Service.id)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_by_id(session: AsyncSession, service_id: int) -> Optional[Service]:
        stmt = select(Service).where(Service.id == service_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        session: AsyncSession,
        category_id: int,
        name: str,
        price_per_1000: Decimal,
        min_quantity: int = 100,
        max_quantity: int = 100000,
        description: Optional[str] = None,
        api_service_id: Optional[int] = None,
    ) -> Service:
        service = Service(
            category_id=category_id,
            name=name,
            price_per_1000=price_per_1000,
            min_quantity=min_quantity,
            max_quantity=max_quantity,
            description=description,
            api_service_id=api_service_id,
        )
        session.add(service)
        await session.commit()
        await session.refresh(service)
        return service

    @staticmethod
    async def update(
        session: AsyncSession,
        service_id: int,
        **kwargs,
    ) -> Optional[Service]:
        stmt = (
            update(Service)
            .where(Service.id == service_id)
            .values(**kwargs)
            .returning(Service)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.scalar_one_or_none()

    @staticmethod
    async def delete(session: AsyncSession, service_id: int) -> bool:
        stmt = delete(Service).where(Service.id == service_id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def get_total_count(session: AsyncSession) -> int:
        stmt = select(func.count(Service.id)).where(Service.is_active == True)
        result = await session.execute(stmt)
        return result.scalar() or 0


# ============================================
# ORDER DAO
# ============================================

class OrderDAO:
    """Buyurtma operatsiyalari"""

    @staticmethod
    async def create(
        session: AsyncSession,
        user_id: int,
        service_id: int,
        target_link: str,
        quantity: int,
        total_price: Decimal,
    ) -> Order:
        order = Order(
            user_id=user_id,
            service_id=service_id,
            target_link=target_link,
            quantity=quantity,
            total_price=total_price,
            status=OrderStatus.PENDING,
        )
        session.add(order)

        # Foydalanuvchi statistikasini yangilash
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                balance=User.balance - total_price,
                total_spent=User.total_spent + total_price,
                total_orders=User.total_orders + 1,
            )
        )

        await session.commit()
        await session.refresh(order)
        return order

    @staticmethod
    async def get_by_id(session: AsyncSession, order_id: int) -> Optional[Order]:
        stmt = select(Order).where(Order.id == order_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_orders(
        session: AsyncSession, user_id: int, limit: int = 20
    ) -> Sequence[Order]:
        stmt = (
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def update_status(
        session: AsyncSession, order_id: int, status: OrderStatus,
        api_order_id: Optional[str] = None,
    ) -> Optional[Order]:
        values = {"status": status}
        if api_order_id:
            values["api_order_id"] = api_order_id
        stmt = (
            update(Order)
            .where(Order.id == order_id)
            .values(**values)
        )
        await session.execute(stmt)
        await session.commit()
        return await OrderDAO.get_by_id(session, order_id)

    @staticmethod
    async def get_total_count(session: AsyncSession) -> int:
        stmt = select(func.count(Order.id))
        result = await session.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    async def get_total_revenue(session: AsyncSession) -> Decimal:
        stmt = select(func.coalesce(func.sum(Order.total_price), 0))
        result = await session.execute(stmt)
        return Decimal(str(result.scalar() or 0))

    @staticmethod
    async def get_pending_orders(session: AsyncSession) -> Sequence[Order]:
        stmt = (
            select(Order)
            .where(Order.status == OrderStatus.PENDING)
            .order_by(Order.created_at.asc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_recent_orders(
        session: AsyncSession, limit: int = 50
    ) -> Sequence[Order]:
        stmt = (
            select(Order)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()


# ============================================
# PAYMENT DAO
# ============================================

class PaymentDAO:
    """To'lov operatsiyalari"""

    @staticmethod
    async def create(
        session: AsyncSession,
        user_id: int,
        amount: Decimal,
        payment_method: PaymentMethod,
        screenshot_file_id: Optional[str] = None,
    ) -> Payment:
        payment = Payment(
            user_id=user_id,
            amount=amount,
            payment_method=payment_method,
            screenshot_file_id=screenshot_file_id,
            status=PaymentStatus.PENDING,
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        return payment

    @staticmethod
    async def get_by_id(session: AsyncSession, payment_id: int) -> Optional[Payment]:
        stmt = select(Payment).where(Payment.id == payment_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def approve(
        session: AsyncSession, payment_id: int, admin_id: int
    ) -> Optional[Payment]:
        """To'lovni tasdiqlash va balansga qo'shish"""
        payment = await PaymentDAO.get_by_id(session, payment_id)
        if not payment or payment.status != PaymentStatus.PENDING:
            return None

        # To'lov statusini yangilash
        payment.status = PaymentStatus.APPROVED
        payment.admin_id = admin_id

        # Balansga qo'shish
        await session.execute(
            update(User)
            .where(User.id == payment.user_id)
            .values(balance=User.balance + payment.amount)
        )

        # Referal bonus (Admin paneldan sozlangan foiz)
        user = await UserDAO.get_by_id(session, payment.user_id)
        if user and user.referred_by_id:
            ref_percent = await SettingsDAO.get_int(session, "referral_bonus_percent", 5)
            bonus = payment.amount * Decimal(str(ref_percent)) / 100
            if bonus > 0:
                await session.execute(
                    update(User)
                    .where(User.id == user.referred_by_id)
                    .values(balance=User.balance + bonus)
                )
                await session.execute(
                    update(Referral)
                    .where(
                        Referral.referrer_id == user.referred_by_id,
                        Referral.referred_id == user.id,
                    )
                    .values(bonus_amount=Referral.bonus_amount + bonus)
                )

        await session.commit()
        await session.refresh(payment)
        return payment

    @staticmethod
    async def reject(
        session: AsyncSession, payment_id: int, admin_id: int,
        note: Optional[str] = None,
    ) -> Optional[Payment]:
        """To'lovni rad etish"""
        stmt = (
            update(Payment)
            .where(Payment.id == payment_id, Payment.status == PaymentStatus.PENDING)
            .values(
                status=PaymentStatus.REJECTED,
                admin_id=admin_id,
                admin_note=note,
            )
        )
        await session.execute(stmt)
        await session.commit()
        return await PaymentDAO.get_by_id(session, payment_id)

    @staticmethod
    async def get_pending(session: AsyncSession) -> Sequence[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.status == PaymentStatus.PENDING)
            .order_by(Payment.created_at.asc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_user_payments(
        session: AsyncSession, user_id: int, limit: int = 20
    ) -> Sequence[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_total_approved(session: AsyncSession) -> Decimal:
        stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.status == PaymentStatus.APPROVED
        )
        result = await session.execute(stmt)
        return Decimal(str(result.scalar() or 0))


# ============================================
# SEED DATA (Boshlang'ich ma'lumotlar)
# ============================================

async def seed_categories_and_services(session: AsyncSession):
    """Boshlang'ich kategoriyalar va xizmatlarni yaratish"""
    # Tekshirish — agar allaqachon bor bo'lsa yaratmaymiz
    existing = await CategoryDAO.get_all_active(session)
    if existing:
        return

    # Kategoriyalar
    categories_data = [
        {"name": "📸 Instagram", "emoji": "📸", "sort_order": 1},
        {"name": "🎵 TikTok", "emoji": "🎵", "sort_order": 2},
        {"name": "📺 YouTube", "emoji": "📺", "sort_order": 3},
        {"name": "✈️ Telegram", "emoji": "✈️", "sort_order": 4},
        {"name": "⭐ Telegram Stars", "emoji": "⭐", "sort_order": 5},
        {"name": "💎 Telegram Premium", "emoji": "💎", "sort_order": 6},
        {"name": "🖼 NFT & Collectibles", "emoji": "🖼", "sort_order": 7},
        {"name": "🎁 Sovg'alar", "emoji": "🎁", "sort_order": 8},
        {"name": "💠 TON Coin", "emoji": "💠", "sort_order": 9},
        {"name": "💵 USDT", "emoji": "💵", "sort_order": 10},
    ]

    services_map = {
        "Instagram": [
            {"name": "👥 Instagram Followers", "price_per_1000": Decimal("15000"), "min_quantity": 100, "max_quantity": 500000},
            {"name": "❤️ Instagram Likes", "price_per_1000": Decimal("8000"), "min_quantity": 50, "max_quantity": 100000},
            {"name": "👁 Instagram Views", "price_per_1000": Decimal("3000"), "min_quantity": 100, "max_quantity": 1000000},
            {"name": "💬 Instagram Comments", "price_per_1000": Decimal("50000"), "min_quantity": 10, "max_quantity": 10000},
            {"name": "📨 Instagram Story Views", "price_per_1000": Decimal("5000"), "min_quantity": 100, "max_quantity": 100000},
            {"name": "💾 Instagram Saves", "price_per_1000": Decimal("12000"), "min_quantity": 50, "max_quantity": 50000},
            {"name": "📤 Instagram Shares", "price_per_1000": Decimal("10000"), "min_quantity": 50, "max_quantity": 50000},
            {"name": "🔄 Instagram Reels Views", "price_per_1000": Decimal("4000"), "min_quantity": 100, "max_quantity": 1000000},
        ],
        "TikTok": [
            {"name": "👥 TikTok Followers", "price_per_1000": Decimal("20000"), "min_quantity": 100, "max_quantity": 500000},
            {"name": "❤️ TikTok Likes", "price_per_1000": Decimal("10000"), "min_quantity": 50, "max_quantity": 100000},
            {"name": "👁 TikTok Views", "price_per_1000": Decimal("2000"), "min_quantity": 500, "max_quantity": 5000000},
            {"name": "🔄 TikTok Shares", "price_per_1000": Decimal("15000"), "min_quantity": 50, "max_quantity": 50000},
            {"name": "💬 TikTok Comments", "price_per_1000": Decimal("45000"), "min_quantity": 10, "max_quantity": 10000},
            {"name": "💾 TikTok Saves", "price_per_1000": Decimal("12000"), "min_quantity": 50, "max_quantity": 50000},
        ],
        "YouTube": [
            {"name": "👥 YouTube Subscribers", "price_per_1000": Decimal("50000"), "min_quantity": 100, "max_quantity": 100000},
            {"name": "👁 YouTube Views", "price_per_1000": Decimal("15000"), "min_quantity": 500, "max_quantity": 1000000},
            {"name": "👍 YouTube Likes", "price_per_1000": Decimal("20000"), "min_quantity": 50, "max_quantity": 50000},
            {"name": "⏱ YouTube Watch Time (soat)", "price_per_1000": Decimal("100000"), "min_quantity": 100, "max_quantity": 10000},
            {"name": "💬 YouTube Comments", "price_per_1000": Decimal("60000"), "min_quantity": 10, "max_quantity": 5000},
        ],
        "Telegram": [
            {"name": "👥 Telegram Members", "price_per_1000": Decimal("25000"), "min_quantity": 100, "max_quantity": 200000},
            {"name": "👁 Telegram Post Views", "price_per_1000": Decimal("3000"), "min_quantity": 100, "max_quantity": 500000},
            {"name": "🔄 Telegram Reactions", "price_per_1000": Decimal("10000"), "min_quantity": 50, "max_quantity": 50000},
            {"name": "📨 Telegram Shares", "price_per_1000": Decimal("15000"), "min_quantity": 50, "max_quantity": 50000},
            {"name": "💬 Telegram Comments", "price_per_1000": Decimal("40000"), "min_quantity": 10, "max_quantity": 10000},
        ],
        "Stars": [
            {"name": "⭐ Telegram Stars (50 dona)", "price_per_1000": Decimal("75000"), "min_quantity": 1, "max_quantity": 1, "description": "50 dona Telegram Stars"},
            {"name": "⭐ Telegram Stars (100 dona)", "price_per_1000": Decimal("150000"), "min_quantity": 1, "max_quantity": 1, "description": "100 dona Telegram Stars"},
            {"name": "⭐ Telegram Stars (250 dona)", "price_per_1000": Decimal("350000"), "min_quantity": 1, "max_quantity": 1, "description": "250 dona Telegram Stars"},
            {"name": "⭐ Telegram Stars (500 dona)", "price_per_1000": Decimal("650000"), "min_quantity": 1, "max_quantity": 1, "description": "500 dona Telegram Stars"},
            {"name": "⭐ Telegram Stars (1000 dona)", "price_per_1000": Decimal("1200000"), "min_quantity": 1, "max_quantity": 1, "description": "1000 dona Telegram Stars"},
        ],
        "Premium": [
            {"name": "💎 Telegram Premium (1 oy)", "price_per_1000": Decimal("35000000"), "min_quantity": 1, "max_quantity": 1, "description": "1 oylik Telegram Premium obuna"},
            {"name": "💎 Telegram Premium (3 oy)", "price_per_1000": Decimal("90000000"), "min_quantity": 1, "max_quantity": 1, "description": "3 oylik Telegram Premium obuna"},
            {"name": "💎 Telegram Premium (6 oy)", "price_per_1000": Decimal("160000000"), "min_quantity": 1, "max_quantity": 1, "description": "6 oylik Telegram Premium obuna"},
            {"name": "💎 Telegram Premium (12 oy)", "price_per_1000": Decimal("280000000"), "min_quantity": 1, "max_quantity": 1, "description": "12 oylik Telegram Premium obuna"},
        ],
        "NFT": [
            {"name": "🖼 Telegram Username NFT", "price_per_1000": Decimal("500000000"), "min_quantity": 1, "max_quantity": 1, "description": "Telegram username NFT sotib olish xizmati"},
            {"name": "🖼 Telegram Nomer NFT", "price_per_1000": Decimal("300000000"), "min_quantity": 1, "max_quantity": 1, "description": "Telegram +888 virtual nomer NFT"},
            {"name": "🖼 Maxsus Emoji Pack", "price_per_1000": Decimal("50000000"), "min_quantity": 1, "max_quantity": 1, "description": "Custom emoji to'plami yaratish"},
        ],
        "Sovg'alar": [
            {"name": "🎁 Telegram Gift (oddiy)", "price_per_1000": Decimal("15000000"), "min_quantity": 1, "max_quantity": 1, "description": "Oddiy Telegram sovg'a"},
            {"name": "🎁 Telegram Gift (noyob)", "price_per_1000": Decimal("50000000"), "min_quantity": 1, "max_quantity": 1, "description": "Noyob Telegram sovg'a"},
            {"name": "🎁 Telegram Gift (premium)", "price_per_1000": Decimal("150000000"), "min_quantity": 1, "max_quantity": 1, "description": "Premium Telegram sovg'a"},
            {"name": "🎂 Tug'ilgan kun tabrik xizmati", "price_per_1000": Decimal("25000000"), "min_quantity": 1, "max_quantity": 1, "description": "Maxsus tug'ilgan kun tabrigi + sovg'a"},
        ],
        "TON": [
            {"name": "💠 TON Coin (10 TON)", "price_per_1000": Decimal("25000000"), "min_quantity": 1, "max_quantity": 1, "description": "10 TON coin sotib olish"},
            {"name": "💠 TON Coin (50 TON)", "price_per_1000": Decimal("120000000"), "min_quantity": 1, "max_quantity": 1, "description": "50 TON coin sotib olish"},
            {"name": "💠 TON Coin (100 TON)", "price_per_1000": Decimal("230000000"), "min_quantity": 1, "max_quantity": 1, "description": "100 TON coin sotib olish"},
            {"name": "💠 TON Coin (500 TON)", "price_per_1000": Decimal("1100000000"), "min_quantity": 1, "max_quantity": 1, "description": "500 TON coin sotib olish"},
        ],
        "USDT": [
            {"name": "💵 USDT (10$)", "price_per_1000": Decimal("13000000"), "min_quantity": 1, "max_quantity": 1, "description": "10 USDT sotib olish (TRC-20)"},
            {"name": "💵 USDT (50$)", "price_per_1000": Decimal("64000000"), "min_quantity": 1, "max_quantity": 1, "description": "50 USDT sotib olish (TRC-20)"},
            {"name": "💵 USDT (100$)", "price_per_1000": Decimal("126000000"), "min_quantity": 1, "max_quantity": 1, "description": "100 USDT sotib olish (TRC-20)"},
            {"name": "💵 USDT (500$)", "price_per_1000": Decimal("620000000"), "min_quantity": 1, "max_quantity": 1, "description": "500 USDT sotib olish (TRC-20)"},
            {"name": "💵 USDT (1000$)", "price_per_1000": Decimal("1230000000"), "min_quantity": 1, "max_quantity": 1, "description": "1000 USDT sotib olish (TRC-20)"},
        ],
    }

    for cat_data in categories_data:
        cat = await CategoryDAO.create(session, **cat_data)

        # Kategoriyaga mos xizmatlarni topish
        cat_key = None
        for key in services_map:
            if key in cat_data["name"]:
                cat_key = key
                break

        if cat_key and cat_key in services_map:
            for i, svc_data in enumerate(services_map[cat_key]):
                await ServiceDAO.create(
                    session,
                    category_id=cat.id,
                    sort_order=i,
                    **svc_data,
                )


# ============================================
# BOT SETTINGS DAO
# ============================================

class SettingsDAO:
    """Bot sozlamalari — admin paneldan boshqariladigan"""

    # Standart qiymatlar
    DEFAULTS = {
        "referral_bonus_percent": ("5", "Referal bonus foizi (%)"),
        "min_payment_amount": ("5000", "Minimum to'ldirish summasi (so'm)"),
        "stars_rate": ("1500", "1 Telegram Star = necha so'm"),
        "payment_card_click": ("8600 0000 0000 0000", "Click karta raqami"),
        "payment_card_payme": ("8600 0000 0000 0000", "Payme karta raqami"),
        "payment_card_holder": ("ISM FAMILIYA", "Karta egasining ismi"),
        "support_username": ("admin", "Qo'llab-quvvatlash username"),
        "mandatory_channels": ("", "Majburiy obuna kanallari (vergul bilan)"),
        "order_group_id": ("0", "Buyurtmalar guruhi ID si"),
        "welcome_bonus": ("0", "Yangi foydalanuvchiga beriladigan bonus (so'm)"),
    }

    @staticmethod
    async def get(session: AsyncSession, key: str, default: str = "") -> str:
        """Sozlamani olish"""
        stmt = select(BotSettings).where(BotSettings.key == key)
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        if setting:
            return setting.value
        # Default dan olish
        if key in SettingsDAO.DEFAULTS:
            return SettingsDAO.DEFAULTS[key][0]
        return default

    @staticmethod
    async def get_int(session: AsyncSession, key: str, default: int = 0) -> int:
        """Sozlamani int sifatida olish"""
        value = await SettingsDAO.get(session, key, str(default))
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    async def get_decimal(session: AsyncSession, key: str, default: str = "0") -> Decimal:
        """Sozlamani Decimal sifatida olish"""
        value = await SettingsDAO.get(session, key, default)
        try:
            return Decimal(value)
        except Exception:
            return Decimal(default)

    @staticmethod
    async def set(session: AsyncSession, key: str, value: str, description: str = None) -> None:
        """Sozlamani saqlash"""
        stmt = select(BotSettings).where(BotSettings.key == key)
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = value
            if description:
                setting.description = description
        else:
            new_setting = BotSettings(
                key=key, value=value,
                description=description or SettingsDAO.DEFAULTS.get(key, ("", ""))[1],
            )
            session.add(new_setting)

        await session.commit()

    @staticmethod
    async def get_all(session: AsyncSession) -> dict:
        """Barcha sozlamalarni olish"""
        stmt = select(BotSettings)
        result = await session.execute(stmt)
        settings_list = result.scalars().all()

        # Default lar bilan birlashtirish
        all_settings = {}
        for key, (default_val, desc) in SettingsDAO.DEFAULTS.items():
            all_settings[key] = {
                "value": default_val,
                "description": desc,
            }

        for s in settings_list:
            all_settings[s.key] = {
                "value": s.value,
                "description": s.description or all_settings.get(s.key, {}).get("description", ""),
            }

        return all_settings


async def seed_settings(session: AsyncSession):
    """Boshlang'ich sozlamalarni yaratish (agar mavjud bo'lmasa)"""
    for key, (default_val, description) in SettingsDAO.DEFAULTS.items():
        existing = await SettingsDAO.get(session, key)
        # Agar DB da yo'q bo'lsa — yaratish
        stmt = select(BotSettings).where(BotSettings.key == key)
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            await SettingsDAO.set(session, key, default_val, description)
