"""함께 목표 — 친구 대화방 공유 체크리스트 + 주간 달성표 (docs/specs/shared-goals.md).

kind="check" 행은 자유 체크리스트(대화당 최대 20개), kind="weekly_reviews" 행은
대화당 1개뿐인 주간 목표치 보관용 — 진행도 자체는 저장하지 않고 ReviewLog 를
매 조회마다 집계한다(daily_loop 리더보드와 동일 원칙: 집계 테이블 없이 로그에서 파생).
"""

from datetime import UTC, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, ReviewLog, SharedGoal, User
from app.services import chat as chat_service

KST = timezone(timedelta(hours=9))

CHECK_MAX = 20
DEFAULT_WEEKLY_TARGET = 300
WEEKLY_TARGET_MIN = 10
WEEKLY_TARGET_MAX = 100_000


def kst_week_start(now: datetime) -> datetime:
    """이번 주(KST 월요일 00시) 시작 — study.kst_day_start 를 주 단위로 확장."""
    local = now.astimezone(KST)
    monday = local - timedelta(days=local.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def other_participant(conv: Conversation, user_id: int) -> int:
    return conv.user_hi_id if conv.user_lo_id == user_id else conv.user_lo_id


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
    """친구 해제 후에는 조회만 남는다 — 변경은 403 (chat 전송 경로와 동일 규칙)."""
    if not await chat_service.are_friends(db, user_id, other_participant(conv, user_id)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_friends")


async def _goal_or_404(db: AsyncSession, goal_id: int) -> SharedGoal:
    goal = await db.get(SharedGoal, goal_id)
    if goal is None or goal.kind != "check":
        # weekly_reviews 행은 이 경로로 다루지 않는다 — id 로 우연히 맞아도 비노출
        raise HTTPException(status.HTTP_404_NOT_FOUND, "goal_not_found")
    return goal


async def _require_goal_participant(
    db: AsyncSession, goal: SharedGoal, user_id: int
) -> Conversation:
    conv = await db.get(Conversation, goal.conversation_id)
    if conv is None or user_id not in (conv.user_lo_id, conv.user_hi_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_participant")
    return conv


async def _nickname_map(db: AsyncSession, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = (await db.execute(select(User.id, User.nickname).where(User.id.in_(user_ids)))).all()
    return dict(rows)


def _check_dict(goal: SharedGoal, names: dict[int, str]) -> dict:
    return {
        "id": goal.id,
        "text": goal.text,
        "done": goal.done,
        "done_by_name": names.get(goal.done_by) if goal.done_by else None,
        "created_by_name": names.get(goal.created_by) if goal.created_by else None,
    }


async def _list_checks(db: AsyncSession, conv_id: int) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(SharedGoal)
                .where(SharedGoal.conversation_id == conv_id, SharedGoal.kind == "check")
                .order_by(SharedGoal.id)
            )
        )
        .scalars()
        .all()
    )
    ids = {uid for g in rows for uid in (g.done_by, g.created_by) if uid is not None}
    names = await _nickname_map(db, ids)
    return [_check_dict(g, names) for g in rows]


async def _weekly_row(db: AsyncSession, conv_id: int) -> SharedGoal | None:
    return (
        await db.execute(
            select(SharedGoal).where(
                SharedGoal.conversation_id == conv_id, SharedGoal.kind == "weekly_reviews"
            )
        )
    ).scalar_one_or_none()


async def _weekly_counts(db: AsyncSession, conv: Conversation, now: datetime) -> dict[int, int]:
    week_start = kst_week_start(now)
    rows = (
        await db.execute(
            select(ReviewLog.user_id, func.count(ReviewLog.id))
            .where(
                ReviewLog.user_id.in_((conv.user_lo_id, conv.user_hi_id)),
                ReviewLog.reviewed_at >= week_start,
            )
            .group_by(ReviewLog.user_id)
        )
    ).all()
    return dict(rows)


async def _weekly_dict(db: AsyncSession, conv: Conversation, user_id: int) -> dict:
    row = await _weekly_row(db, conv.id)
    target = row.target_value if row and row.target_value else DEFAULT_WEEKLY_TARGET
    counts = await _weekly_counts(db, conv, datetime.now(UTC))
    return {
        "target": target,
        "mine": counts.get(user_id, 0),
        "theirs": counts.get(other_participant(conv, user_id), 0),
    }


async def get_view(db: AsyncSession, user_id: int, other_id: int) -> dict:
    """GET /with/{other_id}/goals — 대화가 없으면 친구 검증 후 빈 응답.

    weekly_configured: 주간 목표를 명시 설정한 행이 있는가 — 보드 노출 판정용
    (2026-08-13 기본 숨김 전환: 내용이 있을 때만 바 노출)."""
    conv = await chat_service.get_conversation(db, user_id, other_id)
    if conv is None:
        await chat_service.require_friend(db, user_id, other_id)
        return {
            "items": [],
            "weekly": {"target": DEFAULT_WEEKLY_TARGET, "mine": 0, "theirs": 0},
            "weekly_configured": False,
        }
    return {
        "items": await _list_checks(db, conv.id),
        "weekly": await _weekly_dict(db, conv, user_id),
        "weekly_configured": await _weekly_row(db, conv.id) is not None,
    }


async def clear_board(db: AsyncSession, user_id: int, other_id: int) -> Conversation | None:
    """보드 내리기 — 체크리스트+주간 목표 행 전부 삭제 (멱등).

    같은 테이블의 공지(kind="notice") 행은 별도 표면이라 건드리지 않는다
    (docs/specs/chat-notice.md). 친구 해제 후에는 다른 변경과 동일하게 403."""
    conv = await chat_service.get_conversation(db, user_id, other_id)
    if conv is None:
        await chat_service.require_friend(db, user_id, other_id)
        return None
    await _require_mutable(db, conv, user_id)
    await db.execute(
        delete(SharedGoal).where(
            SharedGoal.conversation_id == conv.id,
            SharedGoal.kind.in_(("check", "weekly_reviews")),
        )
    )
    await db.commit()
    return conv


async def add_check(
    db: AsyncSession, user_id: int, other_id: int, text: str
) -> tuple[dict, Conversation]:
    text = text.strip()
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_text")
    conv = await _get_or_create_conversation(db, user_id, other_id)
    await _require_mutable(db, conv, user_id)
    count = (
        await db.execute(
            select(func.count(SharedGoal.id)).where(
                SharedGoal.conversation_id == conv.id, SharedGoal.kind == "check"
            )
        )
    ).scalar_one()
    if count >= CHECK_MAX:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "goals_full")
    goal = SharedGoal(conversation_id=conv.id, kind="check", text=text, created_by=user_id)
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return _check_dict(goal, await _nickname_map(db, {user_id})), conv


