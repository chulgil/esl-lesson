"""업적 달성 → 테마 지급 규칙 (docs/specs/theme-mall.md).

초기 규칙 시드: 첫 친구 → candy, 첫 게임 → lego (사용자 지시 2026-07-30).
과거 달성자 백필은 불필요 — 업적이 로그 소급 집계라 다음 테마 조회 때
sync_theme_rewards 가 자동 지급한다.
"""

import sqlalchemy as sa

from alembic import op

revision = "d1e2f3a4b5c6"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = op.create_table(
        "theme_reward_rules",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("achievement_key", sa.String(length=64), nullable=False),
        sa.Column("theme_key", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("achievement_key", "theme_key", name="uq_theme_reward_rules_pair"),
    )
    op.bulk_insert(
        table,
        [
            {"achievement_key": "first_friend", "theme_key": "candy"},
            {"achievement_key": "first_game", "theme_key": "lego"},
        ],
    )


def downgrade() -> None:
    op.drop_table("theme_reward_rules")
