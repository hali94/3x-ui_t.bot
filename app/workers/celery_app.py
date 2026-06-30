from celery import Celery
from app.config import settings

celery_app = Celery(
    "vpn_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks.notifications", "app.workers.tasks.traffic_sync"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tehran",
    enable_utc=True,
    worker_concurrency=settings.WORKER_CONCURRENCY,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    beat_schedule={
        "check-expiring-subscriptions": {
            "task": "app.workers.tasks.notifications.check_expiring_subscriptions",
            "schedule": settings.NOTIFICATION_CHECK_INTERVAL_HOURS * 3600,
        },
        "check-traffic-thresholds": {
            "task": "app.workers.tasks.notifications.check_traffic_thresholds",
            "schedule": settings.NOTIFICATION_CHECK_INTERVAL_HOURS * 3600,
        },
        "send-pending-notifications": {
            "task": "app.workers.tasks.notifications.send_pending_notifications",
            "schedule": 300,  # every 5 minutes
        },
        "sync-traffic-from-xui": {
            "task": "app.workers.tasks.traffic_sync.sync_all_traffic",
            "schedule": 1800,  # every 30 minutes
        },
    },
)
