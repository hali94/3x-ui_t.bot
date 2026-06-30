from decimal import Decimal
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from app.models.reseller import Reseller
from app.repositories.base import BaseRepository


class ResellerRepository(BaseRepository[Reseller]):
    model = Reseller

    async def get_by_user_id(self, user_id: int) -> Reseller | None:
        result = await self.session.execute(
            select(Reseller).where(Reseller.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def add_credit(self, reseller_id: int, gb: Decimal) -> Reseller | None:
        reseller = await self.get(reseller_id)
        if not reseller:
            return None
        reseller.credit_gb += gb
        await self.session.flush()
        return reseller

    async def deduct_credit(self, reseller_id: int, gb: Decimal) -> Reseller | None:
        """Atomically deduct credit — raises ValueError if insufficient."""
        reseller = await self.get(reseller_id)
        if not reseller:
            return None
        remaining = reseller.credit_gb - reseller.used_gb
        if remaining < gb:
            raise ValueError(f"موجودی ناکافی: {remaining:.2f} گیگ باقی مانده")
        reseller.used_gb += gb
        await self.session.flush()
        return reseller

    async def list_active(self) -> list[Reseller]:
        result = await self.session.execute(
            select(Reseller)
            .options(selectinload(Reseller.user))
            .where(Reseller.active == True)
        )
        return list(result.scalars().all())
