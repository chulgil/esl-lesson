"""오늘의 목표(daily_goal) — 밀린 양과 무관한 달성 가능 소량 (포기 방지 기획)

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-07-15
"""

from alembic import op

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_settings ADD COLUMN daily_goal INT NOT NULL DEFAULT 20")


def downgrade() -> None:
    op.execute("ALTER TABLE user_settings DROP COLUMN daily_goal")
