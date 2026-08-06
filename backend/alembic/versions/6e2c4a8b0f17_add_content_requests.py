"""콘텐츠 요청 — 공급을 수요와 연결 (effectiveness-audit-2026-08.md P0-3).

Revision ID: 6e2c4a8b0f17
Revises: 7d1f9b3c5e42
Create Date: 2026-08-06
"""

import sqlalchemy as sa

from alembic import op

revision = "6e2c4a8b0f17"
down_revision = "7d1f9b3c5e42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_requests",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("content_requests")
