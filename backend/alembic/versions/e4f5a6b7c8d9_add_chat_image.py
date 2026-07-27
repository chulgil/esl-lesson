"""채팅 이미지 전송 — chat_messages.image_path (docs/specs/chat.md).

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-07-27
"""

import sqlalchemy as sa

from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("image_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "image_path")
