"""리텐션 팩 — 책갈피(스트릭 보호) + 오늘의 미션 원장 (docs/proposal/retention-plan.md).

Revision ID: a9b0c1d2e3f4
Revises: e7f8a9b0c1d2
Create Date: 2026-07-16
"""

import sqlalchemy as sa

from alembic import op

revision = "a9b0c1d2e3f4"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("streak_savers", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("user_settings", sa.Column("saver_award_week", sa.Text(), nullable=True))

    op.create_table(
        "streak_saver_uses",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "day", name="uq_saver_user_day"),
    )
    op.create_index("ix_streak_saver_uses_user_id", "streak_saver_uses", ["user_id"])

    op.create_table(
        "quest_completions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("quest_key", sa.Text(), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "day", "quest_key", name="uq_quest_user_day_key"),
    )
    op.create_index("ix_quest_completions_user_id", "quest_completions", ["user_id"])


def downgrade() -> None:
    op.drop_table("quest_completions")
    op.drop_table("streak_saver_uses")
    op.drop_column("user_settings", "saver_award_week")
    op.drop_column("user_settings", "streak_savers")
