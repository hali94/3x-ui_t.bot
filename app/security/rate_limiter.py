import time
from typing import Callable
import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status
from app.config import settings


class RateLimiter:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def check(self, key: str, limit: int, window: int) -> None:
        """Sliding window rate limiter using Redis."""
        now = time.time()
        window_start = now - window
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, "-inf", window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window)
        results = await pipe.execute()
        count = results[2]
        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="تعداد درخواست‌ها بیش از حد مجاز است. لطفاً کمی صبر کنید.",
            )

    async def check_telegram_user(self, telegram_id: int) -> None:
        key_minute = f"rate:tg:{telegram_id}:minute"
        key_hour = f"rate:tg:{telegram_id}:hour"
        await self.check(key_minute, settings.RATE_LIMIT_PER_MINUTE, 60)
        await self.check(key_hour, settings.RATE_LIMIT_PER_HOUR, 3600)
