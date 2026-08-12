"""친구 1:1 채팅 API — 전송은 REST 멱등 POST, 수신·읽음·입력중은 WS 푸시 (docs/specs/chat.md)."""

import logging
import re
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_current_user
from app.models import ChatMessage, Conversation, LearningItem, User
from app.models.user import UserSettings
from app.services import chat
from app.services import push as push_service
from app.services import translation as translation_service
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


# --- 자동번역 동봉 (docs/specs/chat-translation.md) -------------------------------

TRANSLATE_WINDOW = 30  # 캐시 위주라 저비용이지만, 조회당 엔진 호출 상한은 둔다


def _in_scope(msg: dict, viewer_id: int, settings: UserSettings) -> bool:
    """번역 범위 — 내 글/상대 글 개별 체크 (2026-08-12 요청, 기본 내 글만)."""
    mine = msg["sender_id"] == viewer_id
    return settings.translate_mine if mine else settings.translate_theirs


async def _with_translations(
    db: AsyncSession, viewer_id: int, items: list[dict], settings: UserSettings
) -> list[dict]:
    """최신 30개(삭제 제외, 본문 있는 것, 범위 내)만 번역 동봉 — 새 dict 로 반환해
    인프로세스 캐시(_recent)의 원본 dict 를 건드리지 않는다(뷰어마다 타깃 언어가
    달라 공유 캐시를 오염시키면 안 됨)."""
    candidates = [
        m for m in items if not m["deleted"] and m["body"] and _in_scope(m, viewer_id, settings)
    ]
    window_ids = {m["id"] for m in candidates[-TRANSLATE_WINDOW:]}
    out = []
    for m in items:
        if m["id"] in window_ids:
            t = await translation_service.translate_chat(db, viewer_id, m["body"], settings)
            out.append({**m, "translation": t})
        else:
            out.append({**m, "translation": None})
    return out


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
    viewer_settings = await db.get(UserSettings, user.id)
    translate_on = bool(viewer_settings and viewer_settings.chat_translate)
    # 범위 체크가 둘 다 꺼져 있으면 실질 off — 클라이언트가 WS 수신분 조회를 스킵한다
    scope_mine = bool(translate_on and viewer_settings.translate_mine)
    scope_theirs = bool(translate_on and viewer_settings.translate_theirs)
    if conv is None:
        return {
            "items": [],
            "reads": {},
            "online": invite_hub.online(other_id),
            "peer": peer,
            "translate": translate_on,
            "translate_mine": scope_mine,
            "translate_theirs": scope_theirs,
        }
    items = await chat.get_messages(db, user.id, other_id, before=before, limit=limit)
    reads = await chat.get_read_positions(db, conv.id)
    if translate_on:
        items = await _with_translations(db, user.id, items, viewer_settings)
        await db.commit()
    return {
        "items": items,
        # 읽음 표시 초기 렌더: 상대의 마지막 읽음 위치
        "reads": {str(uid): mid for uid, mid in reads.items()},
        "online": invite_hub.online(other_id),
        "peer": peer,
        "translate": translate_on,
        "translate_mine": scope_mine,
        "translate_theirs": scope_theirs,
    }


@router.get("/messages/{message_id}/translation")
async def message_translation(
    message_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """WS 로 막 수신한 메시지의 번역 — 목록 조회(30개 창) 밖의 개별 메시지용."""
    msg = await db.get(ChatMessage, message_id)
    if msg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message_not_found")
    conv = await db.get(Conversation, msg.conversation_id)
    if conv is None or user.id not in (conv.user_lo_id, conv.user_hi_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_participant")
    viewer_settings = await db.get(UserSettings, user.id)
    if not (viewer_settings and viewer_settings.chat_translate):
        return {"translation": None}
    if msg.deleted_at is not None or not msg.body:
        return {"translation": None}
    # 범위 체크 — 내 글/상대 글 개별 설정 (2026-08-12)
    if not _in_scope({"sender_id": msg.sender_id}, user.id, viewer_settings):
        return {"translation": None}
    result = await translation_service.translate_chat(db, user.id, msg.body, viewer_settings)
    await db.commit()
    return {"translation": result}


# --- 이미지 업로드 (docs/specs/chat.md 이미지 전송) ------------------------------

IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
IMAGE_MAX_BYTES = 5 * 1024 * 1024  # 5MB - 2GB 서버 디스크 보호
# 서버가 발급한 파일명 형식만 통과 - 경로 조작 원천 차단
IMAGE_NAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp|gif)$")


@router.post("/uploads", status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile,
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    ext = IMAGE_TYPES.get(file.content_type or "")
    if ext is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unsupported_image_type")
    data = await file.read()
    if len(data) > IMAGE_MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "image_too_large")
    name = f"{uuid.uuid4().hex}{ext}"
    upload_dir = Path(get_settings().chat_upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / name).write_bytes(data)
    return {"image_id": name}


@router.get("/uploads/{name}")
async def serve_image(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    """대화 참여자만 열람 - 메시지에 귀속된 이미지의 대화 소속을 검사."""
    if IMAGE_NAME_RE.fullmatch(name) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "image_not_found")
    allowed = (
        await db.execute(
            select(ChatMessage.id)
            .join(Conversation, Conversation.id == ChatMessage.conversation_id)
            .where(
                ChatMessage.image_path == name,
                or_(
                    Conversation.user_lo_id == user.id,
                    Conversation.user_hi_id == user.id,
                ),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if allowed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "image_not_found")
    path = Path(get_settings().chat_upload_dir) / name
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "image_not_found")
    return FileResponse(path)


class SendBody(BaseModel):
    to_user_id: int
    body: str = Field(default="", max_length=chat.BODY_MAX)
    client_msg_id: str = Field(min_length=8, max_length=64)
    item_id: int | None = None
    image_id: str | None = None
    reply_to_id: int | None = None


@router.post("/messages", status_code=status.HTTP_201_CREATED)
async def send(
    payload: SendBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if payload.image_id is not None:
        if IMAGE_NAME_RE.fullmatch(payload.image_id) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_image_id")
        if not (Path(get_settings().chat_upload_dir) / payload.image_id).is_file():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "image_not_uploaded")
    data, created = await chat.send_message(
        db,
        user,
        payload.to_user_id,
        payload.body,
        payload.client_msg_id,
        item_id=payload.item_id,
        image_path=payload.image_id,
        reply_to_id=payload.reply_to_id,
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
                    # 내용 없는 알림 — 잠금화면에 발신자·본문을 싣지 않는다
                    chat.chat_push_payload(user.id, data["conversation_id"]),
                )
            except Exception:  # noqa: BLE001
                logger.warning("chat push failed to=%s", payload.to_user_id)
    return {**data, "created": created}


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """본인 메시지 삭제 (soft delete) — 클라는 "삭제되었습니다" 표기 (2026-07-31)."""
    await chat.delete_message(db, user, message_id)


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
