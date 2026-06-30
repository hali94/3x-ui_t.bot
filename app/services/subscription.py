"""
Core business service: create, renew, and manage VPN subscriptions.

This is the primary orchestration layer between the Telegram bot / API and
3x-ui. All credit checks, UUID generation, and audit logging happen here.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.xui.client import XUIClientFactory
from app.integrations.xui.models import XUIClientSettings
from app.models.customer import Customer, CustomerStatus
from app.models.sale import Sale
from app.models.server import Server
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.audit import AuditLogRepository
from app.repositories.customer import CustomerRepository
from app.repositories.reseller import ResellerRepository
from app.repositories.subscription import SaleRepository, SubscriptionRepository
from app.repositories.user import UserRepository
from app.utils.generators import (
    expiry_timestamp_ms,
    gb_to_bytes,
    generate_email,
    generate_uuid,
)

logger = logging.getLogger(__name__)


class SubscriptionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.reseller_repo = ResellerRepository(session)
        self.customer_repo = CustomerRepository(session)
        self.sub_repo = SubscriptionRepository(session)
        self.sale_repo = SaleRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.user_repo = UserRepository(session)

    async def create_subscription(
        self,
        reseller_user_id: int,
        customer_name: str,
        volume_gb: float,
        duration_days: int,
        server: Server,
        customer_telegram_id: int | None = None,
    ) -> tuple[Customer, Subscription, str]:
        """
        Full flow:
        1. Load reseller and check credit
        2. Generate UUID / email
        3. Push client to 3x-ui
        4. Persist Customer + Subscription + Sale
        5. Deduct reseller credit
        6. Return (customer, subscription, link)
        """
        reseller = await self.reseller_repo.get_by_user_id(reseller_user_id)
        if not reseller:
            raise ValueError("نماینده یافت نشد")
        if not reseller.active:
            raise ValueError("حساب نماینده غیرفعال است")

        gb = Decimal(str(volume_gb))
        if not reseller.can_sell(gb):
            raise ValueError(
                f"موجودی کافی نیست\n"
                f"اعتبار باقی‌مانده: {reseller.remaining_credit_gb:.2f} گیگ"
            )

        client_uuid = generate_uuid()
        email = generate_email(reseller.id)
        expire_dt = datetime.now(timezone.utc) + timedelta(days=duration_days)
        expire_ms = expiry_timestamp_ms(duration_days)

        xui_settings = XUIClientSettings(
            id=client_uuid,
            email=email,
            total_gb=gb_to_bytes(volume_gb),
            expire_time=expire_ms,
            enable=True,
        )

        async with XUIClientFactory.create(
            server.xui_url, server.xui_username, server.xui_password
        ) as xui:
            await xui.add_client(server.default_inbound_id, xui_settings)

        # Build the VLESS link (simplified — real link requires inbound stream settings)
        inbound = None
        async with XUIClientFactory.create(
            server.xui_url, server.xui_username, server.xui_password
        ) as xui:
            try:
                inbound = await xui.get_inbound(server.default_inbound_id)
            except Exception:
                pass

        link = self._build_link(client_uuid, email, server, inbound)

        # Persist
        customer = Customer(
            telegram_id=customer_telegram_id,
            reseller_id=reseller.id,
            name=customer_name,
            email=email,
            uuid=client_uuid,
            protocol="vless",
            volume_gb=gb,
            expire_date=expire_dt,
            status=CustomerStatus.ACTIVE,
        )
        customer = await self.customer_repo.create(customer)

        price = gb * reseller.price_per_gb
        sub = Subscription(
            customer_id=customer.id,
            reseller_id=reseller.id,
            server_id=server.id,
            volume_gb=gb,
            price=price,
            expire_date=expire_dt,
            xui_client_id=client_uuid,
            inbound_id=server.default_inbound_id,
            status=SubscriptionStatus.ACTIVE,
            link=link,
        )
        sub = await self.sub_repo.create(sub)

        sale = Sale(
            reseller_id=reseller.id,
            customer_id=customer.id,
            subscription_id=sub.id,
            gb=gb,
            amount=price,
        )
        await self.sale_repo.create(sale)

        # Deduct credit — does the final atomic check
        await self.reseller_repo.deduct_credit(reseller.id, gb)

        reseller_user = await self.user_repo.get_with_reseller(reseller_user_id)
        await self.audit_repo.log(
            action="RESELLER_CREATED_CLIENT",
            user_id=reseller_user.id if reseller_user else None,
            data={
                "reseller_id": reseller.id,
                "customer_email": email,
                "volume_gb": float(gb),
                "duration_days": duration_days,
                "server_id": server.id,
            },
        )

        logger.info(
            "subscription_created",
            extra={
                "reseller_id": reseller.id,
                "client_email": email,
                "volume_gb": float(gb),
                "duration_days": duration_days,
            },
        )

        return customer, sub, link

    async def renew_subscription(
        self,
        reseller_user_id: int,
        customer_id: int,
        volume_gb: float,
        duration_days: int,
        server: Server,
    ) -> tuple[Customer, Subscription]:
        reseller = await self.reseller_repo.get_by_user_id(reseller_user_id)
        if not reseller:
            raise ValueError("نماینده یافت نشد")

        customer = await self.customer_repo.get(customer_id)
        if not customer or customer.reseller_id != reseller.id:
            raise ValueError("مشتری یافت نشد")

        gb = Decimal(str(volume_gb))
        if not reseller.can_sell(gb):
            raise ValueError(
                f"موجودی کافی نیست\n"
                f"اعتبار باقی‌مانده: {reseller.remaining_credit_gb:.2f} گیگ"
            )

        expire_dt = datetime.now(timezone.utc) + timedelta(days=duration_days)
        expire_ms = expiry_timestamp_ms(duration_days)

        xui_settings = XUIClientSettings(
            id=customer.uuid,
            email=customer.email,
            total_gb=gb_to_bytes(volume_gb),
            expire_time=expire_ms,
            enable=True,
        )

        async with XUIClientFactory.create(
            server.xui_url, server.xui_username, server.xui_password
        ) as xui:
            await xui.update_client(customer.uuid, server.default_inbound_id, xui_settings)
            await xui.reset_client_traffic(server.default_inbound_id, customer.email)

        customer.volume_gb = gb
        customer.used_gb = Decimal("0")
        customer.expire_date = expire_dt
        customer.status = CustomerStatus.ACTIVE
        await self.session.flush()

        old_sub = await self.sub_repo.get_active_by_customer(customer.id)
        if old_sub:
            old_sub.status = SubscriptionStatus.RENEWED
            await self.session.flush()

        price = gb * reseller.price_per_gb
        sub = Subscription(
            customer_id=customer.id,
            reseller_id=reseller.id,
            server_id=server.id,
            volume_gb=gb,
            price=price,
            expire_date=expire_dt,
            xui_client_id=customer.uuid,
            inbound_id=server.default_inbound_id,
            status=SubscriptionStatus.ACTIVE,
        )
        sub = await self.sub_repo.create(sub)

        sale = Sale(
            reseller_id=reseller.id,
            customer_id=customer.id,
            subscription_id=sub.id,
            gb=gb,
            amount=price,
        )
        await self.sale_repo.create(sale)
        await self.reseller_repo.deduct_credit(reseller.id, gb)

        await self.audit_repo.log(
            action="RESELLER_RENEWED_CLIENT",
            data={"reseller_id": reseller.id, "customer_id": customer.id, "volume_gb": float(gb)},
        )

        return customer, sub

    @staticmethod
    def _build_link(uuid: str, email: str, server: Server, inbound) -> str:
        if inbound is None:
            return f"vless://{uuid}@{server.xui_url.replace('http://', '').replace('https://', '').split(':')[0]}:443?type=tcp&security=tls#{email}"
        host = server.xui_url.replace("http://", "").replace("https://", "").split(":")[0]
        return f"vless://{uuid}@{host}:{inbound.port}?type=tcp&security=none#{email}"
