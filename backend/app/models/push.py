from datetime import date

from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin


class PushSubscription(Base, PkMixin, CreatedAtMixin):
    """웹 푸시 구독 — 브라우저(기기)당 1행 (docs/specs/push-reminder.md)."""

    __tablename__ = "push_subscriptions"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(Text)
    auth: Mapped[str] = mapped_column(Text)
    # KST 기준 마지막 리마인더 발송일 — 하루 1회 dedup
    last_sent_on: Mapped[date | None]
