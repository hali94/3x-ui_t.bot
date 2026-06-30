"""
Telegram bot entrypoint.
Registers all routers, middlewares, and starts polling.
"""

import asyncio
import logging

import redis.asyncio as aioredis
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from app.bot.handlers import admin, common, reseller
from app.bot.middlewares.auth import AuthMiddleware
from app.bot.middlewares.rate_limit import RateLimitMiddleware
from app.config import settings
from app.database import async_session_factory, init_db
from app.utils.logger import configure_logging, get_logger

logger = get_logger(__name__)


async def main() -> None:
    configure_logging()
    await init_db()

    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    storage = RedisStorage(redis=redis_client)

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=storage)

    # Middlewares (order matters — rate limit before auth)
    dp.update.outer_middleware(RateLimitMiddleware(redis_client))
    dp.update.outer_middleware(AuthMiddleware(async_session_factory))

    # Routers
    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(reseller.router)

    logger.info("bot_starting", token_prefix=settings.TELEGRAM_BOT_TOKEN[:10])

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
