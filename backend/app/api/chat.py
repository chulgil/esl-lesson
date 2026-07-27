"""친구 1:1 채팅 API — 전송은 REST 멱등 POST, 수신·읽음·입력중은 WS 푸시 (docs/specs/chat.md)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import LearningItem, User
from app.services import chat
from app.services import push as push_service
from app.services.game.invites import invite_hub
from app.services.visibility import visible_item_clause

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/conversations")
async def conversations(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {"items": await chat.list_conversations(db, user)}


@router.get("/unread-total")
async def unread_total(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {"total": await chat.unread_total(db, user.id)}


@router.get("/with/{other_id}/messages")
async def messages(
    other_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    before: int | None = None,
    limit: int = 50,
) -> dict:
    # 친구 삭제 후에도 기존 대화 조회는 허용 (기록 보존) — 대화가 없으면 친구 검증
    conv = await chat.get_conversation(db, user.id, other_id)
    if conv is None:
        await chat.require_friend(db, user.id, other_id)
    other = await db.get(User, other_id)
    # 실명·구글 아바타 금지 (2026-07-27 결정) — 닉네임만
    peer = {"user_id": other.id, "name": other.nickname} if other is not None else None
    if conv is None:
        return {"items": [], "reads": {}, "online": invite_hub.online(other_id), "peer": peer}
    items = await chat.get_messages(db, user.id, other_id, before=before, limit=limit)
    reads = await chat.get_read_positions(db, conv.id)
    return {
        "items": items,
        # 읽음 표시 초기 렌더: 상대의 마지막 읽음 위치
        "reads": {str(uid): mid for uid, mid in reads.items()},
        "online": invite_hub.online(other_id),
        "peer": peer,
    }


class SendBody(BaseModel):
    to_user_id: int
    body: str = Field(default="", max_length=chat.BODY_MAX)
    client_msg_id: str = Field(min_length=8, max_length=64)
    item_id: int | None = None


@router.post("/messages", status_code=status.HTTP_201_CREATED)
async def send(
    payload: SendBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    data, created = await chat.send_message(
        db,
        user,
        payload.to_user_id,
        payload.body,
        payload.client_msg_id,
        item_id=payload.item_id,
    )
    if created:
        message = {"t": "chat.message", "from_name": user.nickname, **data}
        delivered = await chat.deliver_ws(payload.to_user_id, message)
        # 미접속이면 웹푸시 (5분 스로틀) — 실패해도 전송 자체는 성공
        if not delivered and chat.should_push(data["conversation_id"], payload.to_user_id):
            try:
                await push_service.send_to_user(
                    db,
                    payload.to_user_id,
                    chat.chat_push_payload(
                        user.nickname, data["body"], user.id, data["conversation_id"]
                    ),
                )
            except Exception:  # noqa: BLE001
                logger.warning("chat push failed to=%s", payload.to_user_id)
    return {**data, "created": created}


@router.post("/with/{other_id}/read")
async def mark_read(
    other_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    payload = await chat.mark_read(db, user.id, other_id)
    if payload is not None:
        await chat.deliver_ws(other_id, {"t": "chat.read", **payload})
    return {"ok": True}


@router.get("/shareable-items")
async def shareable_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    q: str = "",
) -> dict:
    """단어 공유 카드 첨부용 — 내게 보이는 학습 항목 검색 (최대 20개)."""
    query = (
        select(LearningItem)
        .where(visible_item_clause(user.id))
        .order_by(LearningItem.id.desc())
        .limit(20)
    )
    if q.strip():
        query = query.where(LearningItem.en_text.ilike(f"%{q.strip()}%"))
    rows = (await db.execute(query)).scalars().all()
    return {
        "items": [
            {
                "id": i.id,
                "item_type": i.item_type,
                "en_text": i.en_text,
                "ko_text": i.ko_text,
            }
            for i in rows
        ]
    }
