"""대화방 공지 시스템 줄 — chat_messages.kind (docs/specs/chat-notice.md)

Revision ID: b5c6d7e8f9a0
Revises: 1d4fa71a9e31
Create Date: 2026-08-13
"""

import sqlalchemy as sa

from alembic import op

revision = "b5c6d7e8f9a0"
down_revision = "1d4fa71a9e31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("kind", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "kind")
