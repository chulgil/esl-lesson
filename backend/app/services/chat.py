"""친구 1:1 채팅 서비스 — 전송·히스토리·읽음·인프로세스 캐시 (docs/specs/chat.md).

캐시는 API 단일 인스턴스 전제. 수평 확장 시 인스턴스 간 신호는 Postgres
LISTEN/NOTIFY 를 쓴다 (Redis 도입 금지 — 2026-07-27 결정, 스펙 '범위 밖' 참조).
이 모듈의 함수 시그니처는 그대로 유지한다.
"""

import logging
from collections import deque
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, ChatRead, Conversation, Friendship, LearningItem, User
from app.services.friends import are_friends
from app.services.game.invites import invite_hub
from app.services.visibility import visible_item_clause

logger = logging.getLogger(__name__)

RECENT_CACHE_SIZE = 50  # 대화별 최근 메시지 링버퍼 크기 = 기본 페이지 크기
UNREAD_TTL_SECONDS = 30
PUSH_THROTTLE = timedelta(seconds=60)  # 같은 대화 웹푸시 최소 간격
BODY_MAX = 2000

# --- 인프로세스 캐시 -----------------------------------------------------------

# conversation_id -> 최근 메시지 dict 링버퍼 (오름차순). 콜드 스타트 시 DB 로드.
_recent: dict[int, deque[dict]] = {}
# user_id -> (안읽음 합계, 만료 시각)
_unread: dict[int, tuple[int, datetime]] = {}
# (conversation_id, to_user_id) -> 마지막 웹푸시 시각
_last_push: dict[tuple[int, int], datetime] = {}


def reset_caches() -> None:
    """테스트 격리용."""
    _recent.clear()
    _unread.clear()
    _last_push.clear()
    _last_typing.clear()


def _invalidate_unread(*user_ids: int) -> None:
    for uid in user_ids:
        _unread.pop(uid, None)


def cache_append(conversation_id: int, data: dict) -> None:
    """다른 서비스가 생성한 메시지(공지 시스템 줄 등)를 최근 캐시에 반영.

    캐시가 아직 워밍되지 않았으면(콜드 스타트) no-op — 다음 조회가 DB 에서
    읽어 자연히 최신 상태가 된다."""
    buf = _recent.get(conversation_id)
    if buf is not None:
        buf.append(data)


def message_dict(m: ChatMessage) -> dict:
    deleted = m.deleted_at is not None
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "sender_id": m.sender_id,
        # 삭제 메시지는 내용 소거 이중 방어 — 행에 남았더라도 응답엔 절대 미노출
        "body": "" if deleted else m.body,
        "item_ref": None if deleted else m.item_ref,
        "image_url": (
            None if deleted else (f"/api/chat/uploads/{m.image_path}" if m.image_path else None)
        ),
        "client_msg_id": m.client_msg_id,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "deleted": deleted,
        # 답장 인용 대상 — 미리보기(reply_to)는 읽기 시점에 attach_reply_previews 로
        "reply_to_id": None if deleted else m.reply_to_id,
        # 시스템 줄 표식 (docs/specs/chat-notice.md) — NULL=일반 메시지
        "kind": m.kind,
    }


async def attach_reply_previews(db: AsyncSession, items: list[dict]) -> list[dict]:
    """답장 인용 미리보기를 읽기 시점에 해석해 부착 (2026-07-31).

    스냅샷 저장 방식은 원문 삭제 후에도 내용이 남아 물리 소거 원칙과 충돌 —
    항상 현재 행 기준으로 미리보기를 만든다 (삭제된 원문 = "삭제되었습니다").
    캐시 dict 를 제자리 갱신하므로 캐시 히트 경로에서도 최신 상태가 유지된다."""
    ids = {m["reply_to_id"] for m in items if m.get("reply_to_id")}
    if not ids:
        return items
    rows = (await db.execute(select(ChatMessage).where(ChatMessage.id.in_(ids)))).scalars().all()
    by_id: dict[int, dict] = {}
    for r in rows:
        if r.deleted_at is not None:
            preview = "삭제되었습니다"
        else:
            preview = r.body or ("[사진]" if r.image_path else "[단어 카드]")
        by_id[r.id] = {
            "id": r.id,
            "sender_id": r.sender_id,
            "deleted": r.deleted_at is not None,
            "preview": preview[:80],
        }
    for m in items:
        rid = m.get("reply_to_id")
        m["reply_to"] = by_id.get(rid) if rid else None
    return items


