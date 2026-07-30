"""테마 접근 정책 오버라이드 — 백오피스 무료/제한 전환 (docs/specs/theme-mall.md).

행 없음 = 코드 카탈로그(THEME_ACCESS) 기본값. 시드 없음.
"""

import sqlalchemy as sa

from alembic import op

revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "theme_settings",
        sa.Column("theme_key", sa.String(length=32), primary_key=True),
        sa.Column("access", sa.String(length=16), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("theme_settings")
