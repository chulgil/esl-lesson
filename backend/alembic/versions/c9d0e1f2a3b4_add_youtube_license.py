"""공용 승격 CC 라이선스 게이트 — contents.youtube_license (저작권 검토 2026-07-14)

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-14
"""

from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE contents ADD COLUMN youtube_license TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE contents DROP COLUMN youtube_license")
