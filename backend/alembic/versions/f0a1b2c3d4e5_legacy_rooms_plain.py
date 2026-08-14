"""기존 방 = 일반 방 백필 — 2026-08-14 사용자 결정
(docs/specs/chat-language-rooms.md §일반 대화 방)

개편 이전부터 쓰던 대화는 학습 방이 아니라 일반 대화다. "개편 전 방" =
그 쌍의 유일한 방 (개편 전 스키마는 쌍당 1행). 쌍에 방이 2개 이상이면 이미
마법사를 쓴 것이므로 건드리지 않는다 — 이 조건이 유니크
(uq_conversations_pair_langs_mode) 충돌도 구조적으로 차단한다.

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-08-14
"""

import sqlalchemy as sa

from alembic import op

revision = "f0a1b2c3d4e5"
down_revision = "e9f0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE conversations AS c
            SET mode = 'plain', source_lang = 'ko', target_lang = 'en'
            WHERE c.mode = 'learn'
              AND NOT EXISTS (
                SELECT 1 FROM conversations o
                WHERE o.user_lo_id = c.user_lo_id
                  AND o.user_hi_id = c.user_hi_id
                  AND o.id <> c.id
              )
            """
        )
    )


def downgrade() -> None:
    # 데이터 백필 — 원상 구분 정보가 없어 되돌리지 않는다 (no-op)
    pass
