"""
Periodic task: sync traffic from all active 3x-ui servers.

FIX: asyncio.run() replaces deprecated get_event_loop().run_until_complete()
"""

import asyncio
import logging
from decimal import Decimal

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.tasks.traffic_sync.sync_all_traffic",
    bind=True, max_retries=3, default_retry_delay=120,
)
def sync_all_traffic(self):
    try:
        asyncio.run(_async_sync_all())
    except Exception as exc:
        logger.exception("sync_all_traffic_failed")
        raise self.retry(exc=exc)


async def _async_sync_all():
    from sqlalchemy import select
    from app.database import async_session_factory
    from app.models.server import Server
    from app.models.customer import Customer, CustomerStatus
    from app.models.subscription import Subscription, SubscriptionStatus
    from app.integrations.xui.client import XUIClientFactory

    async with async_session_factory() as session:
        servers_result = await session.execute(
            select(Server).where(Server.active == True)
        )
        servers = list(servers_result.scalars().all())

        total_updated = 0
        for server in servers:
            try:
                async with XUIClientFactory.create(
                    server.xui_url, server.xui_username, server.xui_password
                ) as xui:
                    subs_result = await session.execute(
                        select(Subscription).where(
                            Subscription.server_id == server.id,
                            Subscription.status == SubscriptionStatus.ACTIVE,
                        )
                    )
                    active_subs = list(subs_result.scalars().all())

                    for sub in active_subs:
                        customer = await session.get(Customer, sub.customer_id)
                        if not customer:
                            continue
                        try:
                            traffic = await xui.get_client_traffic(customer.email)
                        except Exception:
                            continue

                        if traffic is None:
                            continue

                        used_gb = Decimal(str(round(traffic.used_gb, 4)))
                        customer.used_gb = used_gb
                        total_updated += 1

                        if used_gb >= customer.volume_gb:
                            customer.status = CustomerStatus.TRAFFIC_EXHAUSTED
                        elif customer.status == CustomerStatus.TRAFFIC_EXHAUSTED:
                            customer.status = CustomerStatus.ACTIVE

            except Exception as exc:
                logger.warning(
                    "server_traffic_sync_failed",
                    extra={"server_id": server.id, "error": str(exc)},
                )

        await session.commit()
        logger.info(
            "traffic_sync_complete",
            extra={"servers": len(servers), "customers_updated": total_updated},
        )
