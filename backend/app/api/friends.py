"""친구 API — 요청/수락/목록 + 학습 중(관전 가능) 표시 (docs/specs/study-spectate.md).

관전 코드는 수락된 친구에게만 노출되며, 실제 스트림 시청은 학습자가
관전 요청을 다시 수락해야 시작된다 (2중 동의).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import User
from app.models.friend import Friendship
from app.services.game.dictation import dictator
from app.services.game.invites import invite_hub
from app.services.game.manager import manager
from app.services.game.quiz_royale import royale
from app.services.game.scramble import scrambler
from app.services.game.spectate import spectate_hub
from app.services.game.typing_race import racer
from app.services.notifications import notify

router = APIRouter(prefix="/friends", tags=["friends"])


def _in_game(user_id: int) -> bool:
    """5개 게임 허브 중 한 곳에라도 활성 세션이 있는가 — by_user 는 종료·이탈 시
    각 허브가 정리하므로 존재 자체가 진행 중 신호다 (친구 목록 '게임 중' 표기)."""
    return any(user_id in hub.by_user for hub in (manager, royale, racer, scrambler, dictator))


class FriendRequestBody(BaseModel):
    # 이메일 검증 라이브러리 불필요 — DB 정확 일치 조회만 함
    email: str = Field(min_length=3, max_length=254)


@router.post("/requests")
async def send_request(
    body: FriendRequestBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    target = (
        await db.execute(select(User).where(User.email == body.email.lower()))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
    if target.id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_friend_self")
    existing = (
        await db.execute(
            select(Friendship).where(
                or_(
                    (Friendship.requester_id == user.id) & (Friendship.addressee_id == target.id),
                    (Friendship.requester_id == target.id) & (Friendship.addressee_id == user.id),
                )
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_requested_or_friends")
    row = Friendship(requester_id=user.id, addressee_id=target.id)
    db.add(row)
    await db.flush()  # 알림 payload 에 요청 id 를 담기 위해 선확보
    await notify(
        db, target.id, "friend_request", {"from_name": user.nickname, "request_id": row.id}
    )
    await db.commit()
    return {"id": row.id, "status": row.status}


@router.post("/requests/{request_id}/accept")
async def accept_request(
    request_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = await db.get(Friendship, request_id)
    if row is None or row.addressee_id != user.id or row.status != "pending":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "request_not_found")
    row.status = "accepted"
    # 수락 알림은 요청자에게 — 닉네임은 수락 시점 스냅샷
    await notify(db, row.requester_id, "friend_accepted", {"from_name": user.nickname})
    await db.commit()
    return {"id": row.id, "status": row.status}


@router.delete("/requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def decline_request(
    request_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """거절(받은 요청) 또는 취소(보낸 요청)."""
    row = await db.get(Friendship, request_id)
    if row is None or user.id not in (row.requester_id, row.addressee_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "request_not_found")
    await db.delete(row)
    await db.commit()


@router.delete("/{friend_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friend(
    friend_user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    row = (
        await db.execute(
            select(Friendship).where(
                Friendship.status == "accepted",
                or_(
                    (Friendship.requester_id == user.id)
                    & (Friendship.addressee_id == friend_user_id),
                    (Friendship.requester_id == friend_user_id)
                    & (Friendship.addressee_id == user.id),
                ),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "friend_not_found")
    await db.delete(row)
    await db.commit()


@router.get("")
async def list_friends(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    rows = (
        (
            await db.execute(
                select(Friendship).where(
                    or_(
                        Friendship.requester_id == user.id,
                        Friendship.addressee_id == user.id,
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    other_ids = {r.addressee_id if r.requester_id == user.id else r.requester_id for r in rows}
    users = {
        u.id: u
        for u in ((await db.execute(select(User).where(User.id.in_(other_ids or {0})))).scalars())
    }

    friends, incoming, outgoing = [], [], []
    for r in rows:
        other = users.get(r.addressee_id if r.requester_id == user.id else r.requester_id)
        if other is None:
            continue
        if r.status == "accepted":
            code = spectate_hub.by_host.get(other.id)
            friends.append(
                {
                    "user_id": other.id,
                    "name": other.nickname,
                    "avatar_url": other.avatar_url,
                    "studying": code is not None,
                    "watch_code": code,
                    "online": invite_hub.online(other.id),
                    "gaming": _in_game(other.id),
                }
            )
        elif r.addressee_id == user.id:
            incoming.append({"id": r.id, "name": other.nickname})
        else:
            outgoing.append({"id": r.id, "name": other.nickname})
    return {"friends": friends, "incoming": incoming, "outgoing": outgoing}
