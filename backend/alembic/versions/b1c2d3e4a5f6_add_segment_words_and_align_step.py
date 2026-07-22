"""단어 정렬 — transcript_segments.words + extraction_jobs align 단계.

Revision ID: b1c2d3e4a5f6
Revises: a9b0c1d2e3f4
Create Date: 2026-07-22
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "b1c2d3e4a5f6"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None

_STEPS_OLD = "step IN ('metadata','transcript','translate','extract','embed')"
_STEPS_NEW = "step IN ('metadata','transcript','translate','extract','embed','align')"


def upgrade() -> None:
    op.add_column(
        "transcript_segments",
        sa.Column("words", postgresql.JSONB(), nullable=True),
    )
    op.drop_constraint("ck_jobs_step", "extraction_jobs", type_="check")
    op.create_check_constraint("ck_jobs_step", "extraction_jobs", _STEPS_NEW)


def downgrade() -> None:
    op.drop_constraint("ck_jobs_step", "extraction_jobs", type_="check")
    op.create_check_constraint("ck_jobs_step", "extraction_jobs", _STEPS_OLD)
    op.drop_column("transcript_segments", "words")
