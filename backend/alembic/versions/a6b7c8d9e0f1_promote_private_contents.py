"""기존 개인 콘텐츠 공용 승격 — 유튜브 등록이 관리자 전용으로 바뀐 데 따른 일괄 전환.

사용자 지시 (2026-07-28): 사용자가 등록해 둔 개인 콘텐츠를 관리자가 올린 것처럼
공용으로 만들고, 담아 둔 사용자의 학습은 그대로 유지한다.

순서가 중요하다: 공용은 승인(approved) 항목만 노출되므로(visibility.py),
비공개 식별이 가능한 동안 pending 항목을 먼저 승인해야 기존 구독자의
학습 재료가 사라지지 않는다 (rejected 는 그대로 — 관리자 거절 존중).
구독 행은 건드리지 않아 "담김" 상태·학습 기록이 전부 보존된다.
CC 게이트(공용 승격 409 cc_required)는 소유자 일괄 지시로 우회 — 라이선스
값 자체는 보존되므로 백오피스에서 사후 식별 가능.

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
"""

from alembic import op

revision = "a6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) 비공개 콘텐츠의 pending 항목 승인 (비공개 식별이 가능한 지금 먼저)
    op.execute(
        """
        UPDATE learning_items SET review_status = 'approved'
        WHERE review_status = 'pending' AND id IN (
            SELECT item_id FROM item_occurrences WHERE content_id IN (
                SELECT id FROM contents WHERE visibility = 'private'
            )
        )
        """
    )
    # 2) 비공개 → 공용 전환 (구독 행은 그대로 = 담김 유지)
    op.execute("UPDATE contents SET visibility = 'public' WHERE visibility = 'private'")


def downgrade() -> None:
    # 어떤 콘텐츠가 비공개였는지 정보가 소실되므로 되돌릴 수 없다 (의도된 단방향)
    pass
