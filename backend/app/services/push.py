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
from app.models import LearningItem, PushSubscription, ReviewCard, ReviewLog, UserSettings
from app.services import retention, weekly_report
from app.services.visibility import (
    low_level_sentence_gate,
    queue_type_clause,
    visible_item_clause,
)

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
REMINDER_HOUR_KST = 20  # reminder_hour 미설정(설정 행 없음) 폴백
MIN_REMINDER_HOUR = 5  # 새벽 발송 금지 하한 — 설정 검증(api/study.py)과 동일


def enabled(settings: Settings) -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def _send_sync(subscription_info: dict, payload: dict, settings: Settings) -> None:
    webpush(
        subscription_info=subscription_info,
        data=json.dumps(payload, ensure_ascii=False),
        vapid_private_key=settings.vapid_private_key,
        vapid_claims={"sub": settings.vapid_subject},
    )


async def send_to(sub: PushSubscription, payload: dict, settings: Settings) -> str:
    """ "ok"=전달 성공, "gone"=만료 구독(404/410, 호출자가 행 삭제), "error"=일시 오류(유지).

    이전엔 일시 오류도 True 로 뭉개져 테스트 발송이 '보냈어요'라고 거짓 보고하고
    리마인더가 실패한 날을 발송 완료로 마킹해 재시도를 건너뛰었다 (2026-07-28)."""
    info = {
        "endpoint": sub.endpoint,
        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
    }
    try:
        await asyncio.to_thread(_send_sync, info, payload, settings)
        return "ok"
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (404, 410):
            return "gone"
        logger.warning("push send failed sub=%s status=%s", sub.id, status)
        return "error"


async def send_to_user(db: AsyncSession, user_id: int, payload: dict) -> bool:
    """유저의 모든 구독에 발송 — 하나라도 전달되면 True, 만료 구독은 삭제.

    게임 초대 등 즉시성 알림 공용. 커밋은 호출자 책임.
    """
    settings = get_settings()
    if not enabled(settings):
        return False
    subs = (
        (await db.execute(select(PushSubscription).where(PushSubscription.user_id == user_id)))
        .scalars()
        .all()
    )
    delivered = False
    for sub in subs:
        result = await send_to(sub, payload, settings)
        if result == "ok":
            delivered = True
        elif result == "gone":
            await db.delete(sub)
    await db.flush()
    return delivered


async def due_count(db: AsyncSession, user_id: int, now: datetime) -> int:
    """큐와 같은 출제 범위로 센다 (레벨 타입 + 길이 게이트) — 잠긴 카드만 있는
    사용자에게 알림을 보내면 세션이 비어 불일치 (2026-08-18 전수 점검)."""
    from app.models.item import ITEM_TYPE_LEVEL

    row = (
        await db.execute(
            select(UserSettings.levels_enabled, UserSettings.study_level).where(
                UserSettings.user_id == user_id
            )
        )
    ).one_or_none()
    # 설정 행 없는 유저 폴백 — 모델 기본(study_level=2, levels 1·2)과 일치
    levels = row.levels_enabled if row else [1, 2]
    study_level = row.study_level if row else 2
    types = [t for t, lv in ITEM_TYPE_LEVEL.items() if lv in (levels or [])]
    return (
        await db.execute(
            select(func.count(ReviewCard.id))
            .join(LearningItem, LearningItem.id == ReviewCard.item_id)
            .where(
                ReviewCard.user_id == user_id,
                ReviewCard.due_at <= now,
                ReviewCard.suspended.is_(False),
                visible_item_clause(user_id),
                queue_type_clause(types),
                *low_level_sentence_gate(study_level),
            )
        )
    ).scalar_one()


def reminder_payload(remaining: int) -> dict:
    """목표까지 남은 소량만 언급 — 밀린 전체 수는 위협적이라 싣지 않는다 (포기 방지 기획)."""
    return {
        "title": "ESL Lessonaza",
        "body": f"오늘 목표까지 {remaining}개 — 지금 하면 금방이에요",
        "url": "/study/session",
        "tag": "review-reminder",
    }


DEFAULT_DAILY_GOAL = 30  # user_settings 행 없는 유저 폴백 — 모델 기본과 일치


async def _goal_progress(db: AsyncSession, user_id: int, now: datetime) -> tuple[int, int]:
    """(오늘의 목표, 오늘 복습 수) — KST 자정 기준."""
    goal = (
        await db.execute(select(UserSettings.daily_goal).where(UserSettings.user_id == user_id))
    ).scalar_one_or_none() or DEFAULT_DAILY_GOAL
    local = now.astimezone(KST)
    day_start = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
    done = (
        await db.execute(
            select(func.count(ReviewLog.id)).where(
                ReviewLog.user_id == user_id, ReviewLog.reviewed_at >= day_start
            )
        )
    ).scalar_one()
    return goal, done


