"""주간 성적표 — 지난주 vs 그 전주 델타 + 월요일 푸시 (docs/specs/weekly-report.md)."""

from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select

from app.models import (
    Content,
    ContentRoutineProgress,
    ListenCheck,
    ReviewCard,
    ReviewLog,
    UserSettings,
)
from app.services import push, retention, weekly_report
from tests.test_push import SUB_BODY
from tests.test_study import login, seed_items

# 기준 시각: 성적표를 보는 월요일 아침(KST) — last_week_start 로부터 역산해
# "이번 월요일"을 만들면 요일 산술을 손으로 하지 않는다.
NOW = datetime(2026, 8, 7, 3, 0, tzinfo=UTC)  # 임의 고정점 (금요일 낮 KST)
LAST_MONDAY = weekly_report.last_week_start(NOW)  # 지난주 월요일 (date, KST)
THIS_MONDAY = LAST_MONDAY + timedelta(days=7)


def _kst_utc(day, hour: int) -> datetime:
    """KST 날짜+시각 → UTC — 주 중간 시각만 써서 경계 quirk 을 피한다."""
    return datetime.combine(day, time(hour), tzinfo=weekly_report.KST).astimezone(UTC)


def _monday(hour: int, minute: int = 0) -> datetime:
    """이번 월요일(성적표 발송일) hour:minute KST → UTC."""
    return _kst_utc(THIS_MONDAY, hour).replace(minute=minute)


async def _card(db, user_id: int) -> ReviewCard:
    item = (await seed_items(db, count=1))[0]
    card = ReviewCard(user_id=user_id, item_id=item.id, state="review", due_at=NOW)
    db.add(card)
    await db.flush()
    return card


async def _log(db, user_id: int, card_id: int, at: datetime, correct=True, days=None):
    db.add(
        ReviewLog(
            user_id=user_id,
            card_id=card_id,
            rating=3 if correct else 1,
            correct=correct,
            quiz_mode="choice_kr",
            state_before="review",
            scheduled_days=days,
            reviewed_at=at,
        )
    )
    await db.flush()


async def test_build_deltas_between_weeks(client, db_session):
    """지난주 3복습(2정답) vs 전주 1복습(1정답) — 전 필드 델타 동반."""
    user = await login(client, db_session)
    card = await _card(db_session, user.id)
    mid = LAST_MONDAY + timedelta(days=2)  # 지난주 수요일
    prev_mid = mid - timedelta(days=7)

    await _log(db_session, user.id, card.id, _kst_utc(prev_mid, 12), correct=True)
    for i, ok in enumerate([True, True, False]):
        await _log(db_session, user.id, card.id, _kst_utc(mid, 10 + i), correct=ok)
    # 장기 기억 도달: 간격 7일+ 첫 로그가 지난주에 찍힘
    await _log(db_session, user.id, card.id, _kst_utc(mid, 14), correct=True, days=8.0)

    # login() 이 UserSettings 를 이미 만들어 뒀다 — 새로 만들면 PK 충돌
    settings = await db_session.get(UserSettings, user.id)

    report = await weekly_report.build(db_session, user.id, settings, now=NOW)
    assert report["week_start"] == LAST_MONDAY.isoformat()
    assert report["reviews"] == 4 and report["reviews_delta"] == 3
    assert report["accuracy"] == 75 and report["accuracy_delta"] == 75 - 100
    assert report["long_term_new"] == 1 and report["long_term_new_delta"] == 1
    assert report["has_data"] is True


async def test_build_routine_and_listen_delta(client, db_session):
    """루틴 단계 수 + 재청취 전후 평균 델타 — stage 2 가 지난주에 있어야 잡힌다."""
    user = await login(client, db_session)
    await seed_items(db_session, count=1)  # 콘텐츠(공용) 생성 — 루틴·재청취의 대상
    content = (await db_session.execute(select(Content).limit(1))).scalar_one()
    mid_utc = _kst_utc(LAST_MONDAY + timedelta(days=3), 12)

    for step in (1, 2):
        db_session.add(
            ContentRoutineProgress(
                user_id=user.id, content_id=content.id, step=step, created_at=mid_utc
            )
        )
    db_session.add(
        ListenCheck(
            user_id=user.id,
            content_id=content.id,
            stage=1,
            score=2,
            created_at=mid_utc - timedelta(days=8),
        )
    )
    db_session.add(
        ListenCheck(user_id=user.id, content_id=content.id, stage=2, score=4, created_at=mid_utc)
    )
    await db_session.flush()

    settings = await db_session.get(UserSettings, user.id)

    report = await weekly_report.build(db_session, user.id, settings, now=NOW)
    assert report["routine_steps"] == 2 and report["routine_steps_delta"] == 2
    assert report["listen"] == {"delta": 2.0, "contents": 1}
    assert report["has_data"] is False  # 복습 로그는 없다 — 게이트는 복습 기준


async def test_endpoint_requires_auth_and_returns_report(client, db_session):
    assert (await client.get("/api/study/weekly-report")).status_code == 401

    await login(client, db_session)
    res = await client.get("/api/study/weekly-report")
    assert res.status_code == 200
    body = res.json()
    assert body["has_data"] is False and body["accuracy"] is None
    assert body["listen"] is None


async def test_weekly_push_monday_once_per_user(client, db_session, vapid_keys, monkeypatch):
    """월요일 reminder_hour 이후 1회 — 사용자 단위 dedup (weekly_report_week)."""
    user = await login(client, db_session)
    card = await _card(db_session, user.id)
    mid = _kst_utc(LAST_MONDAY + timedelta(days=2), 12)
    await _log(db_session, user.id, card.id, mid)
    await _log(db_session, user.id, card.id, mid + timedelta(hours=1))
    await client.post("/api/push/subscriptions", json=SUB_BODY)

    sent: list[dict] = []

    async def fake_send(sub, payload, settings):
        sent.append(payload)
        return "ok"

    monkeypatch.setattr(push, "send_to", fake_send)

    # 월요일이지만 사용자 시각(기본 20시) 전 — 발송·마킹 없음
    assert await push.send_weekly_reports(db_session, now=_monday(9)) == 0

    assert await push.send_weekly_reports(db_session, now=_monday(20, 30)) == 1
    assert sent[0]["tag"] == "weekly-report" and sent[0]["url"] == "/study"
    assert "지난주 성적표" in sent[0]["body"] and "+2" in sent[0]["body"]

    # 같은 월요일 재평가 — dedup
    assert await push.send_weekly_reports(db_session, now=_monday(21)) == 0
    row = await db_session.get(UserSettings, user.id)
    assert row.weekly_report_week == retention.iso_week(weekly_report.last_week_start(_monday(21)))


async def test_weekly_push_skips_non_monday_and_empty_week(
    client, db_session, vapid_keys, monkeypatch
):
    """월요일 아님 → 평가 안 함. 지난주 복습 0 → 발송·마킹 모두 안 함."""
    user = await login(client, db_session)
    await client.post("/api/push/subscriptions", json=SUB_BODY)

    async def fake_send(sub, payload, settings):
        return "ok"

    monkeypatch.setattr(push, "send_to", fake_send)

    tuesday = _monday(20) + timedelta(days=1)
    assert await push.send_weekly_reports(db_session, now=tuesday) == 0

    # 월요일 + 시각 통과지만 지난주 복습 0 — 빈 성적표는 보내지 않는다
    assert await push.send_weekly_reports(db_session, now=_monday(20, 30)) == 0
    row = await db_session.get(UserSettings, user.id)
    assert row is None or row.weekly_report_week is None
