"""친구 1:1 채팅 — conversations / chat_messages / chat_reads (docs/specs/chat.md).

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-07-27
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_lo_id", sa.BigInteger(), nullable=False),
        sa.Column("user_hi_id", sa.BigInteger(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_lo_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_hi_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_lo_id", "user_hi_id", name="uq_conversations_pair"),
        sa.CheckConstraint("user_lo_id < user_hi_id", name="ck_conversations_ordered"),
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_id", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("item_ref", postgresql.JSONB(), nullable=True),
        sa.Column("client_msg_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "client_msg_id", name="uq_chat_messages_client"),
    )
    op.create_index("ix_chat_messages_conv_id_desc", "chat_messages", ["conversation_id", "id"])
    op.create_table(
        "chat_reads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("last_read_message_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_chat_reads_user"),
    )


def downgrade() -> None:
    op.drop_table("chat_reads")
    op.drop_index("ix_chat_messages_conv_id_desc", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_table("conversations")
