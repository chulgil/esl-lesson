"""친구 1:1 채팅 API — 전송은 REST 멱등 POST, 수신·읽음·입력중은 WS 푸시 (docs/specs/chat.md)."""

import logging
import re
import uuid
from pathlib import Path
from typing import Annotated, Literal

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
from app.services import chat, chat_match
from app.services import goals as goals_service
from app.services import notice as notice_service
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


# --- 언어 학습 방 (docs/specs/chat-language-rooms.md) ------------------------------


async def _get_room_or_404(db: AsyncSession, room_id: int, user_id: int) -> Conversation:
    room = await db.get(Conversation, room_id)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "room_not_found")
    if user_id not in (room.user_lo_id, room.user_hi_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_participant")
    return room


@router.get("/rooms")
async def rooms(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    return await chat.list_rooms(db, user)


class RoomCreateBody(BaseModel):
    peer_id: int
    source_lang: str
    target_lang: str
    # 'learn'(번역 표시, 기본) | 'plain'(일반 대화 — 번역 없음)
    mode: Literal["learn", "plain"] = "learn"


@router.post("/rooms", status_code=status.HTTP_201_CREATED)
async def create_room(
    payload: RoomCreateBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """친구 초대로 방 생성 — get-or-create (중복 생성 시도 = 기존 방 열기, 스펙 결정 #9)."""
    if payload.peer_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_chat_self")
    # plain 은 언어쌍을 ko→en 으로 정규화 저장 — 쌍당 일반 방 1개 (스펙 §일반 대화 방)
    source, target = (
        ("ko", "en") if payload.mode == "plain" else (payload.source_lang, payload.target_lang)
    )
    chat.validate_lang_pair(source, target)
    await chat.require_friend(db, user.id, payload.peer_id)
    room, created = await chat.get_or_create_room(
        db, user.id, payload.peer_id, source, target, mode=payload.mode
    )
    if created:
        peer_view = await chat.room_dict(db, room, payload.peer_id)
        delivered = await chat.deliver_ws(
            payload.peer_id, {"t": "chat.room_created", "room": peer_view}
        )
        if not delivered:
            try:
                await push_service.send_to_user(
                    db, payload.peer_id, chat.chat_push_payload(user.id, room.id)
                )
            except Exception:  # noqa: BLE001
                logger.warning("chat room_created push failed to=%s", payload.peer_id)
    return {"room": await chat.room_dict(db, room, user.id), "created": created}


@router.get("/rooms/{room_id}")
async def get_room(
    room_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    room = await _get_room_or_404(db, room_id, user.id)
    return await chat.room_dict(db, room, user.id)


@router.get("/rooms/{room_id}/messages")
async def room_messages(
    room_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    before: int | None = None,
    limit: int = 50,
) -> dict:
    room = await _get_room_or_404(db, room_id, user.id)
    items = await chat.get_room_messages(db, room.id, before=before, limit=limit)
    reads = await chat.get_read_positions(db, room.id)
    if room.mode == "learn":
        items = await _attach_room_translations(db, user.id, items, room.target_lang)
        await db.commit()
    else:
        # 일반 대화 방 — 번역 없이 친 그대로 (스펙 §일반 대화 방)
        items = [{**m, "translation": None} for m in items]
    return {
        "items": items,
        "reads": {str(uid): mid for uid, mid in reads.items()},
        "room": await chat.room_dict(db, room, user.id),
    }


@router.post("/rooms/{room_id}/read")
async def room_read(
    room_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    room = await _get_room_or_404(db, room_id, user.id)
    payload = await chat.mark_read_conv(db, room, user.id)
    peer_id = room.user_hi_id if room.user_lo_id == user.id else room.user_lo_id
    await chat.deliver_ws(peer_id, {"t": "chat.read", **payload})
    return {"ok": True}


@router.post("/rooms/{room_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def room_leave(
    room_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """멤버 누구나 나가면 양쪽 종료 — 멱등 204 (docs/specs/chat-language-rooms.md)."""
    room = await _get_room_or_404(db, room_id, user.id)
    peer_id = await chat.leave_room(db, room, user.id)
    if peer_id is not None:
        await chat.deliver_ws(peer_id, {"t": "chat.room_closed", "room_id": room.id})


class MatchJoinBody(BaseModel):
    source_lang: str
    target_lang: str
    mode: Literal["learn", "plain"] = "learn"


@router.post("/match")
async def join_match(
    payload: MatchJoinBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """대기열 참가 — 즉시 성사 시 {room}, 아니면 {waiting: true}."""
    source, target = (
        ("ko", "en") if payload.mode == "plain" else (payload.source_lang, payload.target_lang)
    )
    chat.validate_lang_pair(source, target)
    room = await chat_match.join(db, user.id, source, target, mode=payload.mode)
    if room is None:
        return {"waiting": True}
    peer_id = room.user_hi_id if room.user_lo_id == user.id else room.user_lo_id
    await chat.deliver_ws(
        user.id, {"t": "chat.matched", "room": await chat.room_dict(db, room, user.id)}
    )
    await chat.deliver_ws(
        peer_id, {"t": "chat.matched", "room": await chat.room_dict(db, room, peer_id)}
    )
    return {"room": await chat.room_dict(db, room, user.id)}


@router.get("/match")
async def match_status(user: Annotated[User, Depends(get_current_user)]) -> dict:
    return {"waiting": chat_match.waiting(user.id)}


@router.delete("/match", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_match(user: Annotated[User, Depends(get_current_user)]) -> None:
    chat_match.cancel(user.id)


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
        m
        for m in items
        if not m["deleted"]
        and not m.get("kind")  # 시스템 줄 제외 (docs/specs/chat-notice.md)
        and m["body"]
        and _in_scope(m, viewer_id, settings)
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


async def _attach_room_translations(
    db: AsyncSession, viewer_id: int, items: list[dict], target: str
) -> list[dict]:
    """방 기준 번역 동봉 — 뷰어 설정 무관, 방의 target_lang 을 항상 시도한다
    (docs/specs/chat-language-rooms.md 번역 규칙)."""
    out = []
    for m in items:
        if m["deleted"] or m.get("kind") or not m["body"]:
            out.append({**m, "translation": None})
            continue
        t = await translation_service.translate_to(db, viewer_id, m["body"], target)
        out.append({**m, "translation": t})
    return out


@router.get("/messages/{message_id}/translation")
async def message_translation(
    message_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """방 기준 번역 — 방의 target_lang 을 항상 시도한다(뷰어 설정 무관,
    docs/specs/chat-language-rooms.md 번역 규칙). WS 로 막 수신한 메시지의
    지연 로드용."""
    msg = await db.get(ChatMessage, message_id)
    if msg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message_not_found")
    conv = await db.get(Conversation, msg.conversation_id)
    if conv is None or user.id not in (conv.user_lo_id, conv.user_hi_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_participant")
    if msg.deleted_at is not None or not msg.body or msg.kind is not None or conv.mode != "learn":
        return {"translation": None}
    result = await translation_service.translate_to(db, user.id, msg.body, conv.target_lang)
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
    to_user_id: int | None = None  # 레거시 — room_id 가 있으면 무시 (가장 오래된 활성 방 위임)
    room_id: int | None = None
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

    translation = None
    if payload.room_id is not None:
        room = await _get_room_or_404(db, payload.room_id, user.id)
        data, created = await chat.send_room_message(
            db,
            user,
            room,
            payload.body,
            payload.client_msg_id,
            item_id=payload.item_id,
            image_path=payload.image_id,
            reply_to_id=payload.reply_to_id,
        )
        peer_id = room.user_hi_id if room.user_lo_id == user.id else room.user_lo_id
        # 방 기준 번역 동봉(낙관 렌더 치환용) — 방 UX 로만 한정, 레거시 to_user_id
        # 전송은 여전히 개인 설정(chat_translate) 기반 조회 경로를 따른다.
        # 일반 대화 방(plain)은 번역하지 않는다 (스펙 §일반 대화 방)
        if room.mode == "learn" and data.get("body") and not data.get("kind"):
            translation = await translation_service.translate_to(
                db, user.id, data["body"], room.target_lang
            )
            await db.commit()
    elif payload.to_user_id is not None:
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
        peer_id = payload.to_user_id
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "room_id_or_to_user_id_required")

    if created:
        message = {
            "t": "chat.message",
            "from_name": user.nickname,
            **data,
            "translation": translation,
        }
        delivered = await chat.deliver_ws(peer_id, message)
        # 미접속이면 웹푸시 (5분 스로틀) — 실패해도 전송 자체는 성공
        if not delivered and chat.should_push(data["conversation_id"], peer_id):
            try:
                await push_service.send_to_user(
                    db,
                    peer_id,
                    # 내용 없는 알림 — 잠금화면에 발신자·본문을 싣지 않는다
                    chat.chat_push_payload(user.id, data["conversation_id"]),
                )
            except Exception:  # noqa: BLE001
                logger.warning("chat push failed to=%s", peer_id)
    return {**data, "created": created, "translation": translation}


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


# --- 함께 목표 (docs/specs/shared-goals.md) --------------------------------------


async def _push_goal_sync(conv: Conversation) -> None:
    event = {"t": "goal.sync", "conversation_id": conv.id}
    await chat.deliver_ws(conv.user_lo_id, event)
    await chat.deliver_ws(conv.user_hi_id, event)


class GoalCreateBody(BaseModel):
    text: str = Field(max_length=100)


class GoalPatchBody(BaseModel):
    text: str | None = Field(default=None, max_length=100)
    done: bool | None = None


class WeeklyTargetBody(BaseModel):
    target_value: int


@router.get("/with/{other_id}/goals")
async def get_goals(
    other_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return await goals_service.get_view(db, user.id, other_id)


@router.post("/with/{other_id}/goals", status_code=status.HTTP_201_CREATED)
async def add_goal(
    other_id: int,
    payload: GoalCreateBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    item, conv = await goals_service.add_check(db, user.id, other_id, payload.text)
    await _push_goal_sync(conv)
    return item


@router.patch("/goals/{goal_id}")
async def patch_goal(
    goal_id: int,
    payload: GoalPatchBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    item, conv = await goals_service.patch_check(db, user.id, goal_id, payload.text, payload.done)
    await _push_goal_sync(conv)
    return item


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    conv = await goals_service.delete_check(db, user.id, goal_id)
    await _push_goal_sync(conv)


@router.delete("/with/{other_id}/goals", status_code=status.HTTP_204_NO_CONTENT)
async def clear_goal_board(
    other_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """보드 내리기 — 체크리스트+주간 목표 전부 삭제 (공지는 유지, 멱등)."""
    conv = await goals_service.clear_board(db, user.id, other_id)
    if conv is not None:
        await _push_goal_sync(conv)


@router.patch("/with/{other_id}/goals/weekly")
async def patch_weekly_goal(
    other_id: int,
    payload: WeeklyTargetBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    weekly, conv = await goals_service.set_weekly_target(
        db, user.id, other_id, payload.target_value
    )
    await _push_goal_sync(conv)
    return weekly


# --- 대화방 공지 (docs/specs/chat-notice.md) --------------------------------------


async def _push_notice_system_line(conv: Conversation, msg: dict, from_name: str) -> None:
    """시스템 줄을 기존 메시지 푸시 형식으로 — send 경로(chat.message)와 동일."""
    event = {"t": "chat.message", "from_name": from_name, **msg}
    await chat.deliver_ws(conv.user_lo_id, event)
    await chat.deliver_ws(conv.user_hi_id, event)


async def _push_notice_sync(conv: Conversation) -> None:
    event = {"t": "chat.notice", "conversation_id": conv.id}
    await chat.deliver_ws(conv.user_lo_id, event)
    await chat.deliver_ws(conv.user_hi_id, event)


class NoticeBody(BaseModel):
    title: str
    text: str = ""


@router.get("/with/{other_id}/notice")
async def get_notice(
    other_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return await notice_service.get_notice(db, user.id, other_id)


@router.put("/with/{other_id}/notice")
async def put_notice(
    other_id: int,
    payload: NoticeBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    notice, system_line, conv = await notice_service.set_notice(
        db, user.id, other_id, payload.title, payload.text
    )
    await _push_notice_system_line(conv, system_line, user.nickname)
    await _push_notice_sync(conv)
    return notice


@router.delete("/with/{other_id}/notice", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notice(
    other_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    system_line, conv = await notice_service.clear_notice(db, user.id, other_id)
    if conv is not None and system_line is not None:
        await _push_notice_system_line(conv, system_line, user.nickname)
        await _push_notice_sync(conv)
