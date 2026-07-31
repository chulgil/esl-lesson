"""친구 1:1 채팅 — 대화·메시지·읽음 (docs/specs/chat.md)."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin
from app.models.types import JsonDict


class Conversation(Base, PkMixin, CreatedAtMixin):
    """1:1 대화방 — user_lo < user_hi 정규화로 쌍당 1행."""

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("user_lo_id", "user_hi_id", name="uq_conversations_pair"),
        CheckConstraint("user_lo_id < user_hi_id", name="ck_conversations_ordered"),
    )

    user_lo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    user_hi_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    # 비정규화 — 대화 목록 정렬에 메시지 조인 불필요
    last_message_at: Mapped[datetime | None]


class ChatMessage(Base, PkMixin):
    """메시지. id 가 커서(시간순 단조). item_ref 는 학습 카드 스냅샷 —
    원본 항목이 삭제·수정돼도 대화 기록은 불변 (기록 보존 원칙)."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "client_msg_id", name="uq_chat_messages_client"),
        Index("ix_chat_messages_conv_id_desc", "conversation_id", "id"),
    )

    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversations.id", ondelete="CASCADE")
    )
    sender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    # {item_id, item_type, en_text, ko_text} — 전송 시점 서버 스냅샷
    item_ref: Mapped[dict | None] = mapped_column(JsonDict, nullable=True)
    # 업로드 이미지 파일명 (uuid.ext) — 참여자만 GET /api/chat/uploads/{name} 로 열람
    image_path: Mapped[str | None] = mapped_column(Text)
    # soft delete — 행·커서는 보존, 내용은 소거 후 "삭제되었습니다" 표기 (2026-07-31)
    deleted_at: Mapped[datetime | None]
    # 답장 대상 (카톡식 인용, 2026-07-31) — 원문 미리보기는 읽기 시점 조회
    # (스냅샷이면 원문 삭제 후에도 내용이 남아 물리 소거 원칙과 충돌)
    reply_to_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True
    )
    client_msg_id: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ChatRead(Base, PkMixin):
    """읽음 위치 — 읽음 표시("1")와 안읽음 카운트의 단일 근거."""

    __tablename__ = "chat_reads"
    __table_args__ = (UniqueConstraint("conversation_id", "user_id", name="uq_chat_reads_user"),)

    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversations.id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    last_read_message_id: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
