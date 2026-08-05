"""오늘의 목표 프리셋 상향 — 가볍게 10->15, 기본 20->30 (2026-08-05 사용자 결정).

구 프리셋 값(10/20)을 쓰던 사용자는 새 프리셋으로 승급한다 — 프리셋 자체가
바뀌었으므로 옛 값을 두면 설정 화면에서 어떤 프리셋도 선택되지 않은 상태가 된다.
수동 커스텀 값(그 외)은 건드리지 않는다. 업적 티어(10/20/50)는 별도 유지.

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-08-05
"""

import sqlalchemy as sa

from alembic import op

revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("user_settings", "daily_goal", server_default="30")
    op.execute(sa.text("UPDATE user_settings SET daily_goal = 15 WHERE daily_goal = 10"))
    op.execute(sa.text("UPDATE user_settings SET daily_goal = 30 WHERE daily_goal = 20"))


def downgrade() -> None:
    op.alter_column("user_settings", "daily_goal", server_default="20")
    op.execute(sa.text("UPDATE user_settings SET daily_goal = 10 WHERE daily_goal = 15"))
    op.execute(sa.text("UPDATE user_settings SET daily_goal = 20 WHERE daily_goal = 30"))
