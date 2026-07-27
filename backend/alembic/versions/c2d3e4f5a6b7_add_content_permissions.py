"""콘텐츠 거버넌스 — content_permissions 테이블 + 공용 콘텐츠 구독 백필.

가시성 규칙이 "공용은 전 회원 자동 노출" 에서 "담은(구독) 콘텐츠만 노출" 로
바뀌므로, 백필 없이 배포하면 기존 회원의 학습 큐가 일제히 빈다.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4a5f6
Create Date: 2026-07-27
"""

import sqlalchemy as sa

from alembic import op

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4a5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_permissions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=False),
        sa.Column("rights_holder", sa.Text(), nullable=False),
        sa.Column("rights_holder_contact", sa.Text(), nullable=True),
        sa.Column("granted_at", sa.Date(), nullable=False),
        sa.Column("scope_transcript", sa.Boolean(), nullable=False),
        sa.Column("scope_translate", sa.Boolean(), nullable=False),
        sa.Column("scope_derive", sa.Boolean(), nullable=False),
        sa.Column("scope_commercial", sa.Boolean(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_id", name="uq_content_permissions_content"),
    )

    # 기존 회원 × 기존 공용 콘텐츠 구독 백필 — 이미 있는 구독은 건너뛴다
    op.execute(
        """
        INSERT INTO content_subscriptions (content_id, user_id, created_at)
        SELECT c.id, u.id, now()
        FROM contents c
        CROSS JOIN users u
        WHERE c.visibility = 'public'
          AND NOT EXISTS (
              SELECT 1 FROM content_subscriptions s
              WHERE s.content_id = c.id AND s.user_id = u.id
          )
        """
    )


def downgrade() -> None:
    op.drop_table("content_permissions")
