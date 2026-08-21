"""악세사리 착용 목록 + 일본어 독음 캐시 퍼지 (2026-08-21)

1. user_settings.mascot_outfits — 착용 중인 악세사리 키 목록.
   NULL = 전부 착용(구 all-on 정책과 동일, 기존 사용자 동작 보존).
   docs/specs/mascot-shop.md §착용 토글.
2. hangul_readings ja 행 퍼지 — 장음 오표기(소우데스네) 제보로 독음 프롬프트를
   교정, 기존 캐시는 재생성 (chat-translation.md §한글 독음).

Revision ID: k5f6a7b8c9d0
Revises: j4e5f6a7b8c9
Create Date: 2026-08-21
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "k5f6a7b8c9d0"
down_revision = "j4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("mascot_outfits", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.execute("DELETE FROM hangul_readings WHERE lang = 'ja'")


def downgrade() -> None:
    op.drop_column("user_settings", "mascot_outfits")
