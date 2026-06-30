from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_reseller, get_db
from app.models.server import Server
from app.models.user import User
from app.repositories.customer import CustomerRepository
from app.repositories.reseller import ResellerRepository
from app.schemas.subscription import CustomerResponse, SubscriptionCreate, SubscriptionResponse, SubscriptionRenew
from app.services.subscription import SubscriptionService

router = APIRouter(prefix="/reseller", tags=["Reseller"])


@router.post("/subscriptions", response_model=SubscriptionResponse)
async def create_subscription(
    body: SubscriptionCreate,
    current_user: User = Depends(require_reseller),
    session: AsyncSession = Depends(get_db),
):
    server_result = await session.execute(select(Server).where(Server.id == body.server_id, Server.active == True))
    server = server_result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="سرور یافت نشد")
    service = SubscriptionService(session)
    try:
        customer, sub, link = await service.create_subscription(
            reseller_user_id=current_user.id,
            customer_name=body.customer_name,
            volume_gb=body.volume_gb,
            duration_days=body.duration_days,
            server=server,
            customer_telegram_id=body.customer_telegram_id,
        )
        return sub
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/subscriptions/renew", response_model=SubscriptionResponse)
async def renew_subscription(
    body: SubscriptionRenew,
    current_user: User = Depends(require_reseller),
    session: AsyncSession = Depends(get_db),
):
    server_result = await session.execute(select(Server).where(Server.id == body.server_id, Server.active == True))
    server = server_result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="سرور یافت نشد")
    service = SubscriptionService(session)
    try:
        customer, sub = await service.renew_subscription(
            reseller_user_id=current_user.id,
            customer_id=body.customer_id,
            volume_gb=body.volume_gb,
            duration_days=body.duration_days,
            server=server,
        )
        return sub
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/customers", response_model=list[CustomerResponse])
async def list_customers(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_reseller),
    session: AsyncSession = Depends(get_db),
):
    reseller_repo = ResellerRepository(session)
    reseller = await reseller_repo.get_by_user_id(current_user.id)
    if not reseller:
        raise HTTPException(status_code=404, detail="پروفایل نماینده یافت نشد")
    customer_repo = CustomerRepository(session)
    return await customer_repo.list_by_reseller(reseller.id, limit=limit, offset=offset)
