"""라이브러리 시험 — 콘텐츠별 고정 시험지·응시 기록 (docs/specs/library-exam.md).

문항은 생성 시점 payload 스냅샷으로 고정 — 원본 항목 수정/거절과 무관하게
채점이 자립한다. 랭킹은 exam_attempts 실시간 집계 (적립 테이블 없음).
"""

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, PkMixin
from app.models.types import JsonDict

EXAM_STATUSES = ("active", "archived")


class Exam(Base, PkMixin, CreatedAtMixin):
    """시험지 회차 — 콘텐츠당 active 1개, 재생성 = 기존 archived + round+1."""

    __tablename__ = "exams"
    __table_args__ = (
        UniqueConstraint("content_id", "round", name="uq_exams_content_round"),
        CheckConstraint("status IN ('active','archived')", name="ck_exams_status"),
        # 콘텐츠당 active 1개를 DB 가 강제 — 동시 재생성 경합으로 active 2개가
        # 남으면 요약 조회가 영구 500 (2026-07-31 심층 리뷰). 부분 유니크 인덱스
        Index(
            "uq_exams_content_active",
            "content_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE")
    )
    round: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, default="active", server_default="active")
    # 스냅샷 문항 수 (기본 20, 항목 부족 시 실제 수) — 화면 표기용
    question_count: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )

    questions: Mapped[list["ExamQuestion"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan", order_by="ExamQuestion.seq"
    )


class ExamQuestion(Base, PkMixin):
    """문항 스냅샷 — 채점은 payload.answer_index 로 자립 (item_id 는 참조용)."""

    __tablename__ = "exam_questions"
    __table_args__ = (UniqueConstraint("exam_id", "seq", name="uq_exam_questions_exam_seq"),)

    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exams.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)  # 1..N 출제 순서
    item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("learning_items.id", ondelete="SET NULL")
    )
    # {quiz_mode, prompt, prompt_ko?, choices[4], answer_index, en_text, ko_text}
    payload: Mapped[dict] = mapped_column(JsonDict)

    exam: Mapped[Exam] = relationship(back_populates="questions")


class ExamAttempt(Base, PkMixin):
    """응시 1회 — started_at 서버 기록, submitted_at NULL = 진행 중/이탈."""

    __tablename__ = "exam_attempts"

    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exams.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    # 응시 시작 = attempt 생성 (서버 시각 — 클라 신뢰 금지)
    started_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    submitted_at: Mapped[datetime | None]
    score: Mapped[int | None] = mapped_column(Integer)  # 정답수 x 5
    correct_count: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)  # 서버 시각차
    answers: Mapped[list | None] = mapped_column(JsonDict, nullable=True)  # 복기용 선택 index
