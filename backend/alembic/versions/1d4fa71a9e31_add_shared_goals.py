"""함께 목표 — 대화방 공유 체크리스트·주간 달성표 (docs/specs/shared-goals.md)

Revision ID: 1d4fa71a9e31
Revises: ad5b7ffdd7fb
Create Date: 2026-08-12
"""

import sqlalchemy as sa

from alembic import op

revision = "1d4fa71a9e31"
down_revision = "ad5b7ffdd7fb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shared_goals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            sa.BigInteger(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="check"),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_value", sa.Integer(), nullable=True),
        sa.Column("done", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "done_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_shared_goals_conversation_id", "shared_goals", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_shared_goals_conversation_id", table_name="shared_goals")
    op.drop_table("shared_goals")
