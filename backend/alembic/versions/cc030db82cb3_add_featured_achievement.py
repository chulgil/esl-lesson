"""대표 업적 — 프로필 칭호 (docs/specs/mascot-shop.md 플레이어 배지)

Revision ID: cc030db82cb3
Revises: 3d4c34e2c8d9
Create Date: 2026-08-11
"""

from alembic import op

revision = "cc030db82cb3"
down_revision = "3d4c34e2c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_settings ADD COLUMN featured_achievement TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE user_settings DROP COLUMN featured_achievement")
