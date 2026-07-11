"""학습 API 통합: 큐 생성 -> 답안 -> FSRS 스케줄 갱신 (docs/specs/learning.md)."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.models import LearningItem, ReviewCard, ReviewLog
from app.services.fsrs_service import compute_rating


def test_compute_rating_mapping():
    assert compute_rating(False, 3000, "choice_en2ko", 0) == (1, 0)  # 오답 -> Again
    assert compute_rating(True, 20_000, "choice_en2ko", 0) == (2, 0)  # 느림 -> Hard
    assert compute_rating(True, 8_000, "choice_en2ko", 0) == (3, 0)  # 보통 -> Good
    assert compute_rating(True, 2_000, "choice_en2ko", 0) == (3, 1)  # 빠름 1회 -> Good
    assert compute_rating(True, 2_000, "choice_en2ko", 1) == (4, 2)  # 빠름 연속 2회 -> Easy
    assert compute_rating(True, 40_001, "compose", 0) == (2, 0)  # 입력형 기준 적용


_seed_counter = 0


async def seed_items(
    db, count=5, item_type="word", status="approved", visibility="public", owner=None
):
    """가시성 규칙 대응: 항목은 콘텐츠 출처(occurrence)가 있어야 노출된다."""
    from app.models import Content, ItemOccurrence

    global _seed_counter
    _seed_counter += 1
    batch = _seed_counter

    content = Content(
        source="manual",
        title=f"seed-{visibility}",
        status="ready",
        visibility=visibility,
        created_by=owner,
    )
    db.add(content)
    await db.flush()
    items = []
    for i in range(count):
        item = LearningItem(
            item_type=item_type,
            en_text=f"unique{visibility}{batch}n{i}",
            ko_text=f"뜻{batch}n{i}",
            normalized_key=f"unique{visibility}{batch}n{i}",
            review_status=status,
            hint_thinking="힌트" if item_type == "sentence" else None,
        )
        db.add(item)
        await db.flush()
        db.add(ItemOccurrence(item_id=item.id, content_id=content.id))
        items.append(item)
    await db.commit()
    return items


async def login(client, db, email="s@example.com"):
    from app.api.auth import upsert_google_user
    from app.core.config import get_settings
    from app.core.security import SESSION_COOKIE, create_session_token

    user = await upsert_google_user(
        db,
        {"sub": f"g-{email}", "email": email, "email_verified": True, "name": "S"},
        get_settings(),
    )
    client.cookies.set(SESSION_COOKIE, create_session_token(user))
    return user


async def test_queue_introduces_new_cards_and_builds_questions(client, db_session):
    user = await login(client, db_session)
    await seed_items(db_session, count=5)

    res = await client.get("/api/study/queue")
    assert res.status_code == 200
    body = res.json()
    assert len(body["questions"]) == 5
    assert body["introduced_today"] == 5
    q = body["questions"][0]
    assert q["quiz_mode"] in ("choice_en2ko", "choice_ko2en")
    assert len(q["choices"]) == 4

    cards = (
        (await db_session.execute(select(ReviewCard).where(ReviewCard.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(cards) == 5
    # 재호출해도 중복 생성되지 않는다
    res2 = await client.get("/api/study/queue")
    assert len(res2.json()["questions"]) == 5


async def test_queue_respects_daily_new_limit(client, db_session):
    await login(client, db_session)
    await seed_items(db_session, count=30)
    await client.patch("/api/settings", json={"daily_new_limit": 3})

    res = await client.get("/api/study/queue")
    assert res.json()["introduced_today"] == 3


async def test_queue_excludes_unapproved_items(client, db_session):
    await login(client, db_session)
    await seed_items(db_session, count=3, status="pending")
    res = await client.get("/api/study/queue")
    assert res.json()["questions"] == []


async def test_answer_correct_updates_card_and_logs(client, db_session):
    user = await login(client, db_session)
    await seed_items(db_session, count=4)
    queue = (await client.get("/api/study/queue")).json()
    q = queue["questions"][0]
    item = await db_session.get(LearningItem, q["item_id"])

    res = await client.post(
        "/api/study/answer",
        json={
            "card_id": q["card_id"],
            "quiz_mode": "choice_ko2en",
            "answer": item.en_text,
            "duration_ms": 6000,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["correct"] is True
    assert body["rating_applied"] == 3

    card = await db_session.get(ReviewCard, q["card_id"])
    await db_session.refresh(card)
    assert card.reps == 1
    # sqlite 는 tzinfo 를 보존하지 않으므로 UTC 를 부여해 비교
    due = card.due_at if card.due_at.tzinfo else card.due_at.replace(tzinfo=UTC)
    assert due > datetime.now(UTC)
    assert card.fsrs_json["card"]["stability"] is not None

    logs = (
        (await db_session.execute(select(ReviewLog).where(ReviewLog.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(logs) == 1
    assert logs[0].correct is True


async def test_answer_wrong_lapses_and_stats(client, db_session):
    await login(client, db_session)
    await seed_items(db_session, count=1)
    queue = (await client.get("/api/study/queue")).json()
    q = queue["questions"][0]

    res = await client.post(
        "/api/study/answer",
        json={"card_id": q["card_id"], "quiz_mode": "choice_ko2en", "answer": "wrong"},
    )
    assert res.json()["correct"] is False
    assert res.json()["rating_applied"] == 1

    stats = (await client.get("/api/study/stats")).json()
    assert stats["reviews_today"] == 1
    assert stats["streak_days"] == 1
    assert any(lv["cards"] == 1 for lv in stats["levels"])


async def test_rate_overrides_last_review(client, db_session):
    await login(client, db_session)
    await seed_items(db_session, count=1, item_type="sentence")
    queue = (await client.get("/api/study/queue")).json()
    q = queue["questions"][0]
    item = await db_session.get(LearningItem, q["item_id"])

    await client.post(
        "/api/study/answer",
        json={
            "card_id": q["card_id"],
            "quiz_mode": "compose",
            "answer": item.en_text,
            "duration_ms": 20_000,
        },
    )
    res = await client.post("/api/study/rate", json={"card_id": q["card_id"], "rating": 2})
    assert res.status_code == 200

    card = await db_session.get(ReviewCard, q["card_id"])
    await db_session.refresh(card)
    assert card.reps == 1  # 재적용이지 추가 리뷰가 아니다
    log = (
        await db_session.execute(select(ReviewLog).order_by(ReviewLog.id.desc()).limit(1))
    ).scalar_one()
    assert log.rating == 2


async def test_settings_roundtrip_and_level_filter(client, db_session):
    await login(client, db_session)
    await seed_items(db_session, count=2, item_type="word")
    res = await client.patch("/api/settings", json={"levels_enabled": [4]})
    assert res.json()["levels_enabled"] == [4]

    queue = (await client.get("/api/study/queue")).json()
    assert queue["questions"] == []  # word(레벨1) 비활성화됨
