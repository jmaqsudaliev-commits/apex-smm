"""
SMM Panel Telegram Bot — Konfiguratsiya

Barcha sozlamalar .env fayldan yuklanadi.
Pydantic orqali validatsiya qilinadi — noto'g'ri qiymat bo'lsa bot ishga tushmaydi.
"""

from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Bot konfiguratsiyasi"""

    # Telegram
    bot_token: str = Field(..., description="Telegram Bot Token")
    _admin_ids_str: str = ""
    _mandatory_channels_str: str = ""

    admin_ids_raw: str = Field(default="", alias="ADMIN_IDS")
    mandatory_channels_raw: str = Field(default="", alias="MANDATORY_CHANNELS")

    @property
    def admin_ids(self) -> List[int]:
        raw = self.admin_ids_raw.strip() if self.admin_ids_raw else ""
        if not raw:
            return []
        raw = raw.replace("[", "").replace("]", "")
        res = []
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                res.append(int(part))
        return res

    @property
    def mandatory_channels(self) -> List[str]:
        raw = self.mandatory_channels_raw.strip() if self.mandatory_channels_raw else ""
        if not raw:
            return []
        raw = raw.replace("[", "").replace("]", "")
        return [ch.strip() for ch in raw.split(",") if ch.strip()]

    # Buyurtmalar guruhining ID si (admin guruh)
    order_group_id: int = Field(
        default=0,
        description="Buyurtmalar yuboriladigan guruh ID si"
    )

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///data/smm_bot.db",
        description="Database URL"
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL"
    )

    # To'lov
    min_payment_amount: int = Field(default=5000, description="Minimum to'ldirish summasi (so'm)")
    referral_bonus_percent: int = Field(default=5, description="Referal bonus foizi")

    # Telegram Stars narxi (1 Star = necha so'm)
    stars_rate: int = Field(default=1500, description="1 Telegram Star = necha so'm")

    # To'lov kartalari
    payment_card_click: str = Field(default="8600 0000 0000 0000", description="Click karta")
    payment_card_payme: str = Field(default="8600 0000 0000 0000", description="Payme karta")
    payment_card_holder: str = Field(default="ISM FAMILIYA", description="Karta egasi")

    # Bot
    throttle_rate: float = Field(default=0.5, description="Throttle rate (soniya)")
    log_level: str = Field(default="INFO", description="Log darajasi")

    # Bot haqida
    bot_username: str = Field(default="smm_panel_bot", description="Bot username")
    support_username: str = Field(default="admin", description="Support username")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global konfiguratsiya obyekti
settings = Settings()
