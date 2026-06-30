"""Add reseller hierarchy fields to an existing pre-hierarchy schema.

This migration is a NO-OP for databases created fresh from 000_initial_schema
(all columns already exist). It only matters when upgrading an older deployment
that was created before the hierarchy feature was added.

Revision ID: 001_reseller_hierarchy
Revises: 000_initial_schema
Create Date: 2026-06-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_reseller_hierarchy"
down_revision = "000_initial_schema"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    # ── Guard: skip everything if parent_reseller_id already exists ──────────
    # This is the case for fresh installs created by 000_initial_schema.
    if _column_exists("resellers", "parent_reseller_id"):
        return

    # ── From here on we are upgrading an old schema ──────────────────────────

    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'RESELLER_L1'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'RESELLER_L2'")

    reseller_level_enum = postgresql.ENUM("LEVEL_1", "LEVEL_2", name="resellerlevel")
    reseller_level_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "resellers",
        sa.Column(
            "parent_reseller_id",
            sa.Integer,
            sa.ForeignKey("resellers.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_resellers_parent_reseller_id", "resellers", ["parent_reseller_id"])

    op.add_column(
        "resellers",
        sa.Column(
            "level",
            sa.Enum("LEVEL_1", "LEVEL_2", name="resellerlevel"),
            nullable=False,
            server_default="LEVEL_1",
        ),
    )
    op.add_column(
        "resellers",
        sa.Column("allocated_to_children_gb", sa.Numeric(14, 3), nullable=False, server_default="0"),
    )
    op.add_column(
        "resellers",
        sa.Column("buy_price_per_gb", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "resellers",
        sa.Column("sell_price_per_gb", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "resellers",
        sa.Column("max_child_resellers", sa.Integer, nullable=False, server_default="10"),
    )

    # Migrate existing price_per_gb → sell_price_per_gb if old column exists
    bind = op.get_bind()
    if _column_exists("resellers", "price_per_gb"):
        bind.execute(sa.text("UPDATE resellers SET sell_price_per_gb = price_per_gb"))

    reseller_status_enum = postgresql.ENUM("ACTIVE", "INACTIVE", "SUSPENDED", name="resellerstatus")
    reseller_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "resellers",
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "INACTIVE", "SUSPENDED", name="resellerstatus"),
            nullable=False,
            server_default="ACTIVE",
        ),
    )
    if _column_exists("resellers", "active"):
        bind.execute(
            sa.text(
                "UPDATE resellers SET status = CASE WHEN active = true THEN 'ACTIVE'::resellerstatus ELSE 'INACTIVE'::resellerstatus END"
            )
        )

    # sales: buy/sell price and profit
    if not _column_exists("sales", "buy_price_per_gb"):
        op.add_column("sales", sa.Column("buy_price_per_gb", sa.Numeric(14, 2), nullable=False, server_default="0"))
        op.add_column("sales", sa.Column("sell_price_per_gb", sa.Numeric(14, 2), nullable=False, server_default="0"))
        op.add_column("sales", sa.Column("profit", sa.Numeric(16, 2), nullable=False, server_default="0"))

    # notifications: deduplication columns
    if not _column_exists("notifications", "reference_id"):
        op.add_column("notifications", sa.Column("reference_id", sa.Integer, nullable=True))
        op.create_index("ix_notifications_reference_id", "notifications", ["reference_id"])
        op.add_column("notifications", sa.Column("reference_type", sa.String(64), nullable=True))

    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'L2_RESELLER_CREATED'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'L2_SALE'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'L2_CREDIT_LOW'")


def downgrade() -> None:
    # Only meaningful when this migration actually ran (not for fresh installs)
    pass
