from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, PkMixin, TimestampMixin
from app.models.types import JsonDict

CONTENT_STATUSES = ("pending", "extracting", "ready", "failed")
JOB_STEPS = ("metadata", "transcript", "translate", "extract")
JOB_STATUSES = ("pending", "running", "done", "failed")


class Content(Base, PkMixin, TimestampMixin):
    __tablename__ = "contents"
    __table_args__ = (
        CheckConstraint("source IN ('youtube','manual')", name="ck_contents_source"),
        CheckConstraint(
            "status IN ('pending','extracting','ready','failed')",
            name="ck_contents_status",
        ),
        CheckConstraint("visibility IN ('public','private')", name="ck_contents_visibility"),
    )

    source: Mapped[str] = mapped_column(Text)
    # public=백오피스 공용(검수 후 전체), private=개인 등록(본인 전용)
    # 규칙: docs/specs/content-pipeline.md 콘텐츠 가시성
    visibility: Mapped[str] = mapped_column(Text, default="public", server_default="public")
    youtube_video_id: Mapped[str | None] = mapped_column(Text, unique=True)
    # Data API status.license — creativeCommons | youtube | NULL(미확인). 공용 승격 CC 게이트
    youtube_license: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    title_ko: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending", server_default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )

    segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="content", cascade="all, delete-orphan", order_by="TranscriptSegment.seq"
    )
    jobs: Mapped[list["ExtractionJob"]] = relationship(
        back_populates="content", cascade="all, delete-orphan"
    )


class ContentPermission(Base, PkMixin, CreatedAtMixin):
    """원저작자 이용허락 증빙 (docs/specs/content-governance.md).

    비 CC 영상은 이 행이 있어야 공용 등록된다. 체크박스 하나로 게이트를 뚫으면
    분쟁 시 "허락받았다"를 입증할 데이터가 남지 않는다.
    """

    __tablename__ = "content_permissions"

    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE"), unique=True
    )
    rights_holder: Mapped[str] = mapped_column(Text)
    rights_holder_contact: Mapped[str | None] = mapped_column(Text)
    granted_at: Mapped[date] = mapped_column(Date)
    # 파이프라인이 실제로 수행하는 이용 — 셋 다 허락돼야 등록 가능
    scope_transcript: Mapped[bool] = mapped_column(Boolean)  # 자막 복제·서버 저장
    scope_translate: Mapped[bool] = mapped_column(Boolean)  # 번역 (제22조 2차적저작물)
    scope_derive: Mapped[bool] = mapped_column(Boolean)  # 학습 항목 추출·변형
    # 등록을 막지는 않지만, 수익화 시 제외 대상 판별을 위해 지금 기록해 둔다
    scope_commercial: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[str] = mapped_column(Text)  # 증빙 위치(메일 링크·보관 경로) 또는 요지
    note: Mapped[str | None] = mapped_column(Text)  # 조건·기간·해지 등 특약
    recorded_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )


class ContentSubscription(Base, PkMixin, CreatedAtMixin):
    """콘텐츠 구독 — 같은 영상을 여러 사용자가 공유 (중복 등록 없이 즉시 재사용)."""

    __tablename__ = "content_subscriptions"
    __table_args__ = (
        UniqueConstraint("content_id", "user_id", name="uq_subscriptions_content_user"),
    )

    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))


class TranscriptSegment(Base, PkMixin):
    __tablename__ = "transcript_segments"
    __table_args__ = (UniqueConstraint("content_id", "seq", name="uq_segments_content_seq"),)

    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE")
    )
    seq: Mapped[int] = mapped_column(Integer)
    start_ms: Mapped[int | None] = mapped_column(Integer)
    end_ms: Mapped[int | None] = mapped_column(Integer)
    en_text: Mapped[str] = mapped_column(Text)
    ko_text: Mapped[str | None] = mapped_column(Text)
    # 단어별 시각 [{"w","s","e"}] — 로컬 에이전트 정렬 결과 (docs/specs/word-alignment.md).
    # NULL = 미정렬 → 프론트는 보간 경계로 폴백
    words: Mapped[list | None] = mapped_column(JsonDict, nullable=True)

    content: Mapped[Content] = relationship(back_populates="segments")


class ExtractionJob(Base, PkMixin):
    __tablename__ = "extraction_jobs"
    __table_args__ = (
        CheckConstraint(
            "step IN ('metadata','transcript','translate','extract','embed','align')",
            name="ck_jobs_step",
        ),
        CheckConstraint("status IN ('pending','running','done','failed')", name="ck_jobs_status"),
    )

    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE")
    )
    step: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending", server_default="pending")
    attempt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JsonDict, default=dict)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]

    content: Mapped[Content] = relationship(back_populates="jobs")
