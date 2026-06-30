from datetime import datetime
from decimal import Decimal
from sqlalchemy import Numeric, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reseller_id: Mapped[int] = mapped_column(
        ForeignKey("resellers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    gb: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    buy_price_per_gb: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    sell_price_per_gb: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    profit: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    reseller: Mapped["Reseller"] = relationship("Reseller", back_populates="sales")
    customer: Mapped["Customer"] = relationship("Customer")
    subscription: Mapped["Subscription"] = relationship("Subscription")

    def __repr__(self) -> str:
        return f"<Sale id={self.id} reseller_id={self.reseller_id} gb={self.gb} profit={self.profit}>"
