"""user_settings.reminder_hour 추가 — 복습 리마인더 시각 개인화 (실행 의도).

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-08-04
"""

import sqlalchemy as sa

from alembic import op

revision = "c0d1e2f3a4b5"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기존 사용자도 기본 20시 유지 (기존 고정 발송 시각과 동일 — 행동 변화 없음)
    op.add_column(
        "user_settings",
        sa.Column("reminder_hour", sa.Integer(), nullable=False, server_default="20"),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "reminder_hour")
