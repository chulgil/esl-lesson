"""내가 쓰는 말 제외 원장 — 뺀 문장은 재수집되지 않는다 (my-phrases.md 편집)

Revision ID: 92b27ad838a9
Revises: 14825ff4087c
Create Date: 2026-08-12
"""

import sqlalchemy as sa

from alembic import op

revision = "92b27ad838a9"
down_revision = "14825ff4087c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "phrase_exclusions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "text_key", name="uq_phrase_exclusions_user_key"),
    )
    op.create_index("ix_phrase_exclusions_user_id", "phrase_exclusions", ["user_id"])
    # 번역 캐시 무효화 — 같은 배포에서 엔진이 Haiku 우선으로 바뀐다.
    # DeepL 시절 오염분(의미 반전 오역·의성어 음차·깨진 이모지, 2026-08-12
    # 실측 196건)이 캐시로 계속 서빙되지 않게 비운다 (재번역 비용은 수백 원 미만)
    op.execute("DELETE FROM chat_translations")


def downgrade() -> None:
    op.drop_index("ix_phrase_exclusions_user_id", table_name="phrase_exclusions")
    op.drop_table("phrase_exclusions")
