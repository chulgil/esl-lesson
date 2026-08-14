"""언어 학습 대화방 — conversations 언어쌍·origin·status + item_occurrences.freq
(docs/specs/chat-language-rooms.md · my-phrases.md 활성 100개 순환 보충)

Revision ID: d8e9f0a1b2c3
Revises: c6d7e8f9a0b1
Create Date: 2026-08-14
"""

import sqlalchemy as sa

from alembic import op

revision = "d8e9f0a1b2c3"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기존 방은 ko→en 백필 (설정 단계를 안 거친 방의 디폴트 — 스펙 결정 #8)
    op.add_column(
        "conversations",
        sa.Column("source_lang", sa.String(length=5), nullable=False, server_default="ko"),
    )
    op.add_column(
        "conversations",
        sa.Column("target_lang", sa.String(length=5), nullable=False, server_default="en"),
    )
    op.add_column(
        "conversations",
        sa.Column("origin", sa.String(length=8), nullable=False, server_default="friend"),
    )
    op.add_column(
        "conversations",
        sa.Column("status", sa.String(length=8), nullable=False, server_default="active"),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "closed_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("conversations", sa.Column("closed_at", sa.DateTime(), nullable=True))
    op.drop_constraint("uq_conversations_pair", "conversations", type_="unique")
    op.create_unique_constraint(
        "uq_conversations_pair_langs",
        "conversations",
        ["user_lo_id", "user_hi_id", "source_lang", "target_lang"],
    )
    op.create_check_constraint(
        "ck_conversations_lang_pair", "conversations", "source_lang <> target_lang"
    )

    op.add_column("item_occurrences", sa.Column("freq", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("item_occurrences", "freq")
    op.drop_constraint("ck_conversations_lang_pair", "conversations", type_="check")
    op.drop_constraint("uq_conversations_pair_langs", "conversations", type_="unique")
    op.create_unique_constraint(
        "uq_conversations_pair", "conversations", ["user_lo_id", "user_hi_id"]
    )
    op.drop_column("conversations", "closed_at")
    op.drop_column("conversations", "closed_by")
    op.drop_column("conversations", "status")
    op.drop_column("conversations", "origin")
    op.drop_column("conversations", "target_lang")
    op.drop_column("conversations", "source_lang")
