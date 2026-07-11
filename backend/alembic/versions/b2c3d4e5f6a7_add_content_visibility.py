"""contents.visibility 추가 (public/private) — 기존 행은 public

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-11
"""

import sqlalchemy as sa

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contents",
        sa.Column("visibility", sa.Text(), nullable=False, server_default="public"),
    )
    op.create_check_constraint(
        "ck_contents_visibility", "contents", "visibility IN ('public','private')"
    )
    op.create_index("idx_contents_visibility_owner", "contents", ["visibility", "created_by"])


def downgrade() -> None:
    op.drop_index("idx_contents_visibility_owner", table_name="contents")
    op.drop_constraint("ck_contents_visibility", "contents")
    op.drop_column("contents", "visibility")
