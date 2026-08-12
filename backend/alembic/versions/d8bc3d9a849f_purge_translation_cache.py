"""번역 캐시 재무효화 — 프롬프트 2차 개선 (어조 준수·슬랭 금지) 반영

Revision ID: d8bc3d9a849f
Revises: 92b27ad838a9
Create Date: 2026-08-12
"""

from alembic import op

revision = "d8bc3d9a849f"
down_revision = "92b27ad838a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1차 프롬프트(슬랭 과다) 산출물 소량(실측 22건)을 비워 최종 프롬프트로 재번역
    op.execute("DELETE FROM chat_translations")


def downgrade() -> None:
    pass  # 캐시 삭제는 되돌릴 데이터가 없음 — 재번역으로 자연 복구
