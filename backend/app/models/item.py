from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PkMixin, TimestampMixin
from app.models.types import JsonDict

ITEM_TYPES = ("word", "idiom", "pattern", "sentence")
ITEM_TYPE_LEVEL = {"word": 1, "idiom": 2, "pattern": 3, "sentence": 4}
REVIEW_STATUSES = ("pending", "approved", "rejected")


def normalize_key(text: str) -> str:
    """전역 dedup 키: 소문자 + 공백 정규화 (docs/specs/content-pipeline.md)."""
    return " ".join(text.lower().split())


class LearningItem(Base, PkMixin, TimestampMixin):
    __tablename__ = "learning_items"
    __table_args__ = (
        UniqueConstraint("item_type", "normalized_key", name="uq_items_type_key"),
        CheckConstraint("item_type IN ('word','idiom','pattern','sentence')", name="ck_items_type"),
        CheckConstraint(
            "review_status IN ('pending','approved','rejected')",
            name="ck_items_review_status",
        ),
        CheckConstraint(
            "difficulty_hint IN ('basic','intermediate','advanced')",
            name="ck_items_difficulty",
        ),
    )

    item_type: Mapped[str] = mapped_column(Text)
    en_text: Mapped[str] = mapped_column(Text)
    ko_text: Mapped[str] = mapped_column(Text)
    normalized_key: Mapped[str] = mapped_column(Text)
    hint_thinking: Mapped[str | None] = mapped_column(Text)
    pattern_template: Mapped[str | None] = mapped_column(Text)
    difficulty_hint: Mapped[str] = mapped_column(
        Text, default="intermediate", server_default="intermediate"
    )
    review_status: Mapped[str] = mapped_column(Text, default="pending", server_default="pending")
    extra: Mapped[dict] = mapped_column(JsonDict, default=dict)

    occurrences: Mapped[list["ItemOccurrence"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )

    @property
    def level(self) -> int:
        return ITEM_TYPE_LEVEL[self.item_type]


class ItemOccurrence(Base, PkMixin):
    __tablename__ = "item_occurrences"
    __table_args__ = (
        UniqueConstraint(
            "item_id", "content_id", "segment_id", name="uq_occurrences_item_content_segment"
        ),
    )

    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_items.id", ondelete="CASCADE")
    )
    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE")
    )
    segment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("transcript_segments.id", ondelete="SET NULL")
    )
    context_en: Mapped[str | None] = mapped_column(Text)
    context_ko: Mapped[str | None] = mapped_column(Text)

    item: Mapped[LearningItem] = relationship(back_populates="occurrences")


class WordInsight(Base, PkMixin, TimestampMixin):
    """단어 인사이트 캐시 — 항목당 LLM 1회 생성 후 전역 공유 (docs/proposal/word-insight.md)."""

    __tablename__ = "word_insights"

    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_items.id", ondelete="CASCADE"), unique=True
    )
    payload: Mapped[dict] = mapped_column(JsonDict)
    model: Mapped[str] = mapped_column(Text)
