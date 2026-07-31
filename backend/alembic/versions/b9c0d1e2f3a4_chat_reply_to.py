"""chat_messages.reply_to_id — 카톡식 답장 인용 (2026-07-31)

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-07-31
"""

import sqlalchemy as sa

from alembic import op

revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("reply_to_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_chat_messages_reply_to",
        "chat_messages",
        "chat_messages",
        ["reply_to_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_chat_messages_reply_to", "chat_messages", type_="foreignkey")
    op.drop_column("chat_messages", "reply_to_id")
