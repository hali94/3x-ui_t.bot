from decimal import Decimal
from pydantic import BaseModel, Field, field_validator


class ResellerCreate(BaseModel):
    telegram_id: int
    full_name: str = Field(min_length=2, max_length=512)
    credit_gb: Decimal = Field(gt=0)
    price_per_gb: Decimal = Field(ge=0)
    max_sale_limit_gb: Decimal = Field(gt=0)
    commission_percent: Decimal = Field(ge=0, le=100, default=0)


class ResellerAddCredit(BaseModel):
    gb: Decimal = Field(gt=0)


class ResellerResponse(BaseModel):
    id: int
    user_id: int
    credit_gb: Decimal
    used_gb: Decimal
    remaining_credit_gb: Decimal
    price_per_gb: Decimal
    max_sale_limit_gb: Decimal
    commission_percent: Decimal
    active: bool

    model_config = {"from_attributes": True}


class ResellerListResponse(BaseModel):
    items: list[ResellerResponse]
    total: int
