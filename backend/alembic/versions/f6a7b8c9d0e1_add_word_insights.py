"""word_insights 추가 — 단어 인사이트 캐시 (docs/proposal/word-insight.md P1).

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-13
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "word_insights",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "item_id",
            sa.BigInteger(),
            sa.ForeignKey("learning_items.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("word_insights")
