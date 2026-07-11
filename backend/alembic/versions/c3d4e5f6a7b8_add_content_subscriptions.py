"""content_subscriptions 추가 — 동일 영상 다중 사용자 공유 + 기존 private 백필

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-11
"""

import sqlalchemy as sa

from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_subscriptions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "content_id",
            sa.BigInteger(),
            sa.ForeignKey("contents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("content_id", "user_id", name="uq_subscriptions_content_user"),
    )
    op.create_index("idx_subscriptions_user", "content_subscriptions", ["user_id"])
    # 백필: 기존 개인 콘텐츠의 등록자를 구독자로 등록
    op.execute(
        """
        INSERT INTO content_subscriptions (content_id, user_id)
        SELECT id, created_by FROM contents
        WHERE visibility = 'private' AND created_by IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("idx_subscriptions_user", table_name="content_subscriptions")
    op.drop_table("content_subscriptions")
