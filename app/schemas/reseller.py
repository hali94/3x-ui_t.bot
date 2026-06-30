from decimal import Decimal
from pydantic import BaseModel, Field


class ResellerL1Create(BaseModel):
    telegram_id: int
    full_name: str = Field(min_length=2, max_length=512)
    credit_gb: Decimal = Field(gt=0)
    buy_price_per_gb: Decimal = Field(ge=0)
    sell_price_per_gb: Decimal = Field(ge=0)
    max_child_resellers: int = Field(default=10, ge=0, le=500)
    commission_percent: Decimal = Field(ge=0, le=100, default=0)


class ResellerL2Create(BaseModel):
    parent_reseller_id: int
    telegram_id: int
    full_name: str = Field(min_length=2, max_length=512)
    credit_gb: Decimal = Field(gt=0)
    sell_price_per_gb: Decimal = Field(ge=0)


class ResellerAddCredit(BaseModel):
    gb: Decimal = Field(gt=0)


class AllocateCreditToChild(BaseModel):
    child_reseller_id: int
    gb: Decimal = Field(gt=0)


class ResellerResponse(BaseModel):
    id: int
    user_id: int
    parent_reseller_id: int | None
    level: str
    credit_gb: Decimal
    used_gb: Decimal
    allocated_to_children_gb: Decimal
    remaining_credit_gb: Decimal
    buy_price_per_gb: Decimal
    sell_price_per_gb: Decimal
    max_child_resellers: int
    commission_percent: Decimal
    status: str

    model_config = {"from_attributes": True}
