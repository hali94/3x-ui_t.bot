from decimal import Decimal
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
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_reseller(self, reseller_id: int, limit: int = 50) -> list[Subscription]:
        result = await self.session.execute(
            select(Subscription)
            .options(selectinload(Subscription.customer))
            .where(Subscription.reseller_id == reseller_id)
            .order_by(Subscription.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class SaleRepository(BaseRepository[Sale]):
    model = Sale

    async def total_sales_by_reseller(self, reseller_id: int) -> tuple[Decimal, Decimal, Decimal]:
        """Returns (total_amount, total_gb, total_profit)."""
        result = await self.session.execute(
            select(func.sum(Sale.amount), func.sum(Sale.gb), func.sum(Sale.profit))
            .where(Sale.reseller_id == reseller_id)
        )
        row = result.one()
        return (
            row[0] or Decimal("0"),
            row[1] or Decimal("0"),
            row[2] or Decimal("0"),
        )

    async def list_by_reseller(self, reseller_id: int, limit: int = 50) -> list[Sale]:
        result = await self.session.execute(
            select(Sale)
            .options(selectinload(Sale.customer))
            .where(Sale.reseller_id == reseller_id)
            .order_by(Sale.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def children_sales_summary(self, parent_reseller_id: int) -> list[tuple]:
        """Aggregate sales per child reseller for L1 reporting."""
        from app.models.reseller import Reseller
        from app.models.user import User
        result = await self.session.execute(
            select(
                Reseller.id,
                User.full_name,
                func.sum(Sale.amount).label("total_amount"),
                func.sum(Sale.gb).label("total_gb"),
                func.count(Sale.id).label("sale_count"),
            )
            .join(Reseller, Sale.reseller_id == Reseller.id)
            .join(User, Reseller.user_id == User.id)
            .where(Reseller.parent_reseller_id == parent_reseller_id)
            .group_by(Reseller.id, User.full_name)
        )
        return result.all()