async def send_review_reminders(db: AsyncSession, now: datetime | None = None) -> int:
    """발송 수 반환. 커밋은 호출자 책임 (워커 루프/테스트 공용)."""
    settings = get_settings()
    if not enabled(settings):
        return 0
    now = now or datetime.now(UTC)
    local = now.astimezone(KST)
    # 시각 게이트는 사용자별(reminder_hour) — 전역 게이트는 새벽 하한만
    # (user-journey-motivation-2026-08.md P1 실행 의도: 사용자가 시간을 정한다)
    if local.hour < MIN_REMINDER_HOUR:
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
        hour = (
            await db.execute(
                select(UserSettings.reminder_hour).where(UserSettings.user_id == user_id)
            )
        ).scalar_one_or_none()
        if local.hour < (hour if hour is not None else REMINDER_HOUR_KST):
            continue  # 아직 이 사용자의 시각 전 — 마킹 없이 다음 루프에서 재평가
        due = await due_count(db, user_id, now)
        if due == 0:
            continue  # 마킹하지 않음 — 이후 due 가 생기면 같은 날에도 발송
        goal, done = await _goal_progress(db, user_id, now)
        if done >= goal:
            continue  # 오늘 목표를 이미 채움 — 달성감 보존, 알림 없음
        payload = reminder_payload(min(due, goal - done))
        for sub in user_subs:
            result = await send_to(sub, payload, settings)
            if result == "ok":
                sub.last_sent_on = today
                sent += 1
            elif result == "gone":
                await db.delete(sub)
            # "error" — 마킹하지 않고 유지, 다음 루프에서 재시도 (독스트링 계약)
    await db.flush()
    return sent


# ---------- 주간 성적표 (docs/specs/weekly-report.md) ----------

WEEKLY_REPORT_WEEKDAY = 0  # 월요일(KST) — 새 출발 효과, 한 주를 성적표로 연다


def weekly_report_payload(reviews: int, delta: int) -> dict:
    """절대치보다 델타 — 변화가 없으면 수치만 (성적표 카드와 같은 카피 규칙).

    성적표가 다루는 주가 '지난주'라 비교 대상은 '그 전주' — 화면 카피와 표현을 맞춘다.
    """
    trend = f", 그 전주보다 {delta:+d}" if delta else ""
    return {
        "title": "ESL Lessonaza",
        "body": f"지난주 성적표가 나왔어요 — 복습 {reviews}개{trend}",
        "url": "/study",
        "tag": "weekly-report",
    }


async def send_weekly_reports(db: AsyncSession, now: datetime | None = None) -> int:
    """월요일(KST) `reminder_hour` 이후 주 1회 발송. 발송 수 반환, 커밋은 호출자 책임.

    - dedup 은 대상 주 ISO 를 `user_settings.weekly_report_week` 에 기록 (책갈피
      주간 지급 가드와 같은 패턴). 리마인더의 기기별 `last_sent_on` 과 달리
      **사용자 단위** — 성적표는 기기가 아니라 사람에게 한 번인 사건이다.
    - 지난주 복습 0건이면 보내지 않는다 (빈 성적표는 이탈 유발) — 마킹도 하지
      않아, 뒤늦게 로그가 소급되면 같은 월요일 안에는 다시 평가된다.
    """
    settings = get_settings()
    if not enabled(settings):
        return 0
    now = now or datetime.now(UTC)
    local = now.astimezone(KST)
    if local.weekday() != WEEKLY_REPORT_WEEKDAY or local.hour < MIN_REMINDER_HOUR:
        return 0
    week = retention.iso_week(weekly_report.last_week_start(now))

    subs = (await db.execute(select(PushSubscription))).scalars().all()
    by_user: dict[int, list[PushSubscription]] = {}
    for sub in subs:
        by_user.setdefault(sub.user_id, []).append(sub)

    sent = 0
    for user_id, user_subs in by_user.items():
        user_settings = await db.get(UserSettings, user_id)
        if user_settings is None:
            user_settings = UserSettings(user_id=user_id)
            db.add(user_settings)
            await db.flush()
        if user_settings.weekly_report_week == week:
            continue
        if local.hour < user_settings.reminder_hour:
            continue  # 아직 이 사용자의 시각 전 — 마킹 없이 다음 루프에서 재평가
        reviews, prev_reviews = await weekly_report.review_counts(db, user_id, now)
        if reviews == 0:
            continue
        payload = weekly_report_payload(reviews, reviews - prev_reviews)
        delivered = False
        for sub in user_subs:
            result = await send_to(sub, payload, settings)
            if result == "ok":
                delivered = True
                sent += 1
            elif result == "gone":
                await db.delete(sub)
        if delivered:
            user_settings.weekly_report_week = week
    await db.flush()
    return sent
