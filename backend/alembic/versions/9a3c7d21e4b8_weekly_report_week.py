"""주간 성적표 월요일 푸시 dedup — user_settings.weekly_report_week.

Revision ID: 9a3c7d21e4b8
Revises: 6e2c4a8b0f17
Create Date: 2026-08-06
"""

import sqlalchemy as sa

from alembic import op

revision = "9a3c7d21e4b8"
down_revision = "6e2c4a8b0f17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("weekly_report_week", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_settings", "weekly_report_week")
