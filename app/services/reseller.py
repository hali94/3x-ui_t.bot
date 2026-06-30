from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.reseller import Reseller
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

    async def create_reseller(
        self,
        telegram_id: int,
        full_name: str,
        credit_gb: float,
        price_per_gb: float,
        max_sale_limit_gb: float,
        commission_percent: float = 0.0,
        admin_user_id: int | None = None,
    ) -> tuple[User, Reseller]:
        user = await self.user_repo.create_or_update(telegram_id, None, full_name)
        user.role = UserRole.RESELLER
        user.status = UserStatus.ACTIVE
        await self.session.flush()

        reseller = await self.reseller_repo.get_by_user_id(user.id)
        if reseller:
            raise ValueError("این کاربر قبلاً نماینده است")

        reseller = Reseller(
            user_id=user.id,
            credit_gb=Decimal(str(credit_gb)),
            price_per_gb=Decimal(str(price_per_gb)),
            max_sale_limit_gb=Decimal(str(max_sale_limit_gb)),
            commission_percent=Decimal(str(commission_percent)),
            active=True,
        )
        reseller = await self.reseller_repo.create(reseller)

        await self.audit_repo.log(
            action="ADMIN_CREATED_RESELLER",
            user_id=admin_user_id,
            data={"new_reseller_telegram_id": telegram_id, "credit_gb": credit_gb},
        )
        return user, reseller

    async def add_credit(
        self,
        reseller_id: int,
        gb: float,
        admin_user_id: int | None = None,
    ) -> Reseller:
        reseller = await self.reseller_repo.add_credit(reseller_id, Decimal(str(gb)))
        if not reseller:
            raise ValueError("نماینده یافت نشد")
        await self.audit_repo.log(
            action="ADMIN_ADDED_CREDIT",
            user_id=admin_user_id,
            data={"reseller_id": reseller_id, "added_gb": gb},
        )
        return reseller

    async def deactivate_reseller(self, reseller_id: int, admin_user_id: int | None = None) -> Reseller:
        reseller = await self.reseller_repo.get(reseller_id)
        if not reseller:
            raise ValueError("نماینده یافت نشد")
        reseller.active = False
        reseller.user.status = UserStatus.INACTIVE
        await self.session.flush()
        await self.audit_repo.log(
            action="ADMIN_DEACTIVATED_RESELLER",
            user_id=admin_user_id,
            data={"reseller_id": reseller_id},
        )
        return reseller
