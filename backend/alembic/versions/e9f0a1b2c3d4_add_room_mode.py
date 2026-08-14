"""일반 대화 방 — conversations.mode (learn|plain) + 유니크에 mode 포함
(docs/specs/chat-language-rooms.md §일반 대화 방)

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-08-14
"""

import sqlalchemy as sa

from alembic import op

revision = "e9f0a1b2c3d4"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("mode", sa.String(length=8), nullable=False, server_default="learn"),
    )
    op.drop_constraint("uq_conversations_pair_langs", "conversations", type_="unique")
    op.create_unique_constraint(
        "uq_conversations_pair_langs_mode",
        "conversations",
        ["user_lo_id", "user_hi_id", "source_lang", "target_lang", "mode"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_conversations_pair_langs_mode", "conversations", type_="unique")
    op.create_unique_constraint(
        "uq_conversations_pair_langs",
        "conversations",
        ["user_lo_id", "user_hi_id", "source_lang", "target_lang"],
    )
    op.drop_column("conversations", "mode")
