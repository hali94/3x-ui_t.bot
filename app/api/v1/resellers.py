from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_reseller, require_l1_reseller
from app.models.server import Server
from app.models.user import User
from app.repositories.customer import CustomerRepository
from app.repositories.reseller import ResellerRepository
from app.schemas.reseller import AllocateCreditToChild, ResellerL2Create, ResellerResponse
from app.schemas.subscription import CustomerResponse, SubscriptionCreate, SubscriptionResponse, SubscriptionRenew
from app.security.rbac import check_reseller_owns_customer, check_l1_owns_child
from app.services.reseller import ResellerService
from app.services.subscription import SubscriptionService

router = APIRouter(prefix="/reseller", tags=["Reseller"])


async def _get_server(server_id: int, session: AsyncSession) -> Server:
    result = await session.execute(
        select(Server).where(Server.id == server_id, Server.active == True)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="سرور یافت نشد")
    return server


@router.post("/subscriptions", response_model=SubscriptionResponse)
async def create_subscription(
    body: SubscriptionCreate,
    current_user: User = Depends(require_reseller),
    session: AsyncSession = Depends(get_db),
):
    server = await _get_server(body.server_id, session)
    service = SubscriptionService(session)
    try:
        _, sub, _ = await service.create_subscription(
            reseller_user_id=current_user.id,
            customer_name=body.customer_name,
            volume_gb=body.volume_gb,
            duration_days=body.duration_days,
            server=server,
            customer_telegram_id=body.customer_telegram_id,
        )
        return sub
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/subscriptions/renew", response_model=SubscriptionResponse)
async def renew_subscription(
    body: SubscriptionRenew,
    current_user: User = Depends(require_reseller),
    session: AsyncSession = Depends(get_db),
):
    server = await _get_server(body.server_id, session)
    service = SubscriptionService(session)
    try:
        _, sub = await service.renew_subscription(
            reseller_user_id=current_user.id,
            customer_id=body.customer_id,
            volume_gb=body.volume_gb,
            duration_days=body.duration_days,
            server=server,
        )
        return sub
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/customers", response_model=list[CustomerResponse])
async def list_my_customers(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_reseller),
    session: AsyncSession = Depends(get_db),
):
    repo = ResellerRepository(session)
    reseller = await repo.get_by_user_id(current_user.id)
    if not reseller:
        raise HTTPException(status_code=404, detail="پروفایل نماینده یافت نشد")
    return await CustomerRepository(session).list_by_reseller(reseller.id, limit=limit, offset=offset)


# ── L1-only: create L2 and allocate credit ──────────────────────────────────

@router.post("/sub-resellers", response_model=ResellerResponse, summary="ساخت نماینده سطح ۲")
async def create_l2_reseller(
    body: ResellerL2Create,
    current_user: User = Depends(require_l1_reseller),
    session: AsyncSession = Depends(get_db),
):
    repo = ResellerRepository(session)
    parent = await repo.get_by_user_id(current_user.id)
    if not parent:
        raise HTTPException(status_code=404, detail="پروفایل نماینده یافت نشد")
    if parent.id != body.parent_reseller_id:
        raise HTTPException(status_code=403, detail="⛔ شما فقط می‌توانید زیرنماینده برای خود بسازید")
    service = ResellerService(session)
    try:
        _, child = await service.create_level2_reseller(
            parent_reseller_id=parent.id,
            telegram_id=body.telegram_id,
            full_name=body.full_name,
            credit_gb=float(body.credit_gb),
            sell_price_per_gb=float(body.sell_price_per_gb),
            parent_user_id=current_user.id,
        )
        return child
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/sub-resellers/credit", summary="انتقال اعتبار به نماینده سطح ۲")
async def allocate_credit(
    body: AllocateCreditToChild,
    current_user: User = Depends(require_l1_reseller),
    session: AsyncSession = Depends(get_db),
):
    repo = ResellerRepository(session)
    parent = await repo.get_by_user_id(current_user.id)
    if not parent:
        raise HTTPException(status_code=404, detail="پروفایل نماینده یافت نشد")
    child = await repo.get(body.child_reseller_id)
    if not check_l1_owns_child(parent, child):
        raise HTTPException(status_code=403, detail="⛔ این نماینده زیرمجموعه شما نیست")
    service = ResellerService(session)
    try:
        _, child_updated = await service.allocate_credit_to_child(
            parent_reseller_id=parent.id,
            child_reseller_id=body.child_reseller_id,
            gb=float(body.gb),
            actor_user_id=current_user.id,
        )
        return {"detail": "اعتبار منتقل شد", "child_remaining_gb": float(child_updated.remaining_credit_gb)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/sub-resellers", response_model=list[ResellerResponse], summary="لیست نمایندگان زیرمجموعه")
async def list_sub_resellers(
    current_user: User = Depends(require_l1_reseller),
    session: AsyncSession = Depends(get_db),
):
    repo = ResellerRepository(session)
    parent = await repo.get_by_user_id(current_user.id)
    if not parent:
        raise HTTPException(status_code=404, detail="پروفایل نماینده یافت نشد")
    return await repo.list_children(parent.id)
