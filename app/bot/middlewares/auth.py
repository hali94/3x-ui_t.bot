from typing import Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.user import User, UserStatus
from app.repositories.user import UserRepository


class AuthMiddleware(BaseMiddleware):
    """
    Injects the current User (or None) into handler data.
    Also blocks banned users at the middleware level.
    """

    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_obj = data.get("event_from_user")
        if not user_obj:
            return await handler(event, data)

        async with self.session_factory() as session:
            repo = UserRepository(session)
            db_user = await repo.get_by_telegram_id(user_obj.id)
            if db_user is None:
                db_user = await repo.create_or_update(
                    telegram_id=user_obj.id,
                    username=user_obj.username,
                    full_name=user_obj.full_name or user_obj.first_name or "ناشناس",
                )
                await session.commit()
            elif db_user.status == UserStatus.BANNED:
                if isinstance(event, Message):
                    await event.answer("⛔ حساب شما مسدود شده است.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⛔ حساب شما مسدود شده است.", show_alert=True)
                return

            data["db_user"] = db_user
            data["db_session"] = session
            return await handler(event, data)
