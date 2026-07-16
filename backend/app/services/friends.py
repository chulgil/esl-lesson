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
