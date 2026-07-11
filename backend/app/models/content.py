from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PkMixin, TimestampMixin
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

    content: Mapped[Content] = relationship(back_populates="segments")


class ExtractionJob(Base, PkMixin):
    __tablename__ = "extraction_jobs"
    __table_args__ = (
        CheckConstraint(
            "step IN ('metadata','transcript','translate','extract')",
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
