import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, String, Enum, Numeric, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CustomerStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    DISABLED = "DISABLED"
    TRAFFIC_EXHAUSTED = "TRAFFIC_EXHAUSTED"


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    reseller_id: Mapped[int] = mapped_column(ForeignKey("resellers.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    email: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    protocol: Mapped[str] = mapped_column(String(50), nullable=False, default="vless")
    volume_gb: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    used_gb: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    expire_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[CustomerStatus] = mapped_column(Enum(CustomerStatus), nullable=False, default=CustomerStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    reseller: Mapped["Reseller"] = relationship("Reseller", back_populates="customers")
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="customer")

    @property
    def traffic_percent(self) -> float:
        if self.volume_gb == 0:
            return 100.0
        return float(self.used_gb / self.volume_gb * 100)

    @property
    def remaining_gb(self) -> Decimal:
        return max(Decimal("0"), self.volume_gb - self.used_gb)

    def __repr__(self) -> str:
        return f"<Customer id={self.id} email={self.email} status={self.status}>"