async def patch_check(
    db: AsyncSession,
    user_id: int,
    goal_id: int,
    text: str | None,
    done: bool | None,
) -> tuple[dict, Conversation]:
    """text/done 만 다룬다 — target_value 는 별도 경로(weekly)로 분리
    (goal_id PATCH 는 check 전용)."""
    goal = await _goal_or_404(db, goal_id)
    conv = await _require_goal_participant(db, goal, user_id)
    await _require_mutable(db, conv, user_id)
    if text is not None:
        text = text.strip()
        if not text:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_text")
        goal.text = text
    if done is not None:
        goal.done = done
        goal.done_by = user_id if done else None
    await db.commit()
    await db.refresh(goal)
    ids = {uid for uid in (goal.done_by, goal.created_by) if uid is not None}
    return _check_dict(goal, await _nickname_map(db, ids)), conv


async def delete_check(db: AsyncSession, user_id: int, goal_id: int) -> Conversation:
    goal = await _goal_or_404(db, goal_id)
    conv = await _require_goal_participant(db, goal, user_id)
    await _require_mutable(db, conv, user_id)
    await db.delete(goal)
    await db.commit()
    return conv


async def set_weekly_target(
    db: AsyncSession, user_id: int, other_id: int, target_value: int
) -> tuple[dict, Conversation]:
    if not (WEEKLY_TARGET_MIN <= target_value <= WEEKLY_TARGET_MAX):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_target")
    conv = await _get_or_create_conversation(db, user_id, other_id)
    await _require_mutable(db, conv, user_id)
    row = await _weekly_row(db, conv.id)
    if row is None:
        row = SharedGoal(conversation_id=conv.id, kind="weekly_reviews", created_by=user_id)
        db.add(row)
    row.target_value = target_value
    await db.commit()
    return await _weekly_dict(db, conv, user_id), conv
