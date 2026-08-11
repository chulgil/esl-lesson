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
    """가시성 규칙 대응: 항목은 콘텐츠 출처(occurrence)가 있고 담겨(구독) 있어야 노출된다.

    2026-07-27 이후 공용 콘텐츠도 담아야 노출되므로(content-governance.md), 시드
    시점에 존재하는 사용자를 자동 구독시킨다. 시드 후 로그인하는 경우는 login()
    이 기존 공용 콘텐츠를 담아 준다. 담기 게이트 자체를 검증하는 테스트는 이
    헬퍼를 쓰지 않고 콘텐츠·구독을 직접 만든다.
    """
    from app.models import Content, ContentSubscription, ItemOccurrence, User

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
    if visibility == "private":
        if owner is not None:
            db.add(ContentSubscription(content_id=content.id, user_id=owner))
    else:
        for user_id in (await db.execute(select(User.id))).scalars().all():
            db.add(ContentSubscription(content_id=content.id, user_id=user_id))
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
    await subscribe_existing_public(db, user.id)
    return user


async def subscribe_existing_public(db, user_id):
    """이 사용자를 기존 공용 콘텐츠에 담아 둔다 (seed_items 뒤에 로그인하는 순서 대응)."""
    from app.models import Content, ContentSubscription

    existing = set(
        (
            await db.execute(
                select(ContentSubscription.content_id).where(ContentSubscription.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    rows = (
        (await db.execute(select(Content.id).where(Content.visibility == "public"))).scalars().all()
    )
    for content_id in rows:
        if content_id not in existing:
            db.add(ContentSubscription(content_id=content_id, user_id=user_id))
    await db.commit()


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
    # 잠긴 타입 표시 (2026-08-11): 기본 초급(levels_enabled=[1,2]) — 문장·패턴은
    # 잠김으로 내려가 컬렉션이 "왜 0인지"를 설명한다
    enabled_of = {lv["item_type"]: lv["enabled"] for lv in stats["levels"]}
    assert enabled_of["word"] is True and enabled_of["idiom"] is True
    assert enabled_of["pattern"] is False and enabled_of["sentence"] is False


async def test_rate_overrides_last_review(client, db_session):
    await login(client, db_session)
    await client.patch("/api/settings", json={"study_level": 4})
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
    res = await client.patch(
        "/api/settings", json={"levels_enabled": [4], "hint_delay_seconds": 15}
    )
    assert res.json()["levels_enabled"] == [4]
    assert res.json()["hint_delay_seconds"] == 15

    queue = (await client.get("/api/study/queue")).json()
    assert queue["questions"] == []  # word(레벨1) 비활성화됨


async def test_question_includes_youtube_media_segment(client, db_session):
    """출처가 유튜브 세그먼트인 항목은 문항에 구간 재생 정보 포함 (구간 듣기)."""
    from app.models import Content, ContentSubscription, ItemOccurrence, TranscriptSegment

    user = await login(client, db_session)
    content = Content(
        source="youtube",
        youtube_video_id="dQw4w9WgXcQ",
        title="영상",
        status="ready",
        visibility="private",
        created_by=user.id,
    )
    db_session.add(content)
    await db_session.flush()
    db_session.add(ContentSubscription(content_id=content.id, user_id=user.id))
    segment = TranscriptSegment(
        content_id=content.id, seq=0, start_ms=12000, end_ms=15500, en_text="Hello there."
    )
    db_session.add(segment)
    await db_session.flush()
    item = LearningItem(
        item_type="word",
        en_text="mediaword",
        ko_text="뜻",
        normalized_key="mediaword",
        review_status="pending",
    )
    db_session.add(item)
    await db_session.flush()
    db_session.add(ItemOccurrence(item_id=item.id, content_id=content.id, segment_id=segment.id))
    await db_session.commit()

    queue = (await client.get("/api/study/queue")).json()
    assert queue["hint_delay_seconds"] == 10  # 기본값
    q = queue["questions"][0]
    assert q["media"] == {"video_id": "dQw4w9WgXcQ", "start_ms": 12000, "end_ms": 15500}
    assert q["hint_answer"]  # 힌트 타이머용 정답 정보 포함


async def test_answer_returns_anki_style_interval_previews(client, db_session):
    """등급별 예상 간격 미리보기 — 다시<어려움<=알맞음<=쉬움 (docs/specs/learning.md)."""
    await login(client, db_session)
    await seed_items(db_session, count=1)
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
    previews = res.json()["interval_previews"]
    assert set(previews.keys()) == {"1", "2", "3", "4"}
    assert previews["1"] <= previews["2"] <= previews["3"] <= previews["4"]
    assert previews["4"] > 60  # 쉬움은 하루 이상 단위로 벌어진다


async def test_study_level_derives_enabled_levels(client, db_session):
    """학습 난이도가 활성 레벨을 파생 — 저레벨은 문장(타이핑) 제외 (docs/specs/learning.md)."""
    await login(client, db_session)
    # 입문(1) = 단어만
    res = await client.patch("/api/settings", json={"study_level": 1})
    assert res.json()["study_level"] == 1
    assert res.json()["levels_enabled"] == [1]
    # 중급(3) = 단어+숙어+패턴 (문장 없음 → 타이핑 없음)
    res = await client.patch("/api/settings", json={"study_level": 3})
    assert res.json()["levels_enabled"] == [1, 2, 3]
    # 고급(4) = 문장 포함
    res = await client.patch("/api/settings", json={"study_level": 4})
    assert res.json()["levels_enabled"] == [1, 2, 3, 4]


async def test_default_new_user_is_beginner(client, db_session):
    """신규 사용자 기본은 초급(2) — 문장 타이핑 없이 시작."""
    await login(client, db_session, email="fresh@example.com")
    settings = (await client.get("/api/settings")).json()
    assert settings["study_level"] == 2
    assert settings["levels_enabled"] == [1, 2]


async def test_stats_levels_use_my_visibility_not_global_approved(client, db_session):
    """레벨 분모=내 가시성(공용 승인 ∪ 내 개인 비거부), 분자=suspended 제외 (2026-07-15 검증)."""
    from datetime import UTC, datetime

    from app.models import ReviewCard

    me = await login(client, db_session)
    pub = await seed_items(db_session, count=2)  # 공용 approved 2개
    mine = await seed_items(
        db_session, count=1, status="pending", visibility="private", owner=me.id
    )  # 내 개인 pending — 큐 도입 대상이므로 분모 포함이 맞다
    from app.models import User

    other = User(google_sub="g-vis", email="vis@example.com", name="남", nickname="남")
    db_session.add(other)
    await db_session.flush()
    await seed_items(
        db_session, count=1, status="pending", visibility="private", owner=other.id
    )  # 타인 개인 — 내 화면 분모에서 제외

    now = datetime.now(UTC)
    db_session.add_all(
        [
            ReviewCard(user_id=me.id, item_id=pub[0].id, state="review", due_at=now, reps=1),
            ReviewCard(
                user_id=me.id,
                item_id=pub[1].id,
                state="review",
                due_at=now,
                reps=1,
                suspended=True,
            ),
            ReviewCard(user_id=me.id, item_id=mine[0].id, state="new", due_at=now),
        ]
    )
    await db_session.commit()

    stats = (await client.get("/api/study/stats")).json()
    word = next(lv for lv in stats["levels"] if lv["item_type"] == "word")
    assert word["available_items"] == 3  # 공용 2 + 내 개인 1 (타인 개인 제외)
    assert word["cards"] == 1  # suspended 제외 + 아직 안 푼 새 카드(reps=0) 제외


async def test_collection_counts_only_answered_cards(client, db_session):
    """컬렉션 분자 = 한 번이라도 푼 카드. 큐에 도입만 된 새 카드는 세지 않는다.

    (2026-08-03 — 도입만으로 세면 담은 콘텐츠를 큐에 다 꺼내는 순간 영구 100%)
    """

    def word_level(stats):
        return next(lv for lv in stats["levels"] if lv["item_type"] == "word")

    await login(client, db_session)
    await seed_items(db_session, count=2)
    queue = (await client.get("/api/study/queue")).json()  # 카드 2장 도입
    before = word_level((await client.get("/api/study/stats")).json())
    assert before["available_items"] == 2
    assert before["cards"] == 0  # 아직 아무것도 안 풀었다

    await client.post(
        "/api/study/answer",
        json={
            "card_id": queue["questions"][0]["card_id"],
            "quiz_mode": "choice_ko2en",
            "answer": "wrong",
        },
    )
    after = word_level((await client.get("/api/study/stats")).json())
    assert after["cards"] == 1  # 오답이어도 "만난" 카드


async def test_reviews_today_uses_kst_day_boundary(client, db_session):
    """오늘 복습 카운트는 KST 자정 기준 — 어제 23:59 KST 는 제외."""
    from datetime import UTC, datetime, timedelta

    from app.api.study import KST
    from app.models import ReviewCard, ReviewLog

    me = await login(client, db_session)
    items = await seed_items(db_session, count=1)
    card = ReviewCard(user_id=me.id, item_id=items[0].id, state="review", due_at=datetime.now(UTC))
    db_session.add(card)
    await db_session.flush()

    today_kst = datetime.now(UTC).astimezone(KST).replace(hour=0, minute=1, second=0)
    yesterday_kst = today_kst - timedelta(minutes=2)  # 어제 23:59 KST
    for when in (today_kst, yesterday_kst):
        db_session.add(
            ReviewLog(
                card_id=card.id,
                user_id=me.id,
                rating=3,
                correct=True,
                quiz_mode="choice_en2ko",
                state_before="review",
                reviewed_at=when.astimezone(UTC),
            )
        )
    await db_session.commit()

    stats = (await client.get("/api/study/stats")).json()
    assert stats["reviews_today"] == 1
