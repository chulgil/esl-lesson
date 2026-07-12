"""user_settings.study_level 추가 (학습 난이도 1-4). 기존 사용자는 고급(4) 유지.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-12
"""

import sqlalchemy as sa

from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 신규 기본은 초급(2)이나, 기존 사용자는 이미 전체 학습 중이므로 고급(4)로 백필
    op.add_column(
        "user_settings",
        sa.Column("study_level", sa.Integer(), nullable=False, server_default="4"),
    )
    # 신규 가입자부터 초급(2) 기본
    op.alter_column("user_settings", "study_level", server_default="2")


def downgrade() -> None:
    op.drop_column("user_settings", "study_level")
