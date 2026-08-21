"""캐릭터 말풍선 변경권 — 커스텀 문구 + 소모성 1회권 (2026-08-21 요청)

docs/specs/mascot-shop.md §말풍선 변경권. 가격은 perk:message 정책
(item_settings 오버라이드 — 백오피스 상점 관리에서 설정).

Revision ID: l6a7b8c9d0e1
Revises: k5f6a7b8c9d0
Create Date: 2026-08-21
"""

import sqlalchemy as sa

from alembic import op

revision = "l6a7b8c9d0e1"
down_revision = "k5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("mascot_message", sa.Text(), nullable=True))
    op.add_column(
        "user_settings",
        sa.Column("mascot_message_tickets", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "mascot_message_tickets")
    op.drop_column("user_settings", "mascot_message")
