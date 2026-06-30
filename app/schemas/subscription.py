from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class SubscriptionCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=512)
    volume_gb: float = Field(gt=0, le=10000)
    duration_days: int = Field(gt=0, le=3650)
    server_id: int
    customer_telegram_id: int | None = None


class SubscriptionRenew(BaseModel):
    customer_id: int
    volume_gb: float = Field(gt=0, le=10000)
    duration_days: int = Field(gt=0, le=3650)
    server_id: int


class SubscriptionResponse(BaseModel):
    id: int
    customer_id: int
    reseller_id: int
    server_id: int
    volume_gb: Decimal
    price: Decimal
    start_date: datetime
    expire_date: datetime
    status: str
    link: str | None

    model_config = {"from_attributes": True}


class CustomerResponse(BaseModel):
    id: int
    name: str
    email: str
    uuid: str
    volume_gb: Decimal
    used_gb: Decimal
    traffic_percent: float
    expire_date: datetime | None
    status: str

    model_config = {"from_attributes": True}
