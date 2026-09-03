"""
SMM Panel Telegram Bot — Asosiy ishga tushirish fayli (Entrypoint)

Arxitektura:
- aiogram 3.x
- SQLAlchemy 2.0 (Async) + aiosqlite / asyncpg
- RedisStorage (FSM persistence uchun, server o'chsa ham xotira saqlanadi)
- Middlewares: DB Session, Throttling (Rate Limiting), Majburiy obuna
- 1M+ foydalanuvchiga mo'ljallangan asinxron ishlov
"""

import os
import sys
import asyncio
from loguru import logger

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand

from config import settings
from database.engine import create_tables, close_engine, async_session
from database.dao import seed_categories_and_services, seed_settings
from middlewares.database import DatabaseMiddleware
from middlewares.throttling import ThrottlingMiddleware
from middlewares.subscription import SubscriptionMiddleware
from handlers import setup_routers


def setup_logger():
    """Log tizimini sozlash"""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    logger.remove()
    # Konsolga chiqarish
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )
    # Faylga yozish (kunlik rotatsiya bilan, 10 kunda tozalanadi)
    logger.add(
        "data/bot.log",
        level="INFO",
        rotation="10 MB",
        retention="10 days",
        compression="zip",
        encoding="utf-8",
    )


async def get_storage():
    """FSM storage ni sozlash (Redis yoki Fallback Memory)"""
    try:
        if settings.redis_url:
            storage = RedisStorage.from_url(settings.redis_url)
            # Redis ulanishini tekshirish
            await storage.redis.ping()
            logger.info("✅ Redis FSM Storage muvaffaqiyatli ulandi")
            return storage
    except Exception as e:
        logger.warning(f"⚠️ Redis ulanmadi ({e}), MemoryStorage ishlatilmoqda...")

    return MemoryStorage()


async def set_bot_commands(bot: Bot):
    """Telegram menyu buyruqlarini o'rnatish"""
    commands = [
        BotCommand(command="start", description="🚀 Botni boshlash / Asosiy menyu"),
        BotCommand(command="help", description="ℹ️ Yordam va FAQ"),
        BotCommand(command="admin", description="🔐 Admin panel (faqat adminlar)"),
    ]
    try:
        await bot.set_my_commands(commands)
    except Exception as e:
        logger.warning(f"Buyruqlarni o'rnatishda xato: {e}")


async def on_startup(bot: Bot):
    """Bot ishga tushganda bajariladigan amallar"""
    logger.info("📦 Ma'lumotlar bazasi jadvallari tekshirilmoqda...")
    await create_tables()

    # Boshlang'ich kategoriyalar va sozlamalarni yaratish
    async with async_session() as session:
        await seed_settings(session)
        await seed_categories_and_services(session)

        # Bir martalik tozalash: admin barcha xizmatlarni o'zi qo'shishi uchun eski xizmatlarni tozalash
        cleaned = await SettingsDAO.get(session, "cleaned_default_services", "0")
        if cleaned != "1":
            from database.models import Service, Order
            from sqlalchemy import delete
            try:
                await session.execute(delete(Order))
                await session.execute(delete(Service))
                await SettingsDAO.set(session, "cleaned_default_services", "1", "Eski xizmatlar tozalandi")
                logger.info("🗑 Eski xizmatlar to'liq tozalandi (admin o'zi kiritadi)")
            except Exception as e:
                logger.warning(f"Xizmatlarni tozalashda xato: {e}")
    logger.info("✅ Baza boshlang'ich ma'lumotlari tayyorlandi")

    await set_bot_commands(bot)

    bot_info = await bot.get_me()
    logger.info(f"🤖 Bot ishga tushdi: @{bot_info.username} (ID: {bot_info.id})")

    # Adminlarga bot ishga tushgani haqida xabar
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text="🚀 <b>SMM Panel Bot muvaffaqiyatli ishga tushdi!</b>\n\nAdmin panel: /admin",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


async def on_shutdown(bot: Bot):
    """Bot to'xtatilganda bajariladigan amallar"""
    logger.info("🛑 Bot to'xtatilmoqda...")
    await close_engine()
    logger.info("✅ Database ulanishlari yopildi")


async def main():
    """Asosiy funksiya"""
    setup_logger()
    logger.info("⏳ Bot sozlanmoqda...")

    if not settings.bot_token or settings.bot_token == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ BOT_TOKEN belgilanmagan! .env faylni tekshiring.")
        return

    # FSM Storage
    storage = await get_storage()

    # Bot & Dispatcher
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=storage)

    # Render.com / Cloud Web Service lari uchun health check port
    port = os.getenv("PORT")
    if port:
        try:
            from aiohttp import web
            app = web.Application()
            async def health(req):
                return web.Response(text="SMM Bot is Running! ✅")
            app.router.add_get("/", health)
            app.router.add_get("/health", health)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", int(port))
            await site.start()
            logger.info(f"🌐 Cloud Healthcheck HTTP server {port}-portda ishga tushdi")
        except Exception as e:
            logger.warning(f"Health server sozlashda xato: {e}")

    # Middlewares (Tartib juda muhim!)
    # 1. Database session inject
    dp.update.outer_middleware(DatabaseMiddleware())
    # 2. Throttling spam protection
    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())
    # 3. Mandatory channel subscription check
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    # Routers
    dp.include_router(setup_routers())

    # Startup & Shutdown hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Eski kutilib qolgan xabarlarni tozalash (drop pending updates)
    await bot.delete_webhook(drop_pending_updates=True)

    # Polling boshlash
    logger.info("🚀 Polling boshlandi...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Bot to'xtatildi.")
