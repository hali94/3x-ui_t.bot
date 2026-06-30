"""
Reseller hierarchy management service.

Handles creation of L1/L2 resellers, credit allocation, and status changes.
All credit mutations go through the repository's SELECT FOR UPDATE path.
"""

from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reseller import Reseller, ResellerLevel, ResellerStatus
from app.models.user import User, UserRole, UserStatus
from app.repositories.audit import AuditLogRepository
from app.repositories.reseller import ResellerRepository
from app.repositories.user import UserRepository


class ResellerService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.reseller_repo = ResellerRepository(session)
        self.audit_repo = AuditLogRepository(session)

    # ── Admin: create L1 reseller ───────────────────────────────────────────

    async def create_level1_reseller(
        self,
        telegram_id: int,
        full_name: str,
        credit_gb: float,
        buy_price_per_gb: float,
        sell_price_per_gb: float,
        max_child_resellers: int = 10,
        commission_percent: float = 0.0,
        admin_user_id: int | None = None,
    ) -> tuple[User, Reseller]:
        user = await self.user_repo.create_or_update(telegram_id, None, full_name)
        existing = await self.reseller_repo.get_by_user_id(user.id)
        if existing:
            raise ValueError("این کاربر قبلاً نماینده است")

        user.role = UserRole.RESELLER_L1
        user.status = UserStatus.ACTIVE
        await self.session.flush()

        reseller = Reseller(
            user_id=user.id,
            parent_reseller_id=None,
            level=ResellerLevel.LEVEL_1,
            credit_gb=Decimal(str(credit_gb)),
            buy_price_per_gb=Decimal(str(buy_price_per_gb)),
            sell_price_per_gb=Decimal(str(sell_price_per_gb)),
            max_child_resellers=max_child_resellers,
            commission_percent=Decimal(str(commission_percent)),
            status=ResellerStatus.ACTIVE,
        )
        reseller = await self.reseller_repo.create(reseller)

        await self.audit_repo.log(
            action="ADMIN_CREATED_L1_RESELLER",
            user_id=admin_user_id,
            data={
                "new_telegram_id": telegram_id,
                "credit_gb": credit_gb,
                "sell_price_per_gb": sell_price_per_gb,
            },
        )
        return user, reseller

    # ── L1: create L2 reseller under themselves ─────────────────────────────

    async def create_level2_reseller(
        self,
        parent_reseller_id: int,
        telegram_id: int,
        full_name: str,
        credit_gb: float,
        sell_price_per_gb: float,
        parent_user_id: int | None = None,
    ) -> tuple[User, Reseller]:
        parent = await self.reseller_repo.get(parent_reseller_id)
        if not parent or parent.level != ResellerLevel.LEVEL_1:
            raise ValueError("نماینده سطح ۱ یافت نشد")
        if not parent.active:
            raise ValueError("حساب نماینده سطح ۱ غیرفعال است")

        child_count = await self.reseller_repo.count_children(parent_reseller_id)
        if child_count >= parent.max_child_resellers:
            raise ValueError(
                f"❌ به حداکثر تعداد نمایندگان زیرمجموعه ({parent.max_child_resellers}) رسیده‌اید"
            )

        user = await self.user_repo.create_or_update(telegram_id, None, full_name)
        existing = await self.reseller_repo.get_by_user_id(user.id)
        if existing:
            raise ValueError("این کاربر قبلاً نماینده است")

        gb = Decimal(str(credit_gb))
        if not parent.can_allocate_to_child(gb):
            raise ValueError(
                f"❌ موجودی کافی نیست\n"
                f"اعتبار باقی‌مانده شما: {parent.remaining_credit_gb:.2f} گیگ"
            )

        user.role = UserRole.RESELLER_L2
        user.status = UserStatus.ACTIVE
        await self.session.flush()

        child = Reseller(
            user_id=user.id,
            parent_reseller_id=parent_reseller_id,
            level=ResellerLevel.LEVEL_2,
            credit_gb=gb,
            buy_price_per_gb=parent.sell_price_per_gb,  # child buys at parent's sell price
            sell_price_per_gb=Decimal(str(sell_price_per_gb)),
            max_child_resellers=0,  # L2 cannot have children
            status=ResellerStatus.ACTIVE,
        )
        child = await self.reseller_repo.create(child)

        # Lock parent and deduct allocated credit
        parent_locked = await self.reseller_repo.get_with_lock(parent_reseller_id)
        parent_locked.allocated_to_children_gb += gb
        await self.session.flush()

        await self.audit_repo.log(
            action="L1_CREATED_L2_RESELLER",
            user_id=parent_user_id,
            data={
                "parent_reseller_id": parent_reseller_id,
                "child_telegram_id": telegram_id,
                "credit_gb": credit_gb,
                "sell_price_per_gb": sell_price_per_gb,
            },
        )
        return user, child

    # ── Admin: add credit to L1 ─────────────────────────────────────────────

    async def add_credit_to_reseller(
        self,
        reseller_id: int,
        gb: float,
        actor_user_id: int | None = None,
    ) -> Reseller:
        reseller = await self.reseller_repo.add_credit(reseller_id, Decimal(str(gb)))
        await self.audit_repo.log(
            action="CREDIT_ADDED",
            user_id=actor_user_id,
            data={"reseller_id": reseller_id, "added_gb": gb},
        )
        return reseller

    # ── L1: allocate extra credit to existing L2 ───────────────────────────

    async def allocate_credit_to_child(
        self,
        parent_reseller_id: int,
        child_reseller_id: int,
        gb: float,
        actor_user_id: int | None = None,
    ) -> tuple[Reseller, Reseller]:
        parent, child = await self.reseller_repo.allocate_to_child(
            parent_reseller_id, child_reseller_id, Decimal(str(gb))
        )
        await self.audit_repo.log(
            action="L1_ALLOCATED_CREDIT_TO_L2",
            user_id=actor_user_id,
            data={
                "parent_id": parent_reseller_id,
                "child_id": child_reseller_id,
                "allocated_gb": gb,
            },
        )
        return parent, child

    # ── Deactivate ──────────────────────────────────────────────────────────

    async def deactivate_reseller(
        self, reseller_id: int, actor_user_id: int | None = None
    ) -> Reseller:
        reseller = await self.reseller_repo.get_with_lock(reseller_id)
        if not reseller:
            raise ValueError("نماینده یافت نشد")
        reseller.status = ResellerStatus.INACTIVE
        reseller.user.status = UserStatus.INACTIVE
        # Also suspend all children if L1
        if reseller.level == ResellerLevel.LEVEL_1:
            for child in reseller.children:
                child.status = ResellerStatus.SUSPENDED
                child.user.status = UserStatus.INACTIVE
        await self.session.flush()
        await self.audit_repo.log(
            action="RESELLER_DEACTIVATED",
            user_id=actor_user_id,
            data={"reseller_id": reseller_id, "level": reseller.level},
        )
        return reseller
