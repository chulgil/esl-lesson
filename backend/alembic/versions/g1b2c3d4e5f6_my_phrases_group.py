"""내가 쓰는 말 덱 그룹화 — contents.chat_kind (docs/specs/my-phrases.md 덱 그룹화)

배포 시점에 이미 존재하는 chat 덱은 전부 개편 전(언어 분리 이전) 수집분이라
chat_kind='legacy'로 전환하고 제목을 "내가 쓰는 말 (일반)"으로 통일한다.
이후 sync_my_phrases 가 새로 만드는 언어별 덱은 chat_kind NULL로 남아
legacy 덱과 별개 행으로 구분된다.

Revision ID: g1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-08-14
"""

import sqlalchemy as sa

from alembic import op

revision = "g1b2c3d4e5f6"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contents", sa.Column("chat_kind", sa.String(length=8), nullable=True))
    op.execute(
        sa.text(
            "UPDATE contents SET chat_kind='legacy', title='내가 쓰는 말 (일반)' "
            "WHERE source='chat'"
        )
    )


def downgrade() -> None:
    op.drop_column("contents", "chat_kind")
