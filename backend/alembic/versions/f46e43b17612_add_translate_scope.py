"""채팅 번역 범위 — 내 글/상대 글 개별 체크 (2026-08-12 요청)

Revision ID: f46e43b17612
Revises: 7e640f90f627
Create Date: 2026-08-12
"""

import sqlalchemy as sa

from alembic import op

revision = "f46e43b17612"
down_revision = "7e640f90f627"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기본: 내 글만 번역 — "내가 쓴 한글이 학습언어로 어떻게 되는지" 가 1차 목표
    op.add_column(
        "user_settings",
        sa.Column("translate_mine", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "user_settings",
        sa.Column("translate_theirs", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "translate_theirs")
    op.drop_column("user_settings", "translate_mine")
