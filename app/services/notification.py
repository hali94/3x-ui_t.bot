"""
Notification service with deduplication.

Prevents duplicate notifications by checking if the same type+reference
was already created within the past 24 hours.
"""

import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType, NotificationStatus
from app.repositories.customer import CustomerRepository
from app.repositories.notification import NotificationRepository
from app.repositories.user import UserRepository

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.customer_repo = CustomerRepository(session)
        self.user_repo = UserRepository(session)
        self.notif_repo = NotificationRepository(session)

    async def _create_if_not_duplicate(
        self,
        user_id: int,
        notif_type: NotificationType,
        message: str,
        reference_id: int,
        reference_type: str,
    ) -> Notification | None:
        already = await self.notif_repo.already_sent_today(
            user_id, notif_type, reference_id, reference_type
        )
        if already:
            return None
        notif = Notification(
            user_id=user_id,
            type=notif_type,
            message=message,
            status=NotificationStatus.PENDING,
            reference_id=reference_id,
            reference_type=reference_type,
        )
        self.session.add(notif)
        return notif

    async def check_expiring_subscriptions(self, days: int = 3) -> list[Notification]:
        customers = await self.customer_repo.get_expiring_soon(days)
        notifications: list[Notification] = []

        for customer in customers:
            if not customer.expire_date:
                continue
            remaining_days = (customer.expire_date - datetime.now(timezone.utc)).days

            # Notify the owning reseller
            reseller_user = await self.user_repo.get_with_reseller(customer.reseller_id)
            if not reseller_user:
                continue

            msg = (
                f"⚠️ هشدار انقضا\n\n"
                f"👤 مشتری: {customer.name}\n"
                f"📧 ایمیل: {customer.email}\n"
                f"⏳ {remaining_days} روز دیگر اشتراک منقضی می‌شود\n\n"
                f"لطفاً اشتراک را تمدید کنید."
            )
            notif = await self._create_if_not_duplicate(
                user_id=reseller_user.id,
                notif_type=NotificationType.EXPIRY_WARNING,
                message=msg,
                reference_id=customer.id,
                reference_type="customer",
            )
            if notif:
                notifications.append(notif)

            # Also notify L1 parent if the reseller is L2
            reseller_profile = reseller_user.reseller_profile
            if (
                reseller_profile
                and reseller_profile.parent_reseller_id
            ):
                from app.repositories.reseller import ResellerRepository
                from app.models.reseller import ResellerLevel
                reseller_repo = ResellerRepository(self.session)
                parent = await reseller_repo.get(reseller_profile.parent_reseller_id)
                if parent:
                    parent_user = await self.user_repo.get_with_reseller(parent.user_id)
                    if parent_user:
                        parent_msg = (
                            f"⚠️ هشدار انقضا (نماینده زیرمجموعه)\n\n"
                            f"👥 نماینده: {reseller_user.full_name}\n"
                            f"👤 مشتری: {customer.name}\n"
                            f"⏳ {remaining_days} روز دیگر اشتراک منقضی می‌شود"
                        )
                        parent_notif = await self._create_if_not_duplicate(
                            user_id=parent_user.id,
                            notif_type=NotificationType.EXPIRY_WARNING,
                            message=parent_msg,
                            reference_id=customer.id,
                            reference_type="customer_parent",
                        )
                        if parent_notif:
                            notifications.append(parent_notif)

        await self.session.flush()
        return notifications

    async def check_traffic_thresholds(self) -> list[Notification]:
        notifications: list[Notification] = []
        thresholds = [
            (80.0, NotificationType.TRAFFIC_80, "۸۰٪"),
            (90.0, NotificationType.TRAFFIC_90, "۹۰٪"),
            (100.0, NotificationType.TRAFFIC_100, "۱۰۰٪"),
        ]

        for percent, notif_type, label in thresholds:
            customers = await self.customer_repo.get_by_traffic_threshold(percent)
            for customer in customers:
                reseller_user = await self.user_repo.get_with_reseller(customer.reseller_id)
                if not reseller_user:
                    continue
                msg = (
                    f"🔴 هشدار مصرف\n\n"
                    f"👤 مشتری: {customer.name}\n"
                    f"📊 مصرف به {label} رسیده است\n"
                    f"💾 مصرف: {customer.used_gb:.2f} از {customer.volume_gb:.2f} گیگ"
                )
                notif = await self._create_if_not_duplicate(
                    user_id=reseller_user.id,
                    notif_type=notif_type,
                    message=msg,
                    reference_id=customer.id,
                    reference_type="customer",
                )
                if notif:
                    notifications.append(notif)

        await self.session.flush()
        return notifications

    async def notify_l1_of_l2_sale(
        self,
        parent_reseller_user_id: int,
        l2_reseller_name: str,
        customer_name: str,
        volume_gb: float,
        amount: float,
        sale_id: int,
    ) -> None:
        msg = (
            f"💰 فروش نماینده زیرمجموعه\n\n"
            f"👥 نماینده: {l2_reseller_name}\n"
            f"👤 مشتری: {customer_name}\n"
            f"💾 حجم: {volume_gb:.1f} گیگ\n"
            f"💵 مبلغ: {amount:,.0f} تومان"
        )
        await self._create_if_not_duplicate(
            user_id=parent_reseller_user_id,
            notif_type=NotificationType.L2_SALE,
            message=msg,
            reference_id=sale_id,
            reference_type="sale",
        )
        await self.session.flush()
