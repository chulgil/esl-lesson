"""다국어 학습 기반 — 채팅 번역 캐시·사용량, 언어 설정, 콘텐츠 언어

Revision ID: 7e640f90f627
Revises: 7107c0984dc7
Create Date: 2026-08-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "7e640f90f627"
down_revision = "7107c0984dc7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 채팅 번역 글로벌 캐시 — 문장 단위 (전 사용자 공유, 비용 방어 1층)
    op.create_table(
        "chat_translations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("text_key", sa.String(length=200), nullable=False),
        sa.Column("source_lang", sa.String(length=8), nullable=False),
        sa.Column("target_lang", sa.String(length=8), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("engine", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("text_key", "target_lang", name="uq_chat_translations_key_lang"),
    )
    # 번역 사용량 원장 — 월 예산 하드캡·사용자 일일 한도 판정 근거
    op.create_table(
        "translation_usage",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chars", sa.Integer(), nullable=False),
        sa.Column("engine", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_translation_usage_user_id", "translation_usage", ["user_id"])
    op.create_index("ix_translation_usage_created_at", "translation_usage", ["created_at"])
    # 언어 설정 — 주언어(모국어)·학습언어(복수)·채팅 자동번역 토글
    op.add_column(
        "user_settings",
        sa.Column("primary_lang", sa.Text(), nullable=False, server_default="ko"),
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "learning_langs",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY['en']"),
        ),
    )
    op.add_column(
        "user_settings",
        sa.Column("chat_translate", sa.Boolean(), nullable=False, server_default="false"),
    )
    # 콘텐츠 언어 — 기존 콘텐츠는 전부 영어라 en 백필
    op.add_column("contents", sa.Column("lang", sa.Text(), nullable=False, server_default="en"))


def downgrade() -> None:
    op.drop_column("contents", "lang")
    op.drop_column("user_settings", "chat_translate")
    op.drop_column("user_settings", "learning_langs")
    op.drop_column("user_settings", "primary_lang")
    op.drop_index("ix_translation_usage_created_at", table_name="translation_usage")
    op.drop_index("ix_translation_usage_user_id", table_name="translation_usage")
    op.drop_table("translation_usage")
    op.drop_table("chat_translations")
