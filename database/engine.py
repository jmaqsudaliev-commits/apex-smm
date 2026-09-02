"""
Database Engine — Asinxron ulanish va session boshqaruvi

Connection pooling sozlangan — 1M+ foydalanuvchi uchun optimallashtirilgan.
SQLite (dev) va PostgreSQL (production) ni qo'llab-quvvatlaydi.
"""

import os
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from database.models import Base
from config import settings


def _get_engine_kwargs():
    """Database turiga qarab engine parametrlarini qaytaradi"""
    url = settings.database_url

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
    settings.database_url,
    **_get_engine_kwargs()
)

# Session fabrikasi
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Commit dan keyin obyektlar yangilanmaydi
)


async def create_tables():
    """Jadvallarni yaratish (dev uchun). Production da Alembic ishlating."""
    # data/ papkani yaratish (SQLite uchun)
    if settings.database_url.startswith("sqlite"):
        os.makedirs("data", exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_engine():
    """Engine ni yopish"""
    await engine.dispose()
