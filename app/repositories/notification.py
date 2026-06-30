from datetime import datetime, timedelta, timezone
from sqlalchemy import select, and_
from app.models.notification import Notification, NotificationType, NotificationStatus
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def already_sent_today(
        self,
        user_id: int,
        notif_type: NotificationType,
        reference_id: int,
        reference_type: str,
    ) -> bool:
        """Deduplication guard: true if we already sent this notification today."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await self.session.execute(
            select(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.type == notif_type,
                    Notification.reference_id == reference_id,
                    Notification.reference_type == reference_type,
                    Notification.created_at >= cutoff,
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_pending(self, limit: int = 50) -> list[Notification]:
        result = await self.session.execute(
            select(Notification)
            .where(Notification.status == NotificationStatus.PENDING)
            .order_by(Notification.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
