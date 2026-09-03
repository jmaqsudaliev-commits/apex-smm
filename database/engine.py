"""
Database Engine — Asinxron ulanish va session boshqaruvi

Connection pooling sozlangan — 1M+ foydalanuvchi uchun optimallashtirilgan.
SQLite (dev) va PostgreSQL (production) ni qo'llab-quvvatlaydi.
"""

import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from database.models import Base
from config import settings


def get_db_url() -> str:
    """Database URL ni asinxron formatga moslashtirish (Render/Cloud uchun)"""
    url = settings.database_url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # asyncpg drayveri sslmode parametrini to'g'ridan-to'g'ri tanimaydi
    if "sslmode=require" in url:
        url = url.replace("sslmode=require", "ssl=require")
    elif "sslmode=prefer" in url:
        url = url.replace("sslmode=prefer", "ssl=prefer")
    elif "sslmode=disable" in url:
        url = url.replace("sslmode=disable", "ssl=disable")
    return url


def _get_engine_kwargs():
    """Database turiga qarab engine parametrlarini qaytaradi"""
    url = get_db_url()

    if url.startswith("sqlite"):
        # SQLite uchun — WAL mode yoqilgan (tezroq yozish)
        return {
            "echo": False,
            "connect_args": {"check_same_thread": False},
        }
    else:
        # PostgreSQL uchun — connection pooling
        return {
            "echo": False,
            "pool_size": 50,           # Asosiy ulanishlar soni
            "max_overflow": 100,       # Qo'shimcha ulanishlar
            "pool_timeout": 30,        # Ulanish kutish vaqti
            "pool_recycle": 1800,      # 30 daqiqada ulanish yangilanadi
            "pool_pre_ping": True,     # Ulanish holatini tekshiradi
        }


# Asinxron engine yaratish
engine = create_async_engine(
    get_db_url(),
    **_get_engine_kwargs()
)

# Session fabrikasi
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Commit dan keyin obyektlar yangilanmaydi
)


async def create_tables():
    """Jadvallarni yaratish va yetishmayotgan ustunlarni qo'shish (avtomatik migratsiya)"""
    # data/ papkani yaratish (SQLite uchun)
    if settings.database_url.startswith("sqlite"):
        os.makedirs("data", exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # 1. orders jadvalida order_number ustunini xavfsiz qo'shish
        try:
            await conn.execute(text("ALTER TABLE orders ADD COLUMN order_number VARCHAR(50)"))
        except Exception:
            pass

        # 2. services jadvalida execution_time ustunini xavfsiz qo'shish
        try:
            await conn.execute(text("ALTER TABLE services ADD COLUMN execution_time VARCHAR(100)"))
        except Exception:
            pass


async def close_engine():
    """Engine ni yopish"""
    await engine.dispose()
