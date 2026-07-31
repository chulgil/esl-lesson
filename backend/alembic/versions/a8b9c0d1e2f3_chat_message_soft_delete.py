"""채팅 메시지 soft delete — deleted_at (docs/specs/chat.md).

행·커서는 보존하고 내용만 소거 — 클라는 "삭제되었습니다" 로 표기.
"""

import sqlalchemy as sa

from alembic import op

revision = "a8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "deleted_at")