# --- 친구·대화 -----------------------------------------------------------------


async def require_friend(db: AsyncSession, user_id: int, other_id: int) -> None:
    """수락된 친구가 아니면 404 (존재 비노출). 판정은 공용 are_friends 재사용."""
    if not await are_friends(db, user_id, other_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "friend_not_found")


def _pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


async def get_conversation(db: AsyncSession, a: int, b: int) -> Conversation | None:
    lo, hi = _pair(a, b)
    return (
        await db.execute(
            select(Conversation).where(Conversation.user_lo_id == lo, Conversation.user_hi_id == hi)
        )
    ).scalar_one_or_none()


async def get_or_create_conversation(db: AsyncSession, a: int, b: int) -> Conversation:
    conv = await get_conversation(db, a, b)
    if conv is not None:
        return conv
    lo, hi = _pair(a, b)
    conv = Conversation(user_lo_id=lo, user_hi_id=hi)
    db.add(conv)
    try:
        await db.commit()
    except IntegrityError:
        # 동시 첫 전송 레이스 — 상대가 먼저 만든 행 사용
        await db.rollback()
        conv = await get_conversation(db, a, b)
        if conv is None:  # pragma: no cover
            raise
    return conv


# --- 전송 ----------------------------------------------------------------------


async def snapshot_item(db: AsyncSession, user_id: int, item_id: int) -> dict:
    """학습 카드 스냅샷 — 내게 보이는 항목만, 서버가 내용을 채운다 (위조 방지)."""
    item = (
        await db.execute(
            select(LearningItem).where(LearningItem.id == item_id, visible_item_clause(user_id))
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item_not_found")
    return {
        "item_id": item.id,
        "item_type": item.item_type,
        "en_text": item.en_text,
        "ko_text": item.ko_text,
    }


async def send_message(
    db: AsyncSession,
    sender: User,
    to_user_id: int,
    body: str,
    client_msg_id: str,
    item_id: int | None = None,
    image_path: str | None = None,
    reply_to_id: int | None = None,
) -> tuple[dict, bool]:
    """저장 + 캐시 갱신. 반환 (메시지 dict, 신규 여부). 멱등: 같은 client_msg_id 는 기존 행."""
    if to_user_id == sender.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_chat_self")
    body = body.strip()
    if len(body) > BODY_MAX:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "body_too_long")
    if not body and item_id is None and image_path is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "empty_message")

    # 친구 삭제 후에는 조회만 허용, 전송은 차단 (기록 보존 원칙)
    if not await are_friends(db, sender.id, to_user_id):
        conv = await get_conversation(db, sender.id, to_user_id)
        if conv is not None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "not_friends")
        raise HTTPException(status.HTTP_404_NOT_FOUND, "friend_not_found")

    item_ref = await snapshot_item(db, sender.id, item_id) if item_id is not None else None
    conv = await get_or_create_conversation(db, sender.id, to_user_id)

    # 답장 대상 검증 — 반드시 같은 대화의 메시지 (타 대화 인용 = 정보 유출 경로).
    # 시스템 줄(kind 있음)은 인용 대상이 아님 (docs/specs/chat-notice.md)
    if reply_to_id is not None:
        target = await db.get(ChatMessage, reply_to_id)
        if target is None or target.conversation_id != conv.id or target.kind is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "reply_target_not_found")

    existing = (
        await db.execute(
            select(ChatMessage).where(
                ChatMessage.conversation_id == conv.id,
                ChatMessage.client_msg_id == client_msg_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return (await attach_reply_previews(db, [message_dict(existing)]))[0], False

    msg = ChatMessage(
        conversation_id=conv.id,
        sender_id=sender.id,
        body=body,
        item_ref=item_ref,
        image_path=image_path,
        client_msg_id=client_msg_id,
        reply_to_id=reply_to_id,
    )
    db.add(msg)
    conv.last_message_at = datetime.now(UTC)
    conv_id = conv.id  # rollback 은 ORM 객체를 만료시킨다 — 값으로 캡처
    try:
        await db.commit()
    except IntegrityError:
        # 동시 재전송 레이스 — 먼저 저장된 행 반환
        await db.rollback()
        existing = (
            await db.execute(
                select(ChatMessage).where(
                    ChatMessage.conversation_id == conv_id,
                    ChatMessage.client_msg_id == client_msg_id,
                )
            )
        ).scalar_one()
        return message_dict(existing), False
    await db.refresh(msg)

    data = (await attach_reply_previews(db, [message_dict(msg)]))[0]
    if conv_id in _recent:
        _recent[conv_id].append(data)
    _invalidate_unread(to_user_id)
    return data, True


async def delete_message(db: AsyncSession, user: User, message_id: int) -> None:
    """본인 메시지 soft delete — 행·커서 보존, 내용 소거, 양측에 WS 반영.

    타인/미존재는 404 (존재 비노출), 이미 삭제는 멱등 no-op (2026-07-31)."""
    msg = await db.get(ChatMessage, message_id)
    if msg is None or msg.sender_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message_not_found")
    if msg.deleted_at is None:
        msg.deleted_at = datetime.now(UTC)
        # 내용은 물리 소거 — soft delete 라도 본문·첨부는 남기지 않는다
        msg.body = ""
        msg.item_ref = None
        msg.image_path = None
        await db.commit()

    # 최근 캐시 반영 — 캐시 히트 조회에서 본문이 되살아나지 않게
    buf = _recent.get(msg.conversation_id)
    if buf is not None:
        refreshed = message_dict(msg)
        for idx, entry in enumerate(buf):
            if entry["id"] == message_id:
                buf[idx] = refreshed
                break

    # 열린 대화방 실시간 반영 — 양측 모두
    conv = await db.get(Conversation, msg.conversation_id)
    if conv is not None:
        event = {
            "t": "chat.deleted",
            "conversation_id": msg.conversation_id,
            "message_id": message_id,
        }
        await deliver_ws(conv.user_lo_id, event)
        await deliver_ws(conv.user_hi_id, event)


# --- 조회 ----------------------------------------------------------------------


async def _load_recent(db: AsyncSession, conversation_id: int) -> deque[dict]:
    """링버퍼 콜드 스타트 — DB 최신 50개."""
    rows = (
        (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.id.desc())
                .limit(RECENT_CACHE_SIZE)
            )
        )
        .scalars()
        .all()
    )
    buf: deque[dict] = deque(maxlen=RECENT_CACHE_SIZE)
    for m in reversed(rows):
        buf.append(message_dict(m))
    _recent[conversation_id] = buf
    return buf


async def get_messages(
    db: AsyncSession,
    user_id: int,
    other_id: int,
    before: int | None = None,
    limit: int = RECENT_CACHE_SIZE,
) -> list[dict]:
    """최신 요청(before 없음)은 캐시, 과거 스크롤(before)은 DB. 오름차순 반환."""
    conv = await get_conversation(db, user_id, other_id)
    if conv is None:
        return []
    limit = max(1, min(limit, RECENT_CACHE_SIZE))
    if before is None:
        buf = _recent.get(conv.id)
        if buf is None:
            buf = await _load_recent(db, conv.id)
        return await attach_reply_previews(db, list(buf)[-limit:])
    rows = (
        (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conv.id, ChatMessage.id < before)
                .order_by(ChatMessage.id.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return await attach_reply_previews(db, [message_dict(m) for m in reversed(rows)])


async def list_conversations(db: AsyncSession, user: User) -> list[dict]:
    convs = (
        (
            await db.execute(
                select(Conversation)
                .where(
                    or_(
                        Conversation.user_lo_id == user.id,
                        Conversation.user_hi_id == user.id,
                    )
                )
                .order_by(Conversation.last_message_at.desc().nulls_last())
            )
        )
        .scalars()
        .all()
    )
    if not convs:
        return []
    conv_ids = [c.id for c in convs]
    other_ids = [c.user_hi_id if c.user_lo_id == user.id else c.user_lo_id for c in convs]
    users = {
        u.id: u for u in (await db.execute(select(User).where(User.id.in_(other_ids)))).scalars()
    }
    # 대화별 마지막 메시지 (portable: max(id) IN)
    last_rows = (
        (
            await db.execute(
                select(ChatMessage).where(
                    ChatMessage.id.in_(
                        select(func.max(ChatMessage.id))
                        .where(ChatMessage.conversation_id.in_(conv_ids))
                        .group_by(ChatMessage.conversation_id)
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    last_by_conv = {m.conversation_id: m for m in last_rows}
    unread_by_conv = await _unread_by_conversation(db, user.id, conv_ids)

    out = []
    for conv in convs:
        other = users.get(conv.user_hi_id if conv.user_lo_id == user.id else conv.user_lo_id)
        if other is None:
            continue
        last = last_by_conv.get(conv.id)
        preview = None
        if last is not None:
            # 삭제된 메시지는 body/첨부가 소거돼 "[단어 카드]" 로 오표기됨 (재검토)
            if last.deleted_at is not None:
                preview = "삭제되었습니다"
            else:
                preview = last.body or ("[사진]" if last.image_path else "[단어 카드]")
        out.append(
            {
                "conversation_id": conv.id,
                "user_id": other.id,
                # 실명·구글 아바타 금지 (2026-07-27 결정) — 닉네임만 노출,
                # 아바타는 클라가 닉네임 이니셜로 생성
                "name": other.nickname,
                "online": invite_hub.online(other.id),
                "last_message": preview,
                "last_message_at": conv.last_message_at.isoformat()
                if conv.last_message_at
                else None,
                "unread": unread_by_conv.get(conv.id, 0),
            }
        )
    return out


async def _unread_by_conversation(
    db: AsyncSession, user_id: int, conv_ids: list[int]
) -> dict[int, int]:
    reads = dict(
        (
            await db.execute(
                select(ChatRead.conversation_id, ChatRead.last_read_message_id).where(
                    ChatRead.user_id == user_id, ChatRead.conversation_id.in_(conv_ids)
                )
            )
        ).all()
    )
    counts: dict[int, int] = {}
    rows = (
        await db.execute(
            select(ChatMessage.conversation_id, ChatMessage.id, ChatMessage.sender_id).where(
                ChatMessage.conversation_id.in_(conv_ids),
                ChatMessage.sender_id != user_id,
            )
        )
    ).all()
    for conv_id, msg_id, _sender in rows:
        if msg_id > reads.get(conv_id, 0):
            counts[conv_id] = counts.get(conv_id, 0) + 1
    return counts


async def unread_total(db: AsyncSession, user_id: int) -> int:
    """네비 배지용 합계 — TTL 캐시."""
    cached = _unread.get(user_id)
    now = datetime.now(UTC)
    if cached is not None and cached[1] > now:
        return cached[0]
    conv_ids = (
        (
            await db.execute(
                select(Conversation.id).where(
                    or_(
                        Conversation.user_lo_id == user_id,
                        Conversation.user_hi_id == user_id,
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    total = 0
    if conv_ids:
        total = sum((await _unread_by_conversation(db, user_id, list(conv_ids))).values())
    _unread[user_id] = (total, now + timedelta(seconds=UNREAD_TTL_SECONDS))
    return total


# --- 읽음 ----------------------------------------------------------------------


async def mark_read(db: AsyncSession, user_id: int, other_id: int) -> dict | None:
    """지금까지의 메시지를 읽음 처리. 반환값은 상대에게 보낼 chat.read 페이로드."""
    conv = await get_conversation(db, user_id, other_id)
    if conv is None:
        return None
    last_id = (
        await db.execute(
            select(func.max(ChatMessage.id)).where(ChatMessage.conversation_id == conv.id)
        )
    ).scalar_one() or 0
    read = (
        await db.execute(
            select(ChatRead).where(ChatRead.conversation_id == conv.id, ChatRead.user_id == user_id)
        )
    ).scalar_one_or_none()
    if read is None:
        read = ChatRead(conversation_id=conv.id, user_id=user_id, last_read_message_id=last_id)
        db.add(read)
    elif last_id > read.last_read_message_id:
        read.last_read_message_id = last_id
    await db.commit()
    _invalidate_unread(user_id)
    return {
        "conversation_id": conv.id,
        "user_id": user_id,
        "last_read_message_id": last_id,
    }


async def get_read_positions(db: AsyncSession, conversation_id: int) -> dict[int, int]:
    """대화방 진입 시 읽음 표시 초기 렌더용 — user_id -> last_read_message_id."""
    return dict(
        (
            await db.execute(
                select(ChatRead.user_id, ChatRead.last_read_message_id).where(
                    ChatRead.conversation_id == conversation_id
                )
            )
        ).all()
    )


# --- 실시간 전달·푸시 ------------------------------------------------------------


async def deliver_ws(user_id: int, message: dict) -> bool:
    """접속 중인 사용자의 모든 소켓에 전달 (invite_hub 레지스트리 재사용).

    True 는 최소 1개 소켓에 실제 전송 성공했을 때만 — 좀비 소켓(등록만 남고
    전송 실패)뿐이면 False 를 반환해 호출자가 웹푸시로 폴백하게 한다."""
    sends = list(invite_hub.sockets.get(user_id, []))
    if not sends:
        return False
    delivered = False
    for send in sends:
        try:
            await send(message)
            delivered = True
        except Exception:  # noqa: BLE001 — 한 소켓 실패가 나머지를 막으면 안 됨
            logger.warning("chat ws deliver failed user=%s", user_id)
    # 프리즈된 탭은 send 성공 + JS 정지 상태 — 최근 하트비트 없으면 미전달로
    # 간주해 웹푸시 폴백 (클라는 30초 간격 ping, TTL 90초)
    return delivered and invite_hub.alive(user_id)


def should_push(conversation_id: int, to_user_id: int) -> bool:
    """웹푸시 스팸 방지 — 같은 대화 5분 스로틀."""
    key = (conversation_id, to_user_id)
    now = datetime.now(UTC)
    last = _last_push.get(key)
    if last is not None and now - last < PUSH_THROTTLE:
        return False
    _last_push[key] = now
    return True


TYPING_THROTTLE = timedelta(seconds=2)
_last_typing: dict[tuple[int, int], datetime] = {}


def typing_allowed(from_id: int, to_id: int) -> bool:
    """DB 접근 전 저렴한 게이트 — 서버측 스로틀 + 수신자 접속 확인."""
    if not invite_hub.online(to_id):
        return False
    key = (from_id, to_id)
    now = datetime.now(UTC)
    last = _last_typing.get(key)
    if last is not None and now - last < TYPING_THROTTLE:
        return False
    _last_typing[key] = now
    return True


async def relay_typing(db: AsyncSession, from_id: int, to_id: int) -> None:
    """입력 중 표시 — 친구 관계일 때만 전달 (저장 안 함)."""
    if await are_friends(db, from_id, to_id):
        await deliver_ws(to_id, {"t": "chat.typing", "from_user_id": from_id})


async def broadcast_presence(db: AsyncSession, user_id: int, online: bool) -> None:
    """접속 상태 변화를 접속 중인 친구에게만 푸시 — 친구 수 소규모 전제."""
    rows = (
        (
            await db.execute(
                select(Friendship).where(
                    Friendship.status == "accepted",
                    or_(
                        Friendship.requester_id == user_id,
                        Friendship.addressee_id == user_id,
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    event = {"t": "presence", "user_id": user_id, "online": online}
    for row in rows:
        friend_id = row.addressee_id if row.requester_id == user_id else row.requester_id
        if invite_hub.online(friend_id):
            await deliver_ws(friend_id, event)


def chat_push_payload(sender_id: int, conversation_id: int) -> dict:
    """채팅 알림은 도착 사실만 — 발신자·본문을 싣지 않는다 (2026-08-04).

    잠금화면 미리보기가 위장 테마를 무력화한다(회사/공공장소 화면 보호,
    docs/specs/chat.md 위장 테마와 같은 목적). 숨김은 채팅 한정 — 게임 초대와
    복습 리마인더는 종전대로 문구를 그대로 싣는다.

    표시 문구는 `kind: "chat"` 표식을 보고 서비스 워커가 수신자 테마 라벨
    ("교환 노트"/"공유 문서" 등)로 갈아끼운다. 여기 값은 표식을 모르는 구형
    워커를 위한 폴백이라 그 자체로도 중립이어야 한다."""
    return {
        "kind": "chat",
        "title": "교환 노트",
        "body": "새 글이 있어요",
        "url": f"/chat/{sender_id}",
        "tag": f"chat-{conversation_id}",
    }
