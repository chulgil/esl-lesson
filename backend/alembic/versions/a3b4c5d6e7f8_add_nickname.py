"""닉네임 — 랜덤 초기값 백필, 구글 이름 비노출 (docs/specs/auth.md)

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-07-15
"""

import sqlalchemy as sa

from alembic import op
from app.services.nicknames import random_nickname

revision = "a3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN nickname TEXT NOT NULL DEFAULT ''")
    # 백필: 기존 사용자 전원 랜덤 닉네임 — 구글 이름을 옮겨 담지 않는다 (개인정보 비노출)
    conn = op.get_bind()
    ids = [row[0] for row in conn.execute(sa.text("SELECT id FROM users WHERE nickname = ''"))]
    for user_id in ids:
        conn.execute(
            sa.text("UPDATE users SET nickname = :nickname WHERE id = :id"),
            {"nickname": random_nickname(), "id": user_id},
        )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN nickname")
