"""
Celery notification tasks.

FIX: Uses asyncio.run() instead of deprecated get_event_loop().run_until_complete()
     which raises RuntimeError in Python 3.12 when no current event loop exists.
FIX: Notification deduplication — won't spam the same user twice in 24h.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.workers.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.tasks.notifications.check_expiring_subscriptions",
    bind=True, max_retries=3, default_retry_delay=60,
)
def check_expiring_subscriptions(self):
    try:
        asyncio.run(_async_check_expiring())
    except Exception as exc:
        logger.exception("check_expiring_subscriptions_failed")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.workers.tasks.notifications.check_traffic_thresholds",
    bind=True, max_retries=3, default_retry_delay=60,
)
def check_traffic_thresholds(self):
    try:
        asyncio.run(_async_check_traffic())
    except Exception as exc:
        logger.exception("check_traffic_thresholds_failed")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.workers.tasks.notifications.send_pending_notifications",
    bind=True, max_retries=3, default_retry_delay=30,
)
def send_pending_notifications(self):
    try:
        asyncio.run(_async_send_pending())
    except Exception as exc:
        logger.exception("send_pending_notifications_failed")
        raise self.retry(exc=exc)


# ── Async implementations ────────────────────────────────────────────────────

async def _async_check_expiring():
    from app.database import async_session_factory
    from app.services.notification import NotificationService
    async with async_session_factory() as session:
        service = NotificationService(session)
        notifs = await service.check_expiring_subscriptions(days=settings.EXPIRY_WARN_DAYS)
        await session.commit()
    logger.info("expiry_notifications_created", extra={"count": len(notifs)})


async def _async_check_traffic():
    from app.database import async_session_factory
    from app.services.notification import NotificationService
    async with async_session_factory() as session:
        service = NotificationService(session)
        notifs = await service.check_traffic_thresholds()
        await session.commit()
    logger.info("traffic_notifications_created", extra={"count": len(notifs)})


async def _async_send_pending():
    from app.database import async_session_factory
    from app.models.notification import Notification, NotificationStatus
    from app.repositories.notification import NotificationRepository
    from app.repositories.user import UserRepository
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from sqlalchemy import select

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    sent_count = failed_count = 0

    try:
        async with async_session_factory() as session:
            notif_repo = NotificationRepository(session)
            pending = await notif_repo.get_pending(limit=50)

            for notif in pending:
                try:
                    user_repo = UserRepository(session)
                    user = await user_repo.get(notif.user_id)
                    if user and user.telegram_id:
                        await bot.send_message(chat_id=user.telegram_id, text=notif.message)
                    notif.status = NotificationStatus.SENT
                    notif.sent_at = datetime.now(timezone.utc)
                    sent_count += 1
                except Exception as exc:
                    logger.warning(
                        "notification_send_failed",
                        extra={"notif_id": notif.id, "error": str(exc)},
                    )
                    notif.status = NotificationStatus.FAILED
                    failed_count += 1

            await session.commit()
    finally:
        await bot.session.close()

    logger.info(
        "pending_notifications_processed",
        extra={"sent": sent_count, "failed": failed_count},
    )
