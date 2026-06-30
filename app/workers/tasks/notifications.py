"""
Celery tasks for expiry and traffic notifications.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.workers.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(name="app.workers.tasks.notifications.check_expiring_subscriptions", bind=True, max_retries=3)
def check_expiring_subscriptions(self):
    """Find customers expiring within EXPIRY_WARN_DAYS and create notifications."""
    try:
        _run(_async_check_expiring())
    except Exception as exc:
        logger.exception("check_expiring_subscriptions_failed")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.workers.tasks.notifications.check_traffic_thresholds", bind=True, max_retries=3)
def check_traffic_thresholds(self):
    try:
        _run(_async_check_traffic())
    except Exception as exc:
        logger.exception("check_traffic_thresholds_failed")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.workers.tasks.notifications.send_pending_notifications", bind=True, max_retries=3)
def send_pending_notifications(self):
    try:
        _run(_async_send_pending())
    except Exception as exc:
        logger.exception("send_pending_notifications_failed")
        raise self.retry(exc=exc, countdown=30)


async def _async_check_expiring():
    from app.database import async_session_factory
    from app.services.notification import NotificationService
    async with async_session_factory() as session:
        service = NotificationService(session)
        notifs = await service.check_expiring_subscriptions(days=settings.EXPIRY_WARN_DAYS)
        await session.commit()
        logger.info("expiry_notifications_created", count=len(notifs))


async def _async_check_traffic():
    from app.database import async_session_factory
    from app.services.notification import NotificationService
    async with async_session_factory() as session:
        service = NotificationService(session)
        notifs = await service.check_traffic_thresholds()
        await session.commit()
        logger.info("traffic_notifications_created", count=len(notifs))


async def _async_send_pending():
    from app.database import async_session_factory
    from app.models.notification import Notification, NotificationStatus
    from sqlalchemy import select, update
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    async with async_session_factory() as session:
        result = await session.execute(
            select(Notification)
            .where(Notification.status == NotificationStatus.PENDING)
            .limit(50)
        )
        pending = list(result.scalars().all())

        for notif in pending:
            try:
                from app.repositories.user import UserRepository
                user_repo = UserRepository(session)
                user = await user_repo.get(notif.user_id)
                if user and user.telegram_id:
                    await bot.send_message(user.telegram_id, notif.message)
                notif.status = NotificationStatus.SENT
                notif.sent_at = datetime.now(timezone.utc)
            except Exception as exc:
                logger.warning("notification_send_failed", notif_id=notif.id, error=str(exc))
                notif.status = NotificationStatus.FAILED

        await session.commit()

    await bot.session.close()
    logger.info("pending_notifications_processed", count=len(pending))
