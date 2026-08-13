"""대화방 공지 — 자유 텍스트 고정 공지 (docs/specs/chat-notice.md).

공지 본문은 shared_goals 의 kind="notice" 행 (대화당 1행 — goals._weekly_row 와
같은 "대화당 1행" 패턴, 새로 쓰면 교체). 변경 성공 시 chat_messages 에 시스템 줄
(kind="notice_set"/"notice_clear")을 일반 메시지처럼 적재해 채팅 흐름 안에서
인지시킨다 — 별도 푸시·벨 없음(스펙 결정). 웹푸시는 이 경로에서 호출하지 않는다.
"""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, Conversation, SharedGoal, User
from app.services import chat as chat_service
from app.services import goals as goals_service

NOTICE_MAX = 500
TITLE_MAX = 80
PREVIEW_MAX = 80


async def _existing_conversation_or_404(
    db: AsyncSession, user_id: int, other_id: int
) -> Conversation | None:
    """대화가 없으면 친구 검증 후 None — GET/DELETE 공용 (goals.get_view 패턴)."""
    conv = await chat_service.get_conversation(db, user_id, other_id)
    if conv is None:
        await chat_service.require_friend(db, user_id, other_id)
    return conv


async def _get_or_create_conversation(
    db: AsyncSession, user_id: int, other_id: int
) -> Conversation:
    """대화가 없으면 친구 검증 후 생성 — messages 전송 경로와 동일 게이트."""
    conv = await chat_service.get_conversation(db, user_id, other_id)
    if conv is None:
        await chat_service.require_friend(db, user_id, other_id)
        conv = await chat_service.get_or_create_conversation(db, user_id, other_id)
    return conv


async def _require_mutable(db: AsyncSession, conv: Conversation, user_id: int) -> None:
    """친구 해제 후에는 조회만 남는다 — 변경은 403 (goals·chat 전송 경로와 동일 규칙)."""
    other = goals_service.other_participant(conv, user_id)
    if not await chat_service.are_friends(db, user_id, other):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_friends")


async def _notice_row(db: AsyncSession, conv_id: int) -> SharedGoal | None:
    return (
        await db.execute(
            select(SharedGoal).where(
                SharedGoal.conversation_id == conv_id, SharedGoal.kind == "notice"
            )
        )
    ).scalar_one_or_none()


async def _notice_dict(db: AsyncSession, conv: Conversation) -> dict:
    row = await _notice_row(db, conv.id)
    # title 도입(2026-08-13) 이전 레거시 행은 text 만 있어도 성립
    if row is None or not (row.title or row.text):
        return {"title": None, "text": None}
    editor = await db.get(User, row.created_by) if row.created_by else None
    return {
        "title": row.title,
        "text": row.text,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by_name": editor.nickname if editor else None,
    }


async def _record_system_line(
    db: AsyncSession, conv: Conversation, editor_id: int, kind: str, body: str
) -> dict:
    """시스템 줄 적재 — 일반 메시지 파이프라인(last_message_at·최근 캐시)을 그대로
    탄다. 웹푸시는 호출하지 않는다(조용한 인지, 스펙 결정)."""
    msg = ChatMessage(
        conversation_id=conv.id,
        sender_id=editor_id,
        body=body,
        kind=kind,
        client_msg_id=f"notice-{uuid.uuid4().hex}",
    )
    db.add(msg)
    conv.last_message_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(msg)
    data = chat_service.message_dict(msg)
    chat_service.cache_append(conv.id, data)
    return data


async def get_notice(db: AsyncSession, user_id: int, other_id: int) -> dict:
    """GET /with/{other_id}/notice — 대화가 없으면 친구 검증 후 빈 응답."""
    conv = await _existing_conversation_or_404(db, user_id, other_id)
    if conv is None:
        return {"title": None, "text": None}
    return await _notice_dict(db, conv)


async def set_notice(
    db: AsyncSession, user_id: int, other_id: int, title: str, text: str
) -> tuple[dict, dict, Conversation]:
    """PUT — upsert. 제목 필수(한 줄, 80자), 내용 선택(500자).

    반환: (공지 뷰, 시스템 줄 메시지, 대화)."""
    title = title.strip()
    if not title or "\n" in title:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_title")
    if len(title) > TITLE_MAX:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "title_too_long")
    text = text.strip()
    if len(text) > NOTICE_MAX:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "text_too_long")
    conv = await _get_or_create_conversation(db, user_id, other_id)
    await _require_mutable(db, conv, user_id)
    row = await _notice_row(db, conv.id)
    if row is None:
        row = SharedGoal(conversation_id=conv.id, kind="notice")
        db.add(row)
    row.title = title
    row.text = text
    row.created_by = user_id
    await db.commit()
    await db.refresh(row)
    # 제목이 곧 미리보기 — TITLE_MAX(80) <= PREVIEW_MAX 라 자름 없음
    system_line = await _record_system_line(db, conv, user_id, "notice_set", title)
    return await _notice_dict(db, conv), system_line, conv


async def clear_notice(
    db: AsyncSession, user_id: int, other_id: int
) -> tuple[dict | None, Conversation | None]:
    """DELETE — 멱등. 공지가 없으면 조용히 no-op (시스템 줄·WS 없음).

    반환: (시스템 줄 메시지 또는 None, 대화 또는 None) — API 는 둘 다 값이 있을
    때만 WS 를 푸시한다.
    """
    conv = await _existing_conversation_or_404(db, user_id, other_id)
    if conv is None:
        return None, None
    await _require_mutable(db, conv, user_id)
    row = await _notice_row(db, conv.id)
    if row is None or not (row.title or row.text):
        return None, conv
    row.title = None
    row.text = ""
    row.created_by = user_id
    await db.commit()
    system_line = await _record_system_line(db, conv, user_id, "notice_clear", "")
    return system_line, conv
