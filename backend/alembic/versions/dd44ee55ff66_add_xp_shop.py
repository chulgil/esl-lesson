"""XP 상점 — theme_settings.price_xp + xp_spends 소비 원장 (theme-mall.md XP 상점).

Revision ID: dd44ee55ff66
Revises: aa11bb22cc33
Create Date: 2026-08-05
"""

import sqlalchemy as sa

from alembic import op

revision = "dd44ee55ff66"
down_revision = "aa11bb22cc33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("theme_settings", sa.Column("price_xp", sa.Integer(), nullable=True))
    op.create_table(
        "xp_spends",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("xp_spends")
    op.drop_column("theme_settings", "price_xp")
