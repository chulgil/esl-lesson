"""혼용 스크립트 번역 캐시 정리 — en/ja 번역문에 한글이 남은 오염 행 삭제

2026-08-21 실사용 제보: "원문에 읽는방법까지…" → "원文に読み方も…" 처럼
한글 음절이 섞인 번역이 전역 캐시에 박제됐다. 스크립트 가드
(services/translation._valid_translation) 도입과 함께 기존 오염분을 지운다 —
캐시는 재생성되므로 데이터 손실 없음.

Revision ID: i3d4e5f6a7b8
Revises: h2c3d4e5f6a7
Create Date: 2026-08-21
"""

from alembic import op

revision = "i3d4e5f6a7b8"
down_revision = "h2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM chat_translations WHERE target_lang IN ('en', 'ja') AND text ~ '[가-힣]'"
    )


def downgrade() -> None:
    pass  # 캐시 삭제는 비가역 — 재생성으로 복원된다
