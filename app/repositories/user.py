from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.user import User, UserRole, UserStatus
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.reseller_profile))
            .where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_with_reseller(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.reseller_profile))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_or_update(self, telegram_id: int, username: str | None, full_name: str) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            user.username = username
            user.full_name = full_name
            await self.session.flush()
            return user
        user = User(telegram_id=telegram_id, username=username, full_name=full_name)
        return await self.create(user)

    async def list_resellers(self, active_only: bool = True) -> list[User]:
        roles = [UserRole.RESELLER_L1, UserRole.RESELLER_L2, UserRole.RESELLER]
        q = (
            select(User)
            .options(selectinload(User.reseller_profile))
            .where(User.role.in_(roles))
        )
        if active_only:
            q = q.where(User.status == UserStatus.ACTIVE)
        result = await self.session.execute(q)
        return list(result.scalars().all())
