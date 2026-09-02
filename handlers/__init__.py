"""
Handlers Package — Barcha routerlarni birlashtirish

Routerlar tartibi:
1. start_router — /start va obuna tekshirish
2. admin_router — admin panel buyruqlari va callbacklar
3. services_router — xizmatlar katalogi va buyurtma berish
4. payment_router — to'lov usullari va screenshotlar
5. menu_router — asosiy menyu tugmalari
"""

from aiogram import Router

from handlers.start import router as start_router
from handlers.admin import router as admin_router
from handlers.services import router as services_router
from handlers.payment import router as payment_router
from handlers.menu import router as menu_router


def setup_routers() -> Router:
    """Barcha routerlarni bitta asosiy routerga ulash"""
    main_router = Router()

    # Tartib bo'yicha qo'shish
    main_router.include_router(start_router)
    main_router.include_router(admin_router)
    main_router.include_router(services_router)
    main_router.include_router(payment_router)
    main_router.include_router(menu_router)

    return main_router


__all__ = [
    "setup_routers",
    "start_router",
    "admin_router",
    "services_router",
    "payment_router",
    "menu_router",
]
