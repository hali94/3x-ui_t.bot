from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.sale import Sale
from app.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    model = Subscription

    async def get_active_by_customer(self, customer_id: int) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.customer_id == customer_id,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                )
            )
            .order_by(Subscription.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def list_by_reseller(self, reseller_id: int) -> list[Subscription]:
        result = await self.session.execute(
            select(Subscription)
            .options(selectinload(Subscription.customer))
            .where(Subscription.reseller_id == reseller_id)
            .order_by(Subscription.created_at.desc())
        )
        return list(result.scalars().all())


class SaleRepository(BaseRepository[Sale]):
    model = Sale

    async def total_sales_by_reseller(self, reseller_id: int):
        result = await self.session.execute(
            select(func.sum(Sale.amount), func.sum(Sale.gb))
            .where(Sale.reseller_id == reseller_id)
        )
        return result.one()

    async def list_by_reseller(self, reseller_id: int, limit: int = 50) -> list[Sale]:
        result = await self.session.execute(
            select(Sale)
            .options(selectinload(Sale.customer))
            .where(Sale.reseller_id == reseller_id)
            .order_by(Sale.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
