import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, Numeric, Boolean, ForeignKey, DateTime, func, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ResellerLevel(str, enum.Enum):
    LEVEL_1 = "LEVEL_1"
    LEVEL_2 = "LEVEL_2"


class ResellerStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class Reseller(Base):
    __tablename__ = "resellers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    parent_reseller_id: Mapped[int | None] = mapped_column(
        ForeignKey("resellers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    level: Mapped[ResellerLevel] = mapped_column(
        Enum(ResellerLevel), nullable=False, default=ResellerLevel.LEVEL_1
    )

    # Credit tracking
    # credit_gb  = total GB assigned to this reseller
    # used_gb    = GB actually sold to customers (NOT allocated to children)
    # allocated_to_children_gb = GB given to Level-2 resellers
    credit_gb: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    used_gb: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    allocated_to_children_gb: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)

    # Pricing: buy_price = what they pay per GB, sell_price = what they charge customers
    buy_price_per_gb: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    sell_price_per_gb: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    max_child_resellers: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    commission_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    status: Mapped[ResellerStatus] = mapped_column(
        Enum(ResellerStatus), nullable=False, default=ResellerStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Self-referential hierarchy
    parent: Mapped["Reseller | None"] = relationship(
        "Reseller", remote_side="Reseller.id", back_populates="children", foreign_keys=[parent_reseller_id]
    )
    children: Mapped[list["Reseller"]] = relationship(
        "Reseller", back_populates="parent", foreign_keys=[parent_reseller_id]
    )

    # Other relationships
    user: Mapped["User"] = relationship("User", back_populates="reseller_profile")
    customers: Mapped[list["Customer"]] = relationship("Customer", back_populates="reseller")
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="reseller")
    sales: Mapped[list["Sale"]] = relationship("Sale", back_populates="reseller")

    # ── Credit helpers ──────────────────────────────────────────────────────

    @property
    def active(self) -> bool:
        return self.status == ResellerStatus.ACTIVE

    @property
    def remaining_credit_gb(self) -> Decimal:
        """GB available for this reseller to sell to customers (excludes what was given to children)."""
        return self.credit_gb - self.used_gb - self.allocated_to_children_gb

    @property
    def is_level_1(self) -> bool:
        return self.level == ResellerLevel.LEVEL_1

    @property
    def is_level_2(self) -> bool:
        return self.level == ResellerLevel.LEVEL_2

    def can_sell(self, gb: Decimal) -> bool:
        return self.active and self.remaining_credit_gb >= gb

    def can_allocate_to_child(self, gb: Decimal) -> bool:
        return self.is_level_1 and self.active and self.remaining_credit_gb >= gb

    def __repr__(self) -> str:
        return (
            f"<Reseller id={self.id} level={self.level} "
            f"credit={self.credit_gb} used={self.used_gb} allocated={self.allocated_to_children_gb}>"
        )
