"""review_cards.fsrs_json 추가 (py-fsrs Card 직렬화 원본)

Revision ID: a1b2c3d4e5f6
Revises: e3f3fb706968
Create Date: 2026-07-11
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "e3f3fb706968"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_cards",
        sa.Column("fsrs_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_cards", "fsrs_json")
