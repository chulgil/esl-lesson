"""대화방 공지 제목 — shared_goals.title (docs/specs/chat-notice.md 제목+내용 구조)

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-08-13
"""

import sqlalchemy as sa

from alembic import op

revision = "c6d7e8f9a0b1"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shared_goals", sa.Column("title", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("shared_goals", "title")
