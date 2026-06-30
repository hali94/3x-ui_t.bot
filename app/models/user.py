import enum
from datetime import datetime
from sqlalchemy import BigInteger, String, Enum, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    RESELLER_L1 = "RESELLER_L1"
    RESELLER_L2 = "RESELLER_L2"
    CUSTOMER = "CUSTOMER"

    # Legacy alias kept for migration compatibility
    RESELLER = "RESELLER"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    BANNED = "BANNED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.CUSTOMER)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), nullable=False, default=UserStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    reseller_profile: Mapped["Reseller | None"] = relationship(
        "Reseller", back_populates="user", uselist=False
    )
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="user")
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} telegram_id={self.telegram_id} role={self.role}>"

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_reseller(self) -> bool:
        return self.role in (UserRole.RESELLER_L1, UserRole.RESELLER_L2, UserRole.RESELLER)

    @property
    def is_reseller_l1(self) -> bool:
        return self.role in (UserRole.RESELLER_L1, UserRole.RESELLER)

    @property
    def is_reseller_l2(self) -> bool:
        return self.role == UserRole.RESELLER_L2
