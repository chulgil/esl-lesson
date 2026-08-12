"""내가 쓰는 말 덱 — 채팅 발화 수집·항목 합류·게임 풀 포함 (docs/specs/my-phrases.md)."""

from sqlalchemy import select

from app.models import ChatTranslation, Content, LearningItem
from app.services.game.typing_race import load_sentence_pool
from app.services.langs import normalize_text_key
from tests.test_chat import login, send_body, two_friends
from tests.test_game_manager import wired_db  # noqa: F401


async def seed_translation(db, original: str, translated: str, target: str = "en"):
    db.add(
        ChatTranslation(
            text_key=normalize_text_key(original),
            source_lang="ko",
            target_lang=target,
            text=translated,
            engine="deepl",
        )
    )
    await db.commit()


async def send(client, to_id: int, body: str, cid: str):
    res = await client.post("/api/chat/messages", json=send_body(to_id, body, cid))
    assert res.status_code in (200, 201)
    return res.json()


async def test_sync_creates_deck_and_is_idempotent(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "오늘 저녁에 뭐 먹을까?", "cid-mp00001")
    await seed_translation(db_session, "오늘 저녁에 뭐 먹을까?", "What should we eat tonight?")

    res = await client.get("/api/study/my-phrases")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["added_now"] == 1
    assert body["recent"][0] == {
        "en": "What should we eat tonight?",
        "ko": "오늘 저녁에 뭐 먹을까?",
    }

    # 멱등 — 재호출해도 콘텐츠 1개·항목 1개 유지
    again = (await client.get("/api/study/my-phrases")).json()
    assert again["total"] == 1
    assert again["added_now"] == 0
    decks = (
        (
            await db_session.execute(
                select(Content).where(Content.source == "chat", Content.created_by == a.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(decks) == 1
    assert decks[0].visibility == "private"


async def test_collect_filters_noise(client, db_session):
    """짧은 문장·링크·번역 캐시 없는 문장은 수집하지 않는다."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "네", "cid-mp00011")  # 4자 미만
    await seed_translation(db_session, "네", "Yes")
    await send(client, b.id, "여기 봐 http://x.com 링크야", "cid-mp00012")  # 링크
    await seed_translation(db_session, "여기 봐 http://x.com 링크야", "See this link")
    await send(client, b.id, "번역 캐시가 없는 문장입니다", "cid-mp00013")  # 캐시 없음

    res = (await client.get("/api/study/my-phrases")).json()
    assert res["total"] == 0


async def test_short_phrase_needs_frequency_two(client, db_session):
    """4~5자 문장은 2회 이상 써야 채택 — "자주 쓰는 말" 우선."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "고마워요", "cid-mp00021")  # 4자, 1회
    await seed_translation(db_session, "고마워요", "Thank you")

    assert (await client.get("/api/study/my-phrases")).json()["total"] == 0

    await send(client, b.id, "고마워요", "cid-mp00022")  # 2회째 — 채택
    res = (await client.get("/api/study/my-phrases")).json()
    assert res["total"] == 1
    assert res["recent"][0]["en"] == "Thank you"


async def test_items_flow_into_typing_pool_privately(client, db_session, wired_db):  # noqa: F811
    """수집 항목은 문장 게임 풀에 자동 포함 — 본인에게만 (private 가시성)."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "이번 주말에 등산 갈래?", "cid-mp00031")
    await seed_translation(db_session, "이번 주말에 등산 갈래?", "Wanna go hiking this weekend?")
    assert (await client.get("/api/study/my-phrases")).json()["total"] == 1

    mine = await load_sentence_pool(a.id)
    assert any(s["en"] == "Wanna go hiking this weekend?" for s in mine)
    theirs = await load_sentence_pool(b.id)
    assert not any(s["en"] == "Wanna go hiking this weekend?" for s in theirs)


async def test_queue_introduces_my_phrases(client, db_session):
    """복습 큐 신규 도입에 내 표현이 편입된다 (sentence 레벨 활성 시)."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "내일 회의 몇 시에 시작해?", "cid-mp00041")
    await seed_translation(
        db_session, "내일 회의 몇 시에 시작해?", "What time does the meeting start tomorrow?"
    )
    await client.get("/api/study/my-phrases")
    # 문장 타입 학습 활성 (기본 levels 1,2 는 단어·숙어)
    await client.patch("/api/settings", json={"levels_enabled": [1, 2, 3, 4]})

    queue = (await client.get("/api/study/queue")).json()
    # 문장 문항은 compose (prompt_ko=내 원문, hint_answer=학습언어 번역문)
    answers = {q.get("hint_answer") or "" for q in queue["questions"]}
    assert any("meeting" in t for t in answers)


async def test_deck_study_works_with_default_levels(client, db_session):
    """기본 레벨(단어·숙어)이어도 내 말투 덱 한정 학습은 문장이 나온다 (2026-08-12 빈 세션 보고)."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "오늘 야근해야 할 것 같아", "cid-mp00061")
    await seed_translation(
        db_session, "오늘 야근해야 할 것 같아", "I think I have to work late today"
    )
    deck_id = (await client.get("/api/study/my-phrases")).json()["content_id"]

    # levels_enabled 는 기본값 [1,2] (문장 미포함) 그대로
    queue = (await client.get(f"/api/study/queue?content_id={deck_id}")).json()
    assert len(queue["questions"]) == 1
    assert "work late" in queue["questions"][0]["hint_answer"]


async def test_exclude_phrase_removes_and_stays_removed(client, db_session, wired_db):  # noqa: F811
    """문장 빼기 — 목록·게임 풀에서 사라지고, 재동기화에도 돌아오지 않는다."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "이 문장은 빼고 싶어요", "cid-mp00071")
    await seed_translation(db_session, "이 문장은 빼고 싶어요", "I want to remove this one")
    items = (await client.get("/api/study/my-phrases/items")).json()["items"]
    assert len(items) == 1

    res = await client.delete(f"/api/study/my-phrases/{items[0]['item_id']}")
    assert res.status_code == 204

    # 재동기화(목록 조회가 곧 sync)에도 돌아오지 않는다
    again = (await client.get("/api/study/my-phrases/items")).json()["items"]
    assert again == []
    assert (await client.get("/api/study/my-phrases")).json()["total"] == 0
    # 게임 풀에서도 제외
    pool = await load_sentence_pool(a.id)
    assert not any(s["en"] == "I want to remove this one" for s in pool)

    # 존재하지 않는 항목 404
    res = await client.delete("/api/study/my-phrases/999999")
    assert res.status_code == 404


async def test_deck_item_reuses_global_normalized_key(client, db_session):
    """같은 번역문이 이미 전역 항목으로 있으면 재사용 — Occurrence 만 연결."""
    a, b = await two_friends(client, db_session)
    db_session.add(
        LearningItem(
            item_type="sentence",
            en_text="Thank you so much!",
            ko_text="정말 고마워!",
            normalized_key="thank you so much!",
        )
    )
    await db_session.commit()
    await login(client, db_session, a)
    await send(client, b.id, "정말 고마워 친구야", "cid-mp00051")
    await seed_translation(db_session, "정말 고마워 친구야", "Thank you so much!")
    await client.get("/api/study/my-phrases")

    items = (
        (
            await db_session.execute(
                select(LearningItem).where(LearningItem.normalized_key == "thank you so much!")
            )
        )
        .scalars()
        .all()
    )
    assert len(items) == 1  # 중복 생성 없음
