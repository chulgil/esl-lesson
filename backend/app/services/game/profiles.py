"""플레이어 배지 — 마스코트 + 대표 업적 칭호 (docs/specs/mascot-shop.md 플레이어 배지).

대전·대기실·리더보드에서 상대의 마스코트와 칭호를 보여줘 경쟁 동기를 만든다
(2026-08-11 기획). 조회 실패가 게임 진행을 막지 않도록 호출부는 safe_* 를 쓴다.
"""

import logging

from sqlalchemy import select

from app.core.db import get_session_factory
from app.models.user import UserSettings
from app.services.achievements import DEFINITIONS

logger = logging.getLogger(__name__)

# 업적 키 → 칭호(제목) — 대표 업적 검증·표시의 단일 근거
ACHIEVEMENT_TITLES: dict[str, str] = {key: title for key, title, *_ in DEFINITIONS}


async def player_badges(user_ids: list[int | None], db=None) -> dict[int, dict]:
    """{user_id: {"mascot": key|None, "title": 칭호|None}} — 봇(None)·미설정은 제외.

    db 를 받으면 그 세션으로 조회한다 — HTTP 라우트는 요청 세션을 넘겨야
    테스트 오버라이드(get_db)가 적용된다. WS 브로드캐스트처럼 세션이 없는
    곳만 자체 세션을 연다.
    """
    ids = [i for i in set(user_ids) if i is not None]
    if not ids:
        return {}
    query = select(
        UserSettings.user_id,
        UserSettings.mascot_key,
        UserSettings.featured_achievement,
    ).where(UserSettings.user_id.in_(ids))
    if db is not None:
        rows = (await db.execute(query)).all()
    else:
        async with get_session_factory()() as session:
            rows = (await session.execute(query)).all()
    return {
        user_id: {"mascot": mascot, "title": ACHIEVEMENT_TITLES.get(featured or "")}
        for user_id, mascot, featured in rows
    }


async def safe_player_badges(user_ids: list[int | None], db=None) -> dict[int, dict]:
    """배지 조회 실패는 게임을 막지 않는다 — 빈 dict 폴백."""
    try:
        return await player_badges(user_ids, db=db)
    except Exception:
        logger.exception("player badges lookup failed ids=%s", user_ids)
        return {}
