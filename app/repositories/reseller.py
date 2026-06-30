from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.reseller import Reseller, ResellerLevel, ResellerStatus
from app.repositories.base import BaseRepository


class ResellerRepository(BaseRepository[Reseller]):
    model = Reseller

    async def get_by_user_id(self, user_id: int) -> Reseller | None:
        result = await self.session.execute(
            select(Reseller)
            .options(selectinload(Reseller.user))
            .where(Reseller.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_with_lock(self, reseller_id: int) -> Reseller | None:
        """SELECT FOR UPDATE — use inside a transaction to prevent race conditions."""
        result = await self.session.execute(
            select(Reseller)
            .where(Reseller.id == reseller_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_user_id_with_lock(self, user_id: int) -> Reseller | None:
        """SELECT FOR UPDATE by user_id."""
        result = await self.session.execute(
            select(Reseller)
            .where(Reseller.user_id == user_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def add_credit(self, reseller_id: int, gb: Decimal, granted_by_id: int | None = None) -> Reseller:
        reseller = await self.get_with_lock(reseller_id)
        if not reseller:
            raise ValueError("نماینده یافت نشد")
        reseller.credit_gb += gb
        await self.session.flush()
        return reseller

    async def deduct_credit(self, reseller_id: int, gb: Decimal) -> Reseller:
        """
        Atomically deduct credit for a customer sale.
        Uses SELECT FOR UPDATE to prevent double-spending.
        """
        reseller = await self.get_with_lock(reseller_id)
        if not reseller:
            raise ValueError("نماینده یافت نشد")
        remaining = reseller.remaining_credit_gb
        if remaining < gb:
            raise ValueError(
                f"❌ موجودی ناکافی است\n"
                f"اعتبار باقی‌مانده: {remaining:.2f} گیگ\n"
                f"درخواست شما: {gb:.2f} گیگ"
            )
        reseller.used_gb += gb
        await self.session.flush()
        return reseller

    async def allocate_to_child(self, parent_id: int, child_id: int, gb: Decimal) -> tuple[Reseller, Reseller]:
        """
        Move credit from parent (L1) to child (L2).
        Both rows are locked to prevent race conditions.
        Locks acquired in id order to prevent deadlock.
        """
        first_id, second_id = sorted([parent_id, child_id])
        first = await self.get_with_lock(first_id)
        second = await self.get_with_lock(second_id)
        parent = first if first.id == parent_id else second
        child = first if first.id == child_id else second

        if not parent or parent.level != ResellerLevel.LEVEL_1:
            raise ValueError("نماینده سطح ۱ یافت نشد")
        if not child or child.level != ResellerLevel.LEVEL_2:
            raise ValueError("نماینده سطح ۲ یافت نشد")
        if child.parent_reseller_id != parent.id:
            raise ValueError("⛔ این نماینده زیرمجموعه شما نیست")

        if not parent.can_allocate_to_child(gb):
            raise ValueError(
                f"❌ موجودی کافی نیست\n"
                f"اعتبار باقی‌مانده شما: {parent.remaining_credit_gb:.2f} گیگ"
            )

        parent.allocated_to_children_gb += gb
        child.credit_gb += gb
        await self.session.flush()
        return parent, child

    async def reclaim_from_child(self, parent_id: int, child_id: int, gb: Decimal) -> tuple[Reseller, Reseller]:
        """Reclaim unused credit from child back to parent."""
        first_id, second_id = sorted([parent_id, child_id])
        first = await self.get_with_lock(first_id)
        second = await self.get_with_lock(second_id)
        parent = first if first.id == parent_id else second
        child = first if first.id == child_id else second

        reclaimable = child.remaining_credit_gb
        if gb > reclaimable:
            raise ValueError(
                f"❌ حداکثر {reclaimable:.2f} گیگ قابل بازیابی است"
            )
        child.credit_gb -= gb
        parent.allocated_to_children_gb -= gb
        await self.session.flush()
        return parent, child

    async def list_active(self, level: ResellerLevel | None = None) -> list[Reseller]:
        q = (
            select(Reseller)
            .options(selectinload(Reseller.user))
            .where(Reseller.status == ResellerStatus.ACTIVE)
        )
        if level is not None:
            q = q.where(Reseller.level == level)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def list_children(self, parent_id: int) -> list[Reseller]:
        result = await self.session.execute(
            select(Reseller)
            .options(selectinload(Reseller.user))
            .where(Reseller.parent_reseller_id == parent_id)
            .order_by(Reseller.created_at.desc())
        )
        return list(result.scalars().all())

    async def count_children(self, parent_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).where(Reseller.parent_reseller_id == parent_id)
        )
        return result.scalar_one()
