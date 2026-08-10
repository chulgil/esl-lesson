"""사용 이벤트 원장 — 관측 격차 해소 (P1-D, effectiveness-audit 4차 2026-08-10).

말하기 녹음·방법 화면·주간 성적표 열람·게임 오답 담기처럼 서버 기록이 없어
사용률을 잴 수 없던 표면의 최소 로깅. 분석은 SQL 로 — 백오피스 UI 없음(YAGNI).
"""

from sqlalchemy import BigInteger, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin
from app.models.types import JsonDict


class UsageEvent(Base, PkMixin, CreatedAtMixin):
    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_kind_time", "kind", "created_at"),)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JsonDict, default=dict)
