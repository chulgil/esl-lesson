"""구매 이력 원장 purchases + 아이템 판매 정책 item_settings

Revision ID: 7107c0984dc7
Revises: cc030db82cb3
Create Date: 2026-08-11
"""

import sqlalchemy as sa

from alembic import op

revision = "7107c0984dc7"
down_revision = "cc030db82cb3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchases",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_key", sa.String(length=64), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False, server_default="xp"),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="XP"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_purchases_user_id", "purchases", ["user_id"])
    # 백필 — xp_spends 는 전 행이 상점 구매(theme:/mascot:/outfit:/saver:)라
    # 그대로 XP 결제 이력으로 옮긴다 (시각 보존)
    op.execute(
        "INSERT INTO purchases (user_id, item_key, method, amount, currency, created_at) "
        "SELECT user_id, reason, 'xp', amount, 'XP', created_at FROM xp_spends"
    )
    # 아이템 판매 정책 — 백오피스 가격 오버라이드·이벤트 한정 (행 없음 = 기본)
    op.create_table(
        "item_settings",
        sa.Column("item_key", sa.String(length=64), primary_key=True),
        sa.Column("price_xp", sa.Integer(), nullable=True),
        sa.Column("sale", sa.String(length=16), nullable=False, server_default="xp"),
    )


def downgrade() -> None:
    op.drop_table("item_settings")
    op.drop_index("ix_purchases_user_id", table_name="purchases")
    op.drop_table("purchases")
