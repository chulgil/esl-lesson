"""테마 엔타이틀먼트 — theme_grants + 헤냥이(cat) 초기 지급 (docs/specs/theme-mall.md).

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-07-30
"""

import sqlalchemy as sa

from alembic import op

revision = "b7c8d9e0f1a2"
down_revision = "a6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "theme_grants",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("theme_key", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("granted_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        # 지급 관리자 탈퇴 시에도 지급 이력은 남긴다 — 참조만 비움
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "theme_key", name="uq_theme_grants_user_theme"),
    )
    # 초기 지급 (사용자 지시 2026-07-30): 헤냥이(cat)는 두 계정 전용.
    # 유저가 아직 없으면(미로그인) 스킵 — 최초 로그인 후 백오피스에서 수동 지급.
    # NOT EXISTS 가드로 멱등 — 재실행해도 중복 INSERT 없음 (granted_by null = 시드)
    op.execute(
        """
        INSERT INTO theme_grants (user_id, theme_key, note)
        SELECT u.id, 'cat', '초기 지급 (2026-07-30)'
        FROM users u
        WHERE lower(u.email) IN ('hyein.lim213@gmail.com', 'codenavi@gmail.com')
          AND NOT EXISTS (
            SELECT 1 FROM theme_grants tg
            WHERE tg.user_id = u.id AND tg.theme_key = 'cat'
          )
        """
    )


def downgrade() -> None:
    op.drop_table("theme_grants")
