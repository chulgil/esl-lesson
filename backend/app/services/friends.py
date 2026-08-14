"""친구 관계 조회 — API/WS 공용 (docs/specs/study-spectate.md)."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.friend import Friendship


async def are_friends(db: AsyncSession, user_a: int, user_b: int) -> bool:
    """수락(accepted)된 친구 관계면 True — 방향 무관."""
    row = (
        await db.execute(
            select(Friendship.id).where(
                Friendship.status == "accepted",
                or_(
                    (Friendship.requester_id == user_a) & (Friendship.addressee_id == user_b),
                    (Friendship.requester_id == user_b) & (Friendship.addressee_id == user_a),
                ),
            )
        )
    ).scalar_one_or_none()
    return row is not None


async def friend_ids_of(db: AsyncSession, user_id: int) -> list[int]:
    """수락(accepted)된 친구의 user_id 목록 — 학습 중 알림 등 프레즌스 릴레이 대상 조회
    (docs/specs/study-spectate.md §진입 경로 재설계)."""
    rows = (
        await db.execute(
            select(Friendship).where(
                Friendship.status == "accepted",
                or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
            )
        )
    ).scalars()
    return [r.addressee_id if r.requester_id == user_id else r.requester_id for r in rows]
