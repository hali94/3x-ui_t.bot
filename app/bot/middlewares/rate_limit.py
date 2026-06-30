from typing import Any, Callable, Awaitable
import redis.asyncio as aioredis
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from app.security.rate_limiter import RateLimiter, RateLimitExceeded


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, redis_client: aioredis.Redis):
        self.limiter = RateLimiter(redis_client)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_obj = data.get("event_from_user")
        if not user_obj:
            return await handler(event, data)
        try:
            await self.limiter.check_telegram_user(user_obj.id)
        except RateLimitExceeded as exc:
            if isinstance(event, Message):
                await event.answer(f"⏳ {exc}")
            elif isinstance(event, CallbackQuery):
                await event.answer(f"⏳ {exc}", show_alert=True)
            return
        return await handler(event, data)
