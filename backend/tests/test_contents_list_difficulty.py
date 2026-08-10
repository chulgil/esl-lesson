"""라이브러리 목록 난이도 배지 + 아는 표현 비율 (docs/specs/content-governance.md).

담기 전에 "내 수준의 영상인가"를 알 수 있게 목록 항목마다 실시간 파생값을 준다.
"""

from datetime import UTC, datetime

from sqlalchemy import select

from app.models import Content, ItemOccurrence, LearningItem, ReviewCard, TranscriptSegment
from tests.test_study import login

_word_counter = 0


async def make_content(db, title: str, hints: list[str]) -> Content:
    """공용 ready 콘텐츠 + 주어진 difficulty_hint 항목들. 목록은 공용을 담기 전에도 노출한다."""
    global _word_counter
    content = Content(source="manual", title=title, visibility="public", status="ready")
    db.add(content)
    await db.flush()
    for hint in hints:
        _word_counter += 1
        key = f"diffword{_word_counter}"
        item = LearningItem(
            item_type="word",
            en_text=key,
            ko_text="뜻",
            normalized_key=key,
            review_status="approved",
            difficulty_hint=hint,
        )
        db.add(item)
        await db.flush()
        db.add(ItemOccurrence(item_id=item.id, content_id=content.id))
    await db.commit()
    return content


async def item_ids_of(db, content: Content) -> list[int]:
    return list(
        (
            await db.execute(
                select(ItemOccurrence.item_id).where(ItemOccurrence.content_id == content.id)
            )
        )
        .scalars()
        .all()
    )


async def list_by_title(client) -> dict:
    res = await client.get("/api/contents")
    assert res.status_code == 200
    return {c["title"]: c for c in res.json()["items"]}


async def test_difficulty_label_from_item_hints(client, db_session):
    """가중 평균(basic=0/intermediate=1/advanced=2) 으로 초·중·고급을 파생한다."""
    await make_content(db_session, "고급물", ["advanced", "advanced", "intermediate"])  # 1.67
    await make_content(db_session, "중급물", ["intermediate", "intermediate"])  # 1.0
    await make_content(db_session, "초급물", ["basic", "basic", "intermediate"])  # 0.33
    await make_content(db_session, "빈것", [])
    await login(client, db_session)

    items = await list_by_title(client)
    assert items["고급물"]["difficulty"] == "advanced"
    assert items["중급물"]["difficulty"] == "intermediate"
    assert items["초급물"]["difficulty"] == "beginner"
    assert items["빈것"]["difficulty"] is None


async def test_difficulty_boundaries(client, db_session):
    """경계값: 평균 1.35 이상은 고급, 0.6 이하는 초급."""
    # advanced 2 + basic 1 + intermediate 1 -> (2+2+0+1)/4 = 1.25 -> 중급
    await make_content(db_session, "경계중급", ["advanced", "advanced", "basic", "intermediate"])
    # basic 2 + advanced 1 -> (0+0+2)/3 = 0.67 -> 0.6 초과라 중급
    await make_content(db_session, "경계중급2", ["basic", "basic", "advanced"])
    # basic 3 + intermediate 2 -> 0.4 -> 초급
    await make_content(
        db_session, "확실초급", ["basic", "basic", "basic", "intermediate", "intermediate"]
    )
    await login(client, db_session)

    items = await list_by_title(client)
    assert items["경계중급"]["difficulty"] == "intermediate"
    assert items["경계중급2"]["difficulty"] == "intermediate"
    assert items["확실초급"]["difficulty"] == "beginner"


async def add_segments(db, content: Content, sentences: list[str]) -> None:
    for i, s in enumerate(sentences):
        db.add(TranscriptSegment(content_id=content.id, seq=i, en_text=s))
    await db.commit()


async def test_short_sentences_make_beginner(client, db_session):
    """문장 길이 보정 (2026-08-10): 추출 힌트에 basic 이 사실상 없어(프로드 0건)
    힌트 평균만으로는 초급이 절대 안 나온다 — Easy English 류가 중급으로 오분류.
    짧은 문장(문장당 <=8단어) + 낮은 힌트 평균(<=1.12)이면 초급.
    """
    hints = ["intermediate"] * 9 + ["advanced"]  # 평균 1.1
    short = await make_content(db_session, "초급회화", list(hints))
    await add_segments(
        db_session,
        short,
        ["Hi, how are you?", "I am fine.", "A cup of coffee please."],  # 평균 4단어
    )
    # 같은 힌트 분포라도 문장이 길면 중급 유지
    mid = await make_content(db_session, "중급토크", list(hints))
    await add_segments(
        db_session,
        mid,
        ["We should think about how this actually works in practice today."],  # 11단어
    )
    await login(client, db_session)

    items = await list_by_title(client)
    assert items["초급회화"]["difficulty"] == "beginner"
    assert items["중급토크"]["difficulty"] == "intermediate"


async def test_long_sentences_make_advanced(client, db_session):
    """문장당 17단어 이상(긴 원어민 발화)은 힌트 평균이 1.35 미만이어도 고급."""
    hints = ["intermediate"] * 7 + ["advanced"] * 3  # 평균 1.3 (< 1.35)
    content = await make_content(db_session, "긴발화물", hints)
    await add_segments(
        db_session,
        content,
        [
            "He risked absolutely everything he had in order to warn people about "
            "the dangers that nobody else was willing to talk about openly."  # 23단어
        ],
    )
    await login(client, db_session)
    assert (await list_by_title(client))["긴발화물"]["difficulty"] == "advanced"


async def test_no_segments_falls_back_to_hint_only(client, db_session):
    """세그먼트 없는 수기 콘텐츠는 기존 힌트-단독 기준 유지 (회귀 방지)."""
    await make_content(db_session, "수기중급", ["intermediate", "intermediate"])  # 1.0
    await login(client, db_session)
    assert (await list_by_title(client))["수기중급"]["difficulty"] == "intermediate"


async def test_known_ratio_counts_my_cards(client, db_session):
    """내가 이미 카드로 보유한 항목 비율 — 4개 중 2개 보유면 50."""
    content = await make_content(
        db_session, "겹침물", ["intermediate", "intermediate", "advanced", "advanced"]
    )
    await make_content(db_session, "빈것", [])
    user = await login(client, db_session)

    assert (await list_by_title(client))["겹침물"]["known_ratio"] == 0

    for item_id in (await item_ids_of(db_session, content))[:2]:
        db_session.add(
            ReviewCard(user_id=user.id, item_id=item_id, due_at=datetime.now(UTC), state="new")
        )
    await db_session.commit()

    items = await list_by_title(client)
    assert items["겹침물"]["known_ratio"] == 50
    assert items["빈것"]["known_ratio"] is None


async def test_known_ratio_is_per_user(client, db_session):
    """다른 사용자의 카드는 내 비율에 섞이지 않는다."""
    content = await make_content(db_session, "타인물", ["intermediate", "advanced"])
    other = await login(client, db_session, email="other@example.com")
    for item_id in await item_ids_of(db_session, content):
        db_session.add(
            ReviewCard(user_id=other.id, item_id=item_id, due_at=datetime.now(UTC), state="new")
        )
    await db_session.commit()

    await login(client, db_session, email="me@example.com")
    assert (await list_by_title(client))["타인물"]["known_ratio"] == 0
