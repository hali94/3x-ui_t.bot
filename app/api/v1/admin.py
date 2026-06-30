from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, get_db
from app.models.user import User
from app.repositories.reseller import ResellerRepository
from app.schemas.reseller import ResellerCreate, ResellerAddCredit, ResellerResponse, ResellerListResponse
from app.services.reseller import ResellerService

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/resellers", response_model=ResellerResponse)
async def create_reseller(
    body: ResellerCreate,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    service = ResellerService(session)
    try:
        user, reseller = await service.create_reseller(
            telegram_id=body.telegram_id,
            full_name=body.full_name,
            credit_gb=float(body.credit_gb),
            price_per_gb=float(body.price_per_gb),
            max_sale_limit_gb=float(body.max_sale_limit_gb),
            commission_percent=float(body.commission_percent),
            admin_user_id=current_user.id,
        )
        return reseller
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/resellers", response_model=ResellerListResponse)
async def list_resellers(
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    repo = ResellerRepository(session)
    resellers = await repo.list_active()
    return ResellerListResponse(items=resellers, total=len(resellers))


@router.post("/resellers/{reseller_id}/credit", response_model=ResellerResponse)
async def add_credit(
    reseller_id: int,
    body: ResellerAddCredit,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    service = ResellerService(session)
    try:
        reseller = await service.add_credit(reseller_id, float(body.gb), admin_user_id=current_user.id)
        return reseller
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/resellers/{reseller_id}")
async def deactivate_reseller(
    reseller_id: int,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    service = ResellerService(session)
    try:
        await service.deactivate_reseller(reseller_id, admin_user_id=current_user.id)
        return {"detail": "نماینده با موفقیت غیرفعال شد"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
