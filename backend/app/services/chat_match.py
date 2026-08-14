"""언어 학습 랜덤 매칭 — 인프로세스 대기열 (docs/specs/chat-language-rooms.md).

Redis 없이 단일 인스턴스 전제 (채팅 캐시와 동일 결정, docs/specs/chat.md). 서버
재시작 시 대기열은 소실되며 클라 폴링이 waiting 해제를 감지해 재시도 UI를 띄운다
(스펙 결정 — 허용 범위).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation
from app.services import chat as chat_service

WAIT_TTL = timedelta(minutes=10)
REMATCH_COOLDOWN = timedelta(hours=24)

# (mode, source_lang, target_lang) -> [(user_id, joined_at)] — 선착순 매칭.
# 일반 대화(plain)는 언어쌍이 ko→en 으로 정규화돼 단일 버킷이 된다 (스펙 §일반 대화 방)
_queue: dict[tuple[str, str, str], list[tuple[int, datetime]]] = {}
# user_id -> (mode, source_lang, target_lang) — 재참가 시 이전 대기 제거·waiting 조회용
_by_user: dict[int, tuple[str, str, str]] = {}


def reset() -> None:
    """테스트 격리용."""
    _queue.clear()
    _by_user.clear()


def _aware(dt: datetime) -> datetime:
    """sqlite(테스트) 왕복 시 naive 로 돌아온다 — UTC 저장 규칙이라 그대로 부착."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _prune(key: tuple[str, str, str], now: datetime) -> None:
    """TTL(10분) 초과 대기자를 제거 — _by_user 도 함께 정리한다."""
    entries = _queue.get(key)
    if not entries:
        return
    kept = []
    for uid, joined_at in entries:
        if now - joined_at < WAIT_TTL:
            kept.append((uid, joined_at))
        else:
            _by_user.pop(uid, None)
    if kept:
        _queue[key] = kept
    else:
        _queue.pop(key, None)


def _leave_previous(user_id: int) -> None:
    """사용자당 대기 1건 — 새 참가가 이전 대기를 대체한다."""
    prev_key = _by_user.pop(user_id, None)
    if prev_key is None:
        return
    entries = _queue.get(prev_key)
    if entries is None:
        return
    remaining = [(uid, t) for uid, t in entries if uid != user_id]
    if remaining:
        _queue[prev_key] = remaining
    else:
        _queue.pop(prev_key, None)


async def _recently_closed_with(
    db: AsyncSession, a: int, b: int, source_lang: str, target_lang: str, mode: str
) -> bool:
    """24h 내 같은 언어쌍으로 종료(closed)한 상대는 재매칭 대상에서 제외."""
    conv = await chat_service.get_room_by_langs(db, a, b, source_lang, target_lang, mode)
    if conv is None or conv.status != "closed" or conv.closed_at is None:
        return False
    return datetime.now(UTC) - _aware(conv.closed_at) < REMATCH_COOLDOWN


async def join(
    db: AsyncSession, user_id: int, source_lang: str, target_lang: str, mode: str = "learn"
) -> Conversation | None:
    """대기열 참가 — 즉시 매칭되면 방을 반환, 아니면 None(대기 등록)."""
    now = datetime.now(UTC)
    key = (mode, source_lang, target_lang)
    _leave_previous(user_id)
    _prune(key, now)

    entries = _queue.get(key, [])
    for idx, (candidate_id, _joined_at) in enumerate(entries):
        if candidate_id == user_id:
            continue
        if await _recently_closed_with(db, user_id, candidate_id, source_lang, target_lang, mode):
            continue
        remaining = entries[:idx] + entries[idx + 1 :]
        if remaining:
            _queue[key] = remaining
        else:
            _queue.pop(key, None)
        _by_user.pop(candidate_id, None)
        room, _created = await chat_service.get_or_create_room(
            db, user_id, candidate_id, source_lang, target_lang, origin="match", mode=mode
        )
        return room

    entries.append((user_id, now))
    _queue[key] = entries
    _by_user[user_id] = key
    return None


def waiting(user_id: int) -> bool:
    key = _by_user.get(user_id)
    if key is None:
        return False
    _prune(key, datetime.now(UTC))
    return _by_user.get(user_id) == key


def cancel(user_id: int) -> None:
    _leave_previous(user_id)
