"""웹 푸시 발송 — 복습 리마인더 (docs/specs/push-reminder.md).

- 매일 REMINDER_HOUR_KST 이후, 밀린 복습이 있는 구독자에게 하루 1회 발송
- 404/410(만료 구독)은 행 삭제, 일시 오류는 유지 후 다음 루프에서 재시도
"""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta, timezone

from pywebpush import WebPushException, webpush
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models import LearningItem, PushSubscription, ReviewCard
from app.services.visibility import visible_item_clause

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
REMINDER_HOUR_KST = 20


def enabled(settings: Settings) -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def _send_sync(subscription_info: dict, payload: dict, settings: Settings) -> None:
    webpush(
        subscription_info=subscription_info,
        data=json.dumps(payload, ensure_ascii=False),
        vapid_private_key=settings.vapid_private_key,
        vapid_claims={"sub": settings.vapid_subject},
    )


async def send_to(sub: PushSubscription, payload: dict, settings: Settings) -> bool:
    """False = 구독이 더 이상 유효하지 않음(404/410) — 호출자가 행을 삭제한다."""
    info = {
        "endpoint": sub.endpoint,
        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
    }
    try:
        await asyncio.to_thread(_send_sync, info, payload, settings)
        return True
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (404, 410):
            return False
        logger.warning("push send failed sub=%s status=%s", sub.id, status)
        return True


async def due_count(db: AsyncSession, user_id: int, now: datetime) -> int:
    return (
        await db.execute(
            select(func.count(ReviewCard.id))
            .join(LearningItem, LearningItem.id == ReviewCard.item_id)
            .where(
                ReviewCard.user_id == user_id,
                ReviewCard.due_at <= now,
                ReviewCard.suspended.is_(False),
                visible_item_clause(user_id),
            )
        )
    ).scalar_one()


def reminder_payload(due: int) -> dict:
    return {
        "title": "ESL Lessonaza",
        "body": f"복습 {due}개가 기다려요 — 잊기 전에 다시 만나요",
        "url": "/study/session",
        "tag": "review-reminder",
    }


async def send_review_reminders(db: AsyncSession, now: datetime | None = None) -> int:
    """발송 수 반환. 커밋은 호출자 책임 (워커 루프/테스트 공용)."""
    settings = get_settings()
    if not enabled(settings):
        return 0
    now = now or datetime.now(UTC)
    local = now.astimezone(KST)
    if local.hour < REMINDER_HOUR_KST:
        return 0
    today = local.date()

    subs = (
        (
            await db.execute(
                select(PushSubscription).where(
                    or_(
                        PushSubscription.last_sent_on.is_(None),
                        PushSubscription.last_sent_on < today,
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    by_user: dict[int, list[PushSubscription]] = {}
    for sub in subs:
        by_user.setdefault(sub.user_id, []).append(sub)

    sent = 0
    for user_id, user_subs in by_user.items():
        due = await due_count(db, user_id, now)
        if due == 0:
            continue  # 마킹하지 않음 — 이후 due 가 생기면 같은 날에도 발송
        payload = reminder_payload(due)
        for sub in user_subs:
            if await send_to(sub, payload, settings):
                sub.last_sent_on = today
                sent += 1
            else:
                await db.delete(sub)
    await db.flush()
    return sent
