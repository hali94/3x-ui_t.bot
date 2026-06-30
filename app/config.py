from functools import lru_cache
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "VPN Reseller Platform"
    APP_ENV: str = "production"
    APP_DEBUG: bool = False
    APP_SECRET_KEY: str
    APP_ENCRYPTION_KEY: str

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40

    # Redis
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_ADMIN_IDS: List[int] = []

    @field_validator("TELEGRAM_ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 30
    RATE_LIMIT_PER_HOUR: int = 200

    # Notification Thresholds
    TRAFFIC_WARN_80: bool = True
    TRAFFIC_WARN_90: bool = True
    TRAFFIC_WARN_100: bool = True
    EXPIRY_WARN_DAYS: int = 3

    # Worker
    WORKER_CONCURRENCY: int = 4
    NOTIFICATION_CHECK_INTERVAL_HOURS: int = 6

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
