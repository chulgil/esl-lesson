"""콘텐츠 source 에 'chat' 추가 — 내가 쓰는 말 덱 (docs/specs/my-phrases.md)

Revision ID: 14825ff4087c
Revises: f46e43b17612
Create Date: 2026-08-12
"""

from alembic import op

revision = "14825ff4087c"
down_revision = "f46e43b17612"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_contents_source", "contents", type_="check")
    op.create_check_constraint(
        "ck_contents_source", "contents", "source IN ('youtube','manual','chat')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_contents_source", "contents", type_="check")
    op.create_check_constraint("ck_contents_source", "contents", "source IN ('youtube','manual')")
