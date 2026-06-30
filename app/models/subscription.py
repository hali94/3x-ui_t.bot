import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Enum, Numeric, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    RENEWED = "RENEWED"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    reseller_id: Mapped[int] = mapped_column(ForeignKey("resellers.id", ondelete="RESTRICT"), nullable=False, index=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="RESTRICT"), nullable=False, index=True)

    volume_gb: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expire_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    xui_client_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    inbound_id: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.ACTIVE)
    link: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="subscriptions")
    reseller: Mapped["Reseller"] = relationship("Reseller", back_populates="subscriptions")
    server: Mapped["Server"] = relationship("Server", back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<Subscription id={self.id} customer_id={self.customer_id} status={self.status}>"
