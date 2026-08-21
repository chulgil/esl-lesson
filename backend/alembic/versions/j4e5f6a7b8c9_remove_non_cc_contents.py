"""비 CC BY 유튜브 콘텐츠 제거 — 저작권 리스크 정리 (2026-08-21 사용자 지시)

CC BY(creativeCommon)가 아닌 유튜브 콘텐츠를 전부 삭제한다. 저작권 안내
페이지의 "허락 확보" 원칙과 실데이터를 일치시키는 조치 —
docs/proposal/legal-risk-review-2026-08.md.

삭제 시멘틱은 관리자 삭제(content_service.delete_content_row)와 동일:
- occurrence 명시 삭제 후 콘텐츠 삭제 (segments·구독·시험 등은 FK cascade)
- 연습 기록(review_cards)이 있는 학습 항목은 보존 — 가시성 규칙으로 학습
  목록에서만 빠지고 기록·통계·FSRS 진행은 유지, 재등록 시 그대로 이어짐
- 출처도 기록도 없는 고아 항목만 삭제

프로덕션 조사(2026-08-21 읽기 전용): 대상 6개 콘텐츠, 항목 613개,
사용자 3명의 카드 454장(카드는 보존됨). chat/manual 콘텐츠는 대상 아님.

Revision ID: j4e5f6a7b8c9
Revises: i3d4e5f6a7b8
Create Date: 2026-08-21
"""

from alembic import op

revision = "j4e5f6a7b8c9"
down_revision = "i3d4e5f6a7b8"
branch_labels = None
depends_on = None

NON_CC = (
    "SELECT id FROM contents WHERE source = 'youtube' "
    "AND (youtube_license IS NULL OR youtube_license <> 'creativeCommon')"
)


def upgrade() -> None:
    op.execute(f"DELETE FROM item_occurrences WHERE content_id IN ({NON_CC})")
    op.execute(
        "DELETE FROM contents WHERE source = 'youtube' "
        "AND (youtube_license IS NULL OR youtube_license <> 'creativeCommon')"
    )
    # 고아 항목 정리 — 출처(occurrence)도 연습 기록(card)도 없는 항목만.
    # exam_questions 는 learning_items FK 가 NO ACTION 이라 참조 잔존분을 방어
    # (해당 시험은 콘텐츠 cascade 로 이미 소거되지만, 교차 참조 안전망)
    op.execute(
        "DELETE FROM learning_items li "
        "WHERE NOT EXISTS (SELECT 1 FROM item_occurrences io WHERE io.item_id = li.id) "
        "AND NOT EXISTS (SELECT 1 FROM review_cards rc WHERE rc.item_id = li.id) "
        "AND NOT EXISTS (SELECT 1 FROM exam_questions eq WHERE eq.item_id = li.id)"
    )


def downgrade() -> None:
    pass  # 콘텐츠 삭제는 비가역 — 필요 시 원본 영상 재등록으로 복원
