"""재청취 이해도 셀프 체크 — 전후 1~5점 (effectiveness-audit-2026-08.md P1).

Revision ID: 7d1f9b3c5e42
Revises: 4c8e2a6f0d13
Create Date: 2026-08-05
"""

import sqlalchemy as sa

from alembic import op

revision = "7d1f9b3c5e42"
down_revision = "4c8e2a6f0d13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "listen_checks",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "content_id",
            sa.BigInteger(),
            sa.ForeignKey("contents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.SmallInteger(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "content_id", "stage", name="uq_listen_user_content_stage"),
    )


def downgrade() -> None:
    op.drop_table("listen_checks")
