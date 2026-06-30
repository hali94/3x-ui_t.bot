"""Initial schema — creates all tables and enum types from scratch.

Revision ID: 000_initial_schema
Revises:
Create Date: 2026-06-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "000_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

# ── Reusable enum type references (create_type=False so SQLAlchemy never
#    auto-issues CREATE TYPE — we do it explicitly with checkfirst=True) ──────

userrole = postgresql.ENUM(
    "ADMIN", "RESELLER", "RESELLER_L1", "RESELLER_L2", "CUSTOMER",
    name="userrole", create_type=False,
)
userstatus = postgresql.ENUM(
    "ACTIVE", "INACTIVE", "BANNED",
    name="userstatus", create_type=False,
)
resellerlevel = postgresql.ENUM(
    "LEVEL_1", "LEVEL_2",
    name="resellerlevel", create_type=False,
)
resellerstatus = postgresql.ENUM(
    "ACTIVE", "INACTIVE", "SUSPENDED",
    name="resellerstatus", create_type=False,
)
customerstatus = postgresql.ENUM(
    "ACTIVE", "EXPIRED", "DISABLED", "TRAFFIC_EXHAUSTED",
    name="customerstatus", create_type=False,
)
subscriptionstatus = postgresql.ENUM(
    "ACTIVE", "EXPIRED", "CANCELLED", "RENEWED",
    name="subscriptionstatus", create_type=False,
)
notificationtype = postgresql.ENUM(
    "EXPIRY_WARNING", "TRAFFIC_80", "TRAFFIC_90", "TRAFFIC_100",
    "SUBSCRIPTION_CREATED", "SUBSCRIPTION_RENEWED", "CREDIT_ADDED",
    "L2_RESELLER_CREATED", "L2_SALE", "L2_CREDIT_LOW", "SYSTEM",
    name="notificationtype", create_type=False,
)
notificationstatus = postgresql.ENUM(
    "PENDING", "SENT", "FAILED",
    name="notificationstatus", create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    # Create all enum types first (checkfirst=True = safe to re-run)
    userrole.create(bind, checkfirst=True)
    userstatus.create(bind, checkfirst=True)
    resellerlevel.create(bind, checkfirst=True)
    resellerstatus.create(bind, checkfirst=True)
    customerstatus.create(bind, checkfirst=True)
    subscriptionstatus.create(bind, checkfirst=True)
    notificationtype.create(bind, checkfirst=True)
    notificationstatus.create(bind, checkfirst=True)

    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("full_name", sa.String(512), nullable=False),
        sa.Column("role", userrole, nullable=False, server_default="CUSTOMER"),
        sa.Column("status", userstatus, nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    # ── servers ──────────────────────────────────────────────────────────────
    op.create_table(
        "servers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("xui_url", sa.String(512), nullable=False),
        sa.Column("xui_username", sa.String(255), nullable=False),
        sa.Column("xui_password_encrypted", sa.Text, nullable=False),
        sa.Column("default_inbound_id", sa.Integer, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── resellers ────────────────────────────────────────────────────────────
    op.create_table(
        "resellers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "parent_reseller_id",
            sa.Integer,
            sa.ForeignKey("resellers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("level", resellerlevel, nullable=False, server_default="LEVEL_1"),
        sa.Column("credit_gb", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("used_gb", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("allocated_to_children_gb", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("buy_price_per_gb", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("sell_price_per_gb", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("max_child_resellers", sa.Integer, nullable=False, server_default="10"),
        sa.Column("commission_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("status", resellerstatus, nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_resellers_user_id", "resellers", ["user_id"])
    op.create_index("ix_resellers_parent_reseller_id", "resellers", ["parent_reseller_id"])

    # ── customers ────────────────────────────────────────────────────────────
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger, nullable=True),
        sa.Column(
            "reseller_id",
            sa.Integer,
            sa.ForeignKey("resellers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("email", sa.String(512), nullable=False, unique=True),
        sa.Column("uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("protocol", sa.String(50), nullable=False, server_default="vless"),
        sa.Column("volume_gb", sa.Numeric(12, 3), nullable=False),
        sa.Column("used_gb", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("expire_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", customerstatus, nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_customers_telegram_id", "customers", ["telegram_id"])
    op.create_index("ix_customers_reseller_id", "customers", ["reseller_id"])
    op.create_index("ix_customers_email", "customers", ["email"])
    op.create_index("ix_customers_uuid", "customers", ["uuid"])

    # ── subscriptions ────────────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "customer_id",
            sa.Integer,
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reseller_id",
            sa.Integer,
            sa.ForeignKey("resellers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "server_id",
            sa.Integer,
            sa.ForeignKey("servers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("volume_gb", sa.Numeric(12, 3), nullable=False),
        sa.Column("price", sa.Numeric(14, 2), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expire_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("xui_client_id", sa.String(36), nullable=False),
        sa.Column("inbound_id", sa.Integer, nullable=False),
        sa.Column("status", subscriptionstatus, nullable=False, server_default="ACTIVE"),
        sa.Column("link", sa.String(2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_subscriptions_customer_id", "subscriptions", ["customer_id"])
    op.create_index("ix_subscriptions_reseller_id", "subscriptions", ["reseller_id"])
    op.create_index("ix_subscriptions_server_id", "subscriptions", ["server_id"])
    op.create_index("ix_subscriptions_xui_client_id", "subscriptions", ["xui_client_id"])

    # ── sales ────────────────────────────────────────────────────────────────
    op.create_table(
        "sales",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "reseller_id",
            sa.Integer,
            sa.ForeignKey("resellers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Integer,
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "subscription_id",
            sa.Integer,
            sa.ForeignKey("subscriptions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("gb", sa.Numeric(14, 3), nullable=False),
        sa.Column("buy_price_per_gb", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("sell_price_per_gb", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("profit", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sales_reseller_id", "sales", ["reseller_id"])
    op.create_index("ix_sales_customer_id", "sales", ["customer_id"])
    op.create_index("ix_sales_subscription_id", "sales", ["subscription_id"])

    # ── notifications ────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", notificationtype, nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("status", notificationstatus, nullable=False, server_default="PENDING"),
        sa.Column("reference_id", sa.Integer, nullable=True),
        sa.Column("reference_type", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_reference_id", "notifications", ["reference_id"])

    # ── audit_logs ───────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("data", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("notifications")
    op.drop_table("sales")
    op.drop_table("subscriptions")
    op.drop_table("customers")
    op.drop_table("resellers")
    op.drop_table("servers")
    op.drop_table("users")

    bind = op.get_bind()
    notificationstatus.drop(bind, checkfirst=True)
    notificationtype.drop(bind, checkfirst=True)
    subscriptionstatus.drop(bind, checkfirst=True)
    customerstatus.drop(bind, checkfirst=True)
    resellerstatus.drop(bind, checkfirst=True)
    resellerlevel.drop(bind, checkfirst=True)
    userstatus.drop(bind, checkfirst=True)
    userrole.drop(bind, checkfirst=True)
