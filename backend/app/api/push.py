"""웹 푸시 구독 API (docs/specs/push-reminder.md)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_current_user
from app.models import PushSubscription, User
from app.services import push

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/config")
async def push_config() -> dict:
    """VAPID 공개키 — 비밀 아님, 비로그인 허용 (구독 생성 자체는 로그인 필요)."""
    settings = get_settings()
    return {"enabled": push.enabled(settings), "public_key": settings.vapid_public_key}


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=300)
    auth: str = Field(min_length=1, max_length=300)


class SubscribeBody(BaseModel):
    endpoint: str = Field(min_length=1, max_length=1000)
    keys: SubscriptionKeys

    @field_validator("endpoint")
    @classmethod
    def https_only(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("endpoint must be https")
        return v


@router.post("/subscriptions")
async def subscribe(
    body: SubscribeBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    existing = (
        await db.execute(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint))
    ).scalar_one_or_none()
    if existing is not None:
        # 같은 브라우저 재구독/프로필 전환 — 현재 유저로 갱신
        existing.user_id = user.id
        existing.p256dh = body.keys.p256dh
        existing.auth = body.keys.auth
    else:
        db.add(
            PushSubscription(
                user_id=user.id,
                endpoint=body.endpoint,
                p256dh=body.keys.p256dh,
                auth=body.keys.auth,
            )
        )
    try:
        await db.commit()
    except IntegrityError:
        # 동시 구독 경합 (endpoint UNIQUE) — 먼저 저장된 행을 현재 값으로 갱신
        await db.rollback()
        winner = (
            await db.execute(
                select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
            )
        ).scalar_one()
        winner.user_id = user.id
        winner.p256dh = body.keys.p256dh
        winner.auth = body.keys.auth
        await db.commit()
    return {"saved": True}


class UnsubscribeBody(BaseModel):
    endpoint: str = Field(min_length=1, max_length=1000)


@router.delete("/subscriptions")
async def unsubscribe(
    body: UnsubscribeBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    await db.execute(
        PushSubscription.__table__.delete().where(
            PushSubscription.endpoint == body.endpoint,
            PushSubscription.user_id == user.id,
        )
    )
    await db.commit()
    return {"deleted": True}


@router.post("/test")
async def send_test(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """설정 화면 '테스트 알림' — 내 기기 전체로 즉시 발송."""
    settings = get_settings()
    subs = (
        (await db.execute(select(PushSubscription).where(PushSubscription.user_id == user.id)))
        .scalars()
        .all()
    )
    payload = {
        "title": "ESL Lessonaza",
        "body": "알림이 잘 도착했어요! 복습 리마인더가 이렇게 와요.",
        "url": "/",
        "tag": "push-test",
    }
    sent = 0
    for sub in subs:
        if await push.send_to(sub, payload, settings):
            sent += 1
        else:
            await db.delete(sub)
    await db.commit()
    return {"sent": sent}
