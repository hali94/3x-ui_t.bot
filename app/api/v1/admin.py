from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, get_db
from app.models.user import User
from app.repositories.reseller import ResellerRepository
from app.schemas.reseller import (
    AllocateCreditToChild,
    ResellerAddCredit,
    ResellerL1Create,
    ResellerL2Create,
    ResellerResponse,
)
from app.services.reseller import ResellerService

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/resellers/level1", response_model=ResellerResponse, summary="ساخت نماینده سطح ۱")
async def create_l1_reseller(
    body: ResellerL1Create,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    service = ResellerService(session)
    try:
        _, reseller = await service.create_level1_reseller(
            telegram_id=body.telegram_id,
            full_name=body.full_name,
            credit_gb=float(body.credit_gb),
            buy_price_per_gb=float(body.buy_price_per_gb),
            sell_price_per_gb=float(body.sell_price_per_gb),
            max_child_resellers=body.max_child_resellers,
            commission_percent=float(body.commission_percent),
            admin_user_id=current_user.id,
        )
        return reseller
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/resellers", response_model=list[ResellerResponse], summary="لیست نمایندگان")
async def list_resellers(
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    repo = ResellerRepository(session)
    return await repo.list_active()


@router.post("/resellers/{reseller_id}/credit", response_model=ResellerResponse, summary="افزودن اعتبار")
async def add_credit(
    reseller_id: int,
    body: ResellerAddCredit,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    service = ResellerService(session)
    try:
        return await service.add_credit_to_reseller(
            reseller_id, float(body.gb), actor_user_id=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/resellers/{reseller_id}", summary="غیرفعال کردن نماینده")
async def deactivate_reseller(
    reseller_id: int,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    service = ResellerService(session)
    try:
        await service.deactivate_reseller(reseller_id, actor_user_id=current_user.id)
        return {"detail": "نماینده با موفقیت غیرفعال شد"}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
