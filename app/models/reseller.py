from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, BigInteger, Numeric, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Reseller(Base):
    __tablename__ = "resellers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    credit_gb: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    used_gb: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)

    price_per_gb: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    max_sale_limit_gb: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    commission_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="reseller_profile")
    customers: Mapped[list["Customer"]] = relationship("Customer", back_populates="reseller")
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="reseller")
    sales: Mapped[list["Sale"]] = relationship("Sale", back_populates="reseller")

    @property
    def remaining_credit_gb(self) -> Decimal:
        return self.credit_gb - self.used_gb

    def can_sell(self, gb: Decimal) -> bool:
        return self.active and self.remaining_credit_gb >= gb

    def __repr__(self) -> str:
        return f"<Reseller id={self.id} credit={self.credit_gb} used={self.used_gb}>"
