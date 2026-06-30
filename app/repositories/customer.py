from datetime import datetime, timezone
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.models.customer import Customer, CustomerStatus
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    model = Customer

    async def get_by_email(self, email: str) -> Customer | None:
        result = await self.session.execute(
            select(Customer).where(Customer.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_uuid(self, uuid: str) -> Customer | None:
        result = await self.session.execute(
            select(Customer).where(Customer.uuid == uuid)
        )
        return result.scalar_one_or_none()

    async def list_by_reseller(self, reseller_id: int, limit: int = 50, offset: int = 0) -> list[Customer]:
        result = await self.session.execute(
            select(Customer)
            .where(Customer.reseller_id == reseller_id)
            .order_by(Customer.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_expiring_soon(self, days: int) -> list[Customer]:
        """Return active customers expiring within `days` days."""
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        threshold = now + timedelta(days=days)
        result = await self.session.execute(
            select(Customer)
            .where(
                and_(
                    Customer.status == CustomerStatus.ACTIVE,
                    Customer.expire_date <= threshold,
                    Customer.expire_date >= now,
                )
            )
        )
        return list(result.scalars().all())

    async def get_by_traffic_threshold(self, percent: float) -> list[Customer]:
        """Return active customers who have used >= percent% of their traffic."""
        result = await self.session.execute(
            select(Customer).where(Customer.status == CustomerStatus.ACTIVE)
        )
        customers = list(result.scalars().all())
        return [c for c in customers if c.traffic_percent >= percent]
