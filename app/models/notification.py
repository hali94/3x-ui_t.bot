import enum
from datetime import datetime
from sqlalchemy import String, Enum, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class NotificationType(str, enum.Enum):
    EXPIRY_WARNING = "EXPIRY_WARNING"
    TRAFFIC_80 = "TRAFFIC_80"
    TRAFFIC_90 = "TRAFFIC_90"
    TRAFFIC_100 = "TRAFFIC_100"
    SUBSCRIPTION_CREATED = "SUBSCRIPTION_CREATED"
    SUBSCRIPTION_RENEWED = "SUBSCRIPTION_RENEWED"
    CREDIT_ADDED = "CREDIT_ADDED"
    SYSTEM = "SYSTEM"


class NotificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(Enum(NotificationStatus), nullable=False, default=NotificationStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")

    def __repr__(self) -> str:
        return f"<Notification id={self.id} type={self.type} status={self.status}>"
