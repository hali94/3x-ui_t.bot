import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.notification import Notification, NotificationType, NotificationStatus
from app.repositories.customer import CustomerRepository
from app.repositories.user import UserRepository
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.customer_repo = CustomerRepository(session)
        self.user_repo = UserRepository(session)

    async def check_expiring_subscriptions(self, days: int = 3) -> list[Notification]:
        customers = await self.customer_repo.get_expiring_soon(days)
        notifications = []
        for customer in customers:
            remaining_days = (customer.expire_date - datetime.now(timezone.utc)).days
            reseller_user = await self.user_repo.get_with_reseller(customer.reseller_id)
            if not reseller_user:
                continue
            msg = (
                f"⚠️ هشدار انقضا\n\n"
                f"👤 کاربر: {customer.name}\n"
                f"📧 ایمیل: {customer.email}\n"
                f"⏳ {remaining_days} روز دیگر اشتراک منقضی می‌شود\n\n"
                f"لطفاً اشتراک را تمدید کنید."
            )
            notif = Notification(
                user_id=reseller_user.id,
                type=NotificationType.EXPIRY_WARNING,
                message=msg,
                status=NotificationStatus.PENDING,
            )
            self.session.add(notif)
            notifications.append(notif)
        await self.session.flush()
        return notifications

    async def check_traffic_thresholds(self) -> list[Notification]:
        notifications = []
        thresholds = [
            (80, NotificationType.TRAFFIC_80, "۸۰٪"),
            (90, NotificationType.TRAFFIC_90, "۹۰٪"),
            (100, NotificationType.TRAFFIC_100, "۱۰۰٪"),
        ]
        for percent, notif_type, label in thresholds:
            customers = await self.customer_repo.get_by_traffic_threshold(float(percent))
            for customer in customers:
                reseller_user = await self.user_repo.get_with_reseller(customer.reseller_id)
                if not reseller_user:
                    continue
                msg = (
                    f"🔴 هشدار مصرف\n\n"
                    f"👤 کاربر: {customer.name}\n"
                    f"📊 مصرف به {label} رسیده است\n"
                    f"💾 مصرف: {customer.used_gb:.2f} از {customer.volume_gb:.2f} گیگ"
                )
                notif = Notification(
                    user_id=reseller_user.id,
                    type=notif_type,
                    message=msg,
                    status=NotificationStatus.PENDING,
                )
                self.session.add(notif)
                notifications.append(notif)
        await self.session.flush()
        return notifications
