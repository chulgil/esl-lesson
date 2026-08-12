"""번역 캐시 재무효화 — 인젝션 방어 전 오염분 제거

Revision ID: ad5b7ffdd7fb
Revises: d8bc3d9a849f
Create Date: 2026-08-12
"""

from alembic import op

revision = "ad5b7ffdd7fb"
down_revision = "d8bc3d9a849f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 지시로 해석된 메시지의 응답이 캐시에 남아있다 (2026-08-12 크리티컬 제보)
    # — 방어 배포와 함께 전량 재번역 (캐시 재구축 비용은 미미)
    op.execute("DELETE FROM chat_translations")


def downgrade() -> None:
    pass  # 캐시 삭제는 되돌릴 데이터가 없음 — 재번역으로 자연 복구
