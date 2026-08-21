"""한글 독음 캐시 — 학습 방 번역문의 발음을 한글로 (chat-translation.md §한글 독음)

Revision ID: h2c3d4e5f6a7
Revises: g1b2c3d4e5f6
Create Date: 2026-08-21
"""

import sqlalchemy as sa

from alembic import op

revision = "h2c3d4e5f6a7"
down_revision = "g1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hangul_readings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("text_key", sa.String(200), nullable=False),
        sa.Column("lang", sa.String(8), nullable=False),
        sa.Column("reading", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("text_key", "lang", name="uq_hangul_readings_key_lang"),
    )


def downgrade() -> None:
    op.drop_table("hangul_readings")
