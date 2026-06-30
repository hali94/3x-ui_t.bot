"""
Sliding-window rate limiter backed by Redis sorted sets.

Raises RateLimitExceeded (not FastAPI's HTTPException) so it works
in both the Telegram bot and the API layer.
"""

import time
import redis.asyncio as aioredis
from app.config import settings


class RateLimitExceeded(Exception):
    pass


class RateLimiter:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.time()
        window_start = now - window_seconds
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, "-inf", window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()
        count = results[2]
        if count > limit:
            raise RateLimitExceeded(
                f"تعداد درخواست‌ها بیش از حد مجاز است. "
                f"لطفاً {window_seconds // 60} دقیقه صبر کنید."
            )

    async def check_telegram_user(self, telegram_id: int) -> None:
        await self.check(
            f"rate:tg:{telegram_id}:min",
            settings.RATE_LIMIT_PER_MINUTE,
            60,
        )
        await self.check(
            f"rate:tg:{telegram_id}:hr",
            settings.RATE_LIMIT_PER_HOUR,
            3600,
        )
