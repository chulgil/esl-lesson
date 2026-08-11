"""리텐션 팩 — 책갈피(스트릭 보호) + 오늘의 미션 (docs/proposal/retention-plan.md)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import ReviewCard, ReviewLog, StreakSaverUse, UserSettings
from app.services import retention
from tests.test_study import login, seed_items

KST = retention.KST


async def _log_on(db, user_id: int, days_ago: int, count: int = 1) -> None:
    """days_ago 일 전(KST) 정오에 복습 로그 count 개 생성."""
    items = await seed_items(db, count=1)
    card = ReviewCard(
        user_id=user_id, item_id=items[0].id, state="review", due_at=datetime.now(UTC)
    )
    db.add(card)
    await db.flush()
    noon_kst = datetime.now(UTC).astimezone(KST).replace(hour=12, minute=0, second=0, microsecond=0)
    when = (noon_kst - timedelta(days=days_ago)).astimezone(UTC)
    for _ in range(count):
        db.add(
            ReviewLog(
                card_id=card.id,
                user_id=user_id,
                rating=3,
                correct=True,
                quiz_mode="choice_en2ko",
                state_before="review",
                reviewed_at=when,
            )
        )
    await db.flush()


async def _settings(db, user_id: int) -> UserSettings:
    return (
        await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    ).scalar_one()


# ---------- 책갈피 (스트릭 보호) ----------


async def test_saver_awarded_once_per_week_on_goal(client, db_session):
    """오늘 목표 달성 → 책갈피 1개 지급, 같은 주 재달성엔 중복 지급 없음."""
    user = await login(client, db_session)
    await _log_on(db_session, user.id, days_ago=0, count=30)  # 기본 목표 30 달성 (2026-08-05 상향)

    res = await client.get("/api/study/stats")
    assert res.json()["streak_savers"] == 1

    res = await client.get("/api/study/stats")  # 같은 주 재호출
    assert res.json()["streak_savers"] == 1


async def test_saver_not_awarded_below_goal(client, db_session):
    user = await login(client, db_session)
    await _log_on(db_session, user.id, days_ago=0, count=5)

    res = await client.get("/api/study/stats")
    assert res.json()["streak_savers"] == 0


async def test_saver_cap_at_two(client, db_session):
    user = await login(client, db_session)
    settings = await _settings(db_session, user.id)
    settings.streak_savers = 2
    settings.saver_award_week = None  # 지급 가드 해제 상태여도
    await db_session.flush()
    await _log_on(db_session, user.id, days_ago=0, count=30)

    res = await client.get("/api/study/stats")
    assert res.json()["streak_savers"] == 2  # 상한 유지


async def test_saver_consumed_to_bridge_single_gap(client, db_session):
    """그저께까지 학습, 어제 공백, 오늘 학습 → 책갈피 1개 자동 소모로 스트릭 유지."""
    user = await login(client, db_session)
    settings = await _settings(db_session, user.id)
    settings.streak_savers = 1
    await db_session.flush()

    await _log_on(db_session, user.id, days_ago=3)
    await _log_on(db_session, user.id, days_ago=2)
    await _log_on(db_session, user.id, days_ago=0)  # 어제(1)는 공백

    res = await client.get("/api/study/stats")
    body = res.json()
    # 책갈피 날은 +0: 학습일 3일(그저께·3일전·오늘)만 카운트, 리셋은 방지
    assert body["streak_days"] == 3
    assert body["streak_savers"] == 0
    yesterday = (datetime.now(UTC).astimezone(KST).date() - timedelta(days=1)).isoformat()
    assert yesterday in body["streak_saved_days"]

    uses = (
        (await db_session.execute(select(StreakSaverUse).where(StreakSaverUse.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(uses) == 1


async def test_saver_not_consumed_when_gap_too_wide(client, db_session):
    """공백 2일인데 책갈피 1개뿐 → 소모하지 않고 스트릭은 오늘부터 새로 센다 (낭비 방지)."""
    user = await login(client, db_session)
    settings = await _settings(db_session, user.id)
    settings.streak_savers = 1
    await db_session.flush()

    await _log_on(db_session, user.id, days_ago=3)
    await _log_on(db_session, user.id, days_ago=0)  # 1·2일 전 공백

    res = await client.get("/api/study/stats")
    body = res.json()
    assert body["streak_days"] == 1  # 오늘만
    assert body["streak_savers"] == 1  # 소모 안 함
    assert body["streak_saved_days"] == []


async def test_saver_bridges_two_day_gap_with_two_savers(client, db_session):
    user = await login(client, db_session)
    settings = await _settings(db_session, user.id)
    settings.streak_savers = 2
    await db_session.flush()

    await _log_on(db_session, user.id, days_ago=3)
    await _log_on(db_session, user.id, days_ago=0)

    res = await client.get("/api/study/stats")
    body = res.json()
    assert body["streak_days"] == 2  # 3일 전 + 오늘
    assert body["streak_savers"] == 0
    assert len(body["streak_saved_days"]) == 2


async def test_streak_window_matches_stats_daily_grid(client, db_session):
    """61일+ 연속 학습 — study.py stats 의 400일 잔디 창과 동일 창을 써야 끊기지 않는다.

    STREAK_WINDOW_DAYS 가 stats.daily 조회 창(400일)보다 좁으면(구 값 60일)
    그 경계에서 스트릭이 강제로 절단된다 (2026-08-03 잔디 확장 시 미동기화).
    """
    user = await login(client, db_session)
    for days_ago in range(65):  # 오늘 포함 65일 연속
        await _log_on(db_session, user.id, days_ago=days_ago)

    res = await client.get("/api/study/stats")
    assert res.json()["streak_days"] == 65


async def test_saver_not_consumed_for_today_not_yet_studied(client, db_session):
    """오늘 아직 안 했을 뿐이면 소모하지 않는다 — 어제까지 이어진 스트릭만 보여준다."""
    user = await login(client, db_session)
    settings = await _settings(db_session, user.id)
    settings.streak_savers = 2
    await db_session.flush()

    await _log_on(db_session, user.id, days_ago=1)
    await _log_on(db_session, user.id, days_ago=2)

    res = await client.get("/api/study/stats")
    body = res.json()
    assert body["streak_days"] == 2
    assert body["streak_savers"] == 2  # 소모 없음
    assert body["streak_saved_days"] == []


# ---------- 오늘의 미션 ----------


async def test_quests_deterministic_and_core_included(client, db_session):
    """미션 3종 — 복습 코어 1개 고정 + 날짜 결정적 2개 (재호출에도 동일)."""
    await login(client, db_session)

    res = await client.get("/api/study/quests")
    assert res.status_code == 200
    body = res.json()
    keys = [q["key"] for q in body["items"]]
    assert len(keys) == 3
    assert retention.CORE_QUEST in keys

    res2 = await client.get("/api/study/quests")
    assert [q["key"] for q in res2.json()["items"]] == keys


async def test_quest_progress_and_completion_ledger(client, db_session):
    """복습 미션 진행 → 완료 시 원장 적립(멱등) + stats XP 에 보너스 합산."""
    user = await login(client, db_session)

    base_xp = (await client.get("/api/study/stats")).json()["xp"]

    await _log_on(db_session, user.id, days_ago=0, count=10)  # review_10 달성
    res = await client.get("/api/study/quests")
    quest = next(q for q in res.json()["items"] if q["key"] == retention.CORE_QUEST)
    assert quest["done"] is True
    assert quest["current"] >= quest["target"]

    # 원장 멱등 — 재호출에도 1행
    await client.get("/api/study/quests")
    from app.models import QuestCompletion

    rows = (
        (
            await db_session.execute(
                select(QuestCompletion).where(
                    QuestCompletion.user_id == user.id,
                    QuestCompletion.quest_key == retention.CORE_QUEST,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1

    # stats XP = 복습 10개(100) + 오늘 완료된 모든 미션 보너스 합
    # (날짜·유저별로 picked 되는 나머지 2개 미션 중 하나가 같은 복습 액션으로
    #  같이 달성될 수 있어 CORE_QUEST 한 건만으로 계산하면 날짜에 따라 깨진다)
    all_rows = (
        (
            await db_session.execute(
                select(QuestCompletion).where(QuestCompletion.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    stats = (await client.get("/api/study/stats")).json()
    assert stats["xp"] == base_xp + 100 + sum(r.xp for r in all_rows)


async def test_quest_all_done_bonus(client, db_session):
    """3종 모두 완료하면 보너스 XP 가 원장에 한 번 더 적립된다."""
    user = await login(client, db_session)

    day = datetime.now(UTC).astimezone(KST).date()
    picked = retention.pick_quests(user.id, day.isoformat())

    # 모든 미션을 강제로 달성 상태로 만든다
    await _log_on(db_session, user.id, days_ago=0, count=10)  # review_10 + accuracy_80
    if "game_1" in picked:
        from app.models import GameMatch

        db_session.add(
            GameMatch(mode="pve", status="finished", player1_id=user.id, player2_id=None)
        )
    if "puzzle_try" in picked:
        from app.models import DailyPuzzlePlay

        db_session.add(DailyPuzzlePlay(user_id=user.id, day=day, guesses=["apple"]))
    # new_cards_5 는 _log_on 의 카드 1개뿐이면 부족 — 필요 시 4개 추가
    if "new_cards_5" in picked:
        items = await seed_items(db_session, count=4)
        for item in items:
            db_session.add(
                ReviewCard(user_id=user.id, item_id=item.id, state="new", due_at=datetime.now(UTC))
            )
    await db_session.flush()

    res = await client.get("/api/study/quests")
    body = res.json()
    assert all(q["done"] for q in body["items"])
    assert body["all_done"] is True

    from app.models import QuestCompletion

    bonus = (
        await db_session.execute(
            select(QuestCompletion).where(
                QuestCompletion.user_id == user.id,
                QuestCompletion.quest_key == retention.ALL_DONE_KEY,
            )
        )
    ).scalar_one()
    assert bonus.xp == retention.ALL_DONE_XP
