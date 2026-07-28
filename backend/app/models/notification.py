"""알림 센터 — 친구 요청·수락·게임 초대 개인 알림함 (docs/specs/notifications.md)."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin
from app.models.types import JsonDict


class Notification(Base, PkMixin, CreatedAtMixin):
    """개인 알림. payload 는 발생 시점 스냅샷(닉네임 등) — 원본이 바뀌어도
    알림 문구는 불변 (chat_messages.item_ref 패턴)."""

    __tablename__ = "notifications"
    # 내 알림 최신순(id DESC) 조회 전용 — btree 역방향 스캔으로 충분
    __table_args__ = (Index("ix_notifications_user_id_id", "user_id", "id"),)

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(32))
    # {from_name, ...} — friend_request 는 request_id, game_invite 는 game·code 포함
    payload: Mapped[dict] = mapped_column(JsonDict)
    # null = 안읽음. 읽음 시각을 남겨 재읽음 처리에도 최초 시각 보존
    read_at: Mapped[datetime | None]
