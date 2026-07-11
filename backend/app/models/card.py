from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, PkMixin

CARD_STATES = ("new", "learning", "review", "relearning")


class ReviewCard(Base, PkMixin, CreatedAtMixin):
    __tablename__ = "review_cards"
    __table_args__ = (
        UniqueConstraint("user_id", "item_id", name="uq_cards_user_item"),
        CheckConstraint("state IN ('new','learning','review','relearning')", name="ck_cards_state"),
        Index(
            "idx_cards_due",
            "user_id",
            "due_at",
            postgresql_where="NOT suspended",
        ),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_items.id", ondelete="CASCADE")
    )
    state: Mapped[str] = mapped_column(Text, default="new", server_default="new")
    due_at: Mapped[datetime]
    stability: Mapped[float | None]
    difficulty: Mapped[float | None]
    reps: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    lapses: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    last_review_at: Mapped[datetime | None]

    logs: Mapped[list["ReviewLog"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )


class ReviewLog(Base, PkMixin):
    __tablename__ = "review_logs"
    __table_args__ = (Index("idx_logs_user_time", "user_id", "reviewed_at"),)

    card_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("review_cards.id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    rating: Mapped[int] = mapped_column(SmallInteger)
    correct: Mapped[bool] = mapped_column(Boolean)
    answer_text: Mapped[str | None] = mapped_column(Text)
    quiz_mode: Mapped[str] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    state_before: Mapped[str] = mapped_column(Text)
    scheduled_days: Mapped[float | None]
    elapsed_days: Mapped[float | None]
    reviewed_at: Mapped[datetime]

    card: Mapped[ReviewCard] = relationship(back_populates="logs")
