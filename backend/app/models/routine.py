"""콘텐츠 루틴 여정 — 3파트 6단계 진행 + 한 문장 요약.

TED 10단계 루틴 흡수 (docs/proposal/ted-routine-2026-08.md): 카드 단위(FSRS)
위에 콘텐츠 단위 여정을 얹는 이층 구조. 단계는 1..6 —
1 자막 없이 듣기 / 2 중심 찾으며 듣기 / 3 직해(A-B 루프) / 4 카드 학습 /
5 섀도잉 / 6 한 문장 요약.
"""

from sqlalchemy import BigInteger, ForeignKey, SmallInteger, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin

ROUTINE_STEP_COUNT = 6


class ContentRoutineProgress(Base, PkMixin, CreatedAtMixin):
    """단계 체크 원장 — 행 존재 = 그 단계 완료 (체크 해제 시 행 삭제)."""

    __tablename__ = "content_routine_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "content_id", "step", name="uq_routine_user_content_step"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE")
    )
    step: Mapped[int] = mapped_column(SmallInteger)


class ContentSummary(Base, PkMixin, CreatedAtMixin):
    """한 문장 요약 제출 이력 — 액티브 인출. 최신 행이 화면 표시분."""

    __tablename__ = "content_summaries"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE")
    )
    text: Mapped[str] = mapped_column(Text)
    # LLM 의미 피드백 — 생성 실패 시 None (인출 자체가 목적이라 저장은 진행)
    feedback: Mapped[str | None] = mapped_column(Text)


class ListenCheck(Base, PkMixin, CreatedAtMixin):
    """재청취 이해도 셀프 체크 — stage 1(첫 청취) / 2(루틴 후), 1~5점.

    같은 영상의 전후 델타가 "안 들리던 게 들린다"의 측정 가능한 증거
    (docs/proposal/effectiveness-audit-2026-08.md P1). 재제출은 갱신(upsert).
    """

    __tablename__ = "listen_checks"
    __table_args__ = (
        UniqueConstraint("user_id", "content_id", "stage", name="uq_listen_user_content_stage"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE")
    )
    stage: Mapped[int] = mapped_column(SmallInteger)
    score: Mapped[int] = mapped_column(SmallInteger)
