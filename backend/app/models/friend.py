from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin

FRIEND_STATUSES = ("pending", "accepted")


class Friendship(Base, PkMixin, CreatedAtMixin):
    """친구 관계 — 요청(pending) → 수락(accepted). 한 쌍당 1행 (docs/specs/study-spectate.md)."""

    __tablename__ = "friendships"
    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friend_pair"),
        CheckConstraint("status IN ('pending','accepted')", name="ck_friend_status"),
        CheckConstraint("requester_id != addressee_id", name="ck_friend_not_self"),
    )

    requester_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE")
    )
    addressee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(Text, default="pending", server_default="pending")
