"""내가 쓰는 말 덱 — 채팅 발화 수집·언어별 분리·항목 합류·게임 풀 포함
(docs/specs/my-phrases.md)."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.models import (
    ChatMessage,
    ChatTranslation,
    Content,
    ContentSubscription,
    ItemOccurrence,
    LearningItem,
    ReviewCard,
)
from app.services.chat import get_conversation
from app.services.game.typing_race import load_sentence_pool
from app.services.langs import normalize_text_key
from tests.test_chat import login, login_as, make_friends, send_body, two_friends
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


async def learn_pair(client, db):
    """학습 방(ko→en)을 명시적으로 가진 친구 쌍 — 기존 방·레거시 경로가 일반
    방(plain)이 된 뒤(2026-08-14 결정 #8), 수집 대상은 마법사로 만든 학습 방이다."""
    from app.services import chat as chat_service

    a, b = await two_friends(client, db)
    await chat_service.get_or_create_room(db, a.id, b.id, "ko", "en", mode="learn")
    return a, b


async def send(client, to_id: int, body: str, cid: str):
    res = await client.post("/api/chat/messages", json=send_body(to_id, body, cid))
    assert res.status_code in (200, 201)
    return res.json()


async def three_users_two_rooms(client, db):
    """a-b 는 학습(ko→en) 방, a-c 는 set_room_lang 으로 언어를 바꿔 쓴다."""
    from app.services import chat as chat_service

    a = await login_as(client, db, "a@example.com")
    b = await login_as(client, db, "b@example.com")
    c = await login_as(client, db, "c@example.com")
    await make_friends(db, a, b)
    await make_friends(db, a, c)
    await chat_service.get_or_create_room(db, a.id, b.id, "ko", "en", mode="learn")
    await chat_service.get_or_create_room(db, a.id, c.id, "ko", "en", mode="learn")
    return a, b, c


async def set_room_lang(db, a, b, target_lang: str) -> None:
    conv = await get_conversation(db, a.id, b.id)
    conv.target_lang = target_lang
    conv.mode = "learn"
    await db.commit()


async def seed_legacy_deck(db, user_id: int, en_text: str, ko_text: str, lang: str = "en"):
    """(일반) 덱 시뮬레이션 — 마이그레이션 g1b2c3d4e5f6 이 배포 시점의 chat 덱을
    chat_kind='legacy'로 전환하는 상태를 테스트에서 직접 재현한다
    (docs/specs/my-phrases.md 덱 그룹화)."""
    deck = Content(
        source="chat",
        chat_kind="legacy",
        title="내가 쓰는 말 (일반)",
        status="ready",
        visibility="private",
        created_by=user_id,
        lang=lang,
    )
    db.add(deck)
    await db.flush()
    db.add(ContentSubscription(content_id=deck.id, user_id=user_id))
    item = LearningItem(
        item_type="sentence",
        en_text=en_text,
        ko_text=ko_text,
        normalized_key=normalize_text_key(en_text),
    )
    db.add(item)
    await db.flush()
    db.add(ItemOccurrence(item_id=item.id, content_id=deck.id))
    await db.commit()
    return deck, item


async def test_sync_creates_deck_and_is_idempotent(client, db_session):
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "오늘 저녁에 뭐 먹을까?", "cid-mp00001")
    await send(client, b.id, "오늘 저녁에 뭐 먹을까?", "cid-mp00001b")
    await seed_translation(db_session, "오늘 저녁에 뭐 먹을까?", "What should we eat tonight?")

    res = await client.get("/api/study/my-phrases")
    assert res.status_code == 200
    body = res.json()
    assert body["lang"] == "en"
    assert body["total"] == 1
    assert body["active"] == 1
    assert body["graduated"] == 0
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
    assert decks[0].title == "내가 쓰는 말 (영어)"


async def test_lang_rooms_split_into_separate_decks(client, db_session):
    """방의 target_lang 이 다르면 발화가 서로 다른 언어별 덱으로 나뉜다
    (2026-08-14 언어별 덱 — my-phrases.md)."""
    a, b, c = await three_users_two_rooms(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "오늘 저녁에 뭐 먹을까?", "cid-lang001")
    await send(client, b.id, "오늘 저녁에 뭐 먹을까?", "cid-lang001b")
    await seed_translation(
        db_session, "오늘 저녁에 뭐 먹을까?", "What should we eat tonight?", "en"
    )

    await send(client, c.id, "미안 늦었어", "cid-lang002")
    await send(client, c.id, "미안 늦었어", "cid-lang002b")
    await set_room_lang(db_session, a, c, "ja")
    await seed_translation(db_session, "미안 늦었어", "遅れてごめん", "ja")

    en = (await client.get("/api/study/my-phrases?lang=en")).json()
    assert en["lang"] == "en"
    assert en["total"] == 1
    assert en["recent"][0]["en"] == "What should we eat tonight?"

    ja = (await client.get("/api/study/my-phrases?lang=ja")).json()
    assert ja["lang"] == "ja"
    assert ja["total"] == 1
    assert ja["recent"][0]["en"] == "遅れてごめん"

    assert en["content_id"] != ja["content_id"]
    decks = (
        await db_session.execute(
            select(Content.lang, Content.title).where(
                Content.source == "chat", Content.created_by == a.id
            )
        )
    ).all()
    assert set(decks) == {
        ("en", "내가 쓰는 말 (영어)"),
        ("ja", "내가 쓰는 말 (일본어)"),
    }


async def test_legacy_deck_stays_separate_from_new_lang_sync(client, db_session):
    """(일반) 덱(chat_kind='legacy')이 있어도 학습 방 수집은 별개의 새 언어별
    덱을 만든다 — legacy 덱에 섞이지 않는다 (my-phrases.md 덱 그룹화)."""
    a, b = await learn_pair(client, db_session)
    legacy_deck, _legacy_item = await seed_legacy_deck(
        db_session, a.id, "Legacy phrase", "레거시 문장"
    )

    await login(client, db_session, a)
    await send(client, b.id, "새로 쓰는 문장이에요", "cid-grp001")
    await send(client, b.id, "새로 쓰는 문장이에요", "cid-grp001b")
    await seed_translation(db_session, "새로 쓰는 문장이에요", "This is a new sentence")

    en = (await client.get("/api/study/my-phrases?lang=en")).json()
    assert en["total"] == 1
    assert en["recent"][0]["en"] == "This is a new sentence"
    assert en["content_id"] != legacy_deck.id
    assert en["legacy_total"] == 1  # legacy 존재 여부/개수를 프론트에 알림

    # legacy 덱 자체는 건드리지 않는다
    decks = (
        (
            await db_session.execute(
                select(Content).where(Content.source == "chat", Content.created_by == a.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(decks) == 2
    kinds = {d.chat_kind for d in decks}
    assert kinds == {"legacy", None}


async def test_legacy_lang_returns_summary_and_items_without_sync(client, db_session):
    """lang='legacy' 는 sync 없이 (일반) 덱 현황·목록만 반환한다 (my-phrases.md API)."""
    a, _b = await two_friends(client, db_session)
    legacy_deck, _item = await seed_legacy_deck(db_session, a.id, "Legacy phrase", "레거시 문장")

    await login(client, db_session, a)
    res = (await client.get("/api/study/my-phrases?lang=legacy")).json()
    assert res["lang"] == "legacy"
    assert res["content_id"] == legacy_deck.id
    assert res["total"] == 1
    assert res["added_now"] == 0  # 신규 수집 동결 — sync 호출 없음
    assert res["legacy_total"] == 1
    assert res["recent"][0] == {"en": "Legacy phrase", "ko": "레거시 문장"}

    items = (await client.get("/api/study/my-phrases/items?lang=legacy")).json()
    assert items["lang"] == "legacy"
    assert len(items["items"]) == 1
    assert items["items"][0]["en_text"] == "Legacy phrase"
    assert items["legacy_total"] == 1


async def test_legacy_lang_missing_deck_returns_empty(client, db_session):
    """(일반) 덱이 아직 없는 사용자는 lang='legacy' 조회 시 빈 현황을 받는다."""
    a = await login_as(client, db_session, "nolegacy@example.com")
    await login(client, db_session, a)
    res = (await client.get("/api/study/my-phrases?lang=legacy")).json()
    assert res == {
        "content_id": None,
        "lang": "legacy",
        "total": 0,
        "active": 0,
        "graduated": 0,
        "added_now": 0,
        "recent": [],
        "legacy_total": 0,
        "subscribed": True,
    }


async def test_legacy_phrase_removal_updates_legacy_total(client, db_session):
    """(일반) 덱 문장 빼기도 언어별 덱과 동일하게 동작한다 (my-phrases.md 편집)."""
    a, _b = await two_friends(client, db_session)
    legacy_deck, item = await seed_legacy_deck(db_session, a.id, "Legacy phrase", "레거시 문장")

    await login(client, db_session, a)
    res = await client.delete(f"/api/study/my-phrases/{item.id}")
    assert res.status_code == 204

    after = (await client.get("/api/study/my-phrases?lang=legacy")).json()
    assert after["content_id"] == legacy_deck.id  # 덱 자체는 남는다(빈 채로)
    assert after["total"] == 0
    assert after["legacy_total"] == 0


async def test_collect_filters_noise(client, db_session):
    """짧은 문장·링크·번역 캐시 없는 문장은 수집하지 않는다."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "네", "cid-mp00011")  # 4자 미만
    await send(client, b.id, "네", "cid-mp00011b")
    await seed_translation(db_session, "네", "Yes")
    await send(client, b.id, "여기 봐 http://x.com 링크야", "cid-mp00012")  # 링크
    await send(client, b.id, "여기 봐 http://x.com 링크야", "cid-mp00012b")
    await seed_translation(db_session, "여기 봐 http://x.com 링크야", "See this link")
    await send(client, b.id, "번역 캐시가 없는 문장입니다", "cid-mp00013")  # 캐시 없음

    res = (await client.get("/api/study/my-phrases")).json()
    assert res["total"] == 0


async def test_short_phrase_needs_frequency_two(client, db_session):
    """길이와 무관하게 2회 이상 써야 채택 — "자주 쓰는 말"의 이름값 (2026-08-12 기획)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "고마워요", "cid-mp00021")  # 4자, 1회
    await seed_translation(db_session, "고마워요", "Thank you")

    assert (await client.get("/api/study/my-phrases")).json()["total"] == 0

    await send(client, b.id, "고마워요", "cid-mp00022")  # 2회째 — 채택
    res = (await client.get("/api/study/my-phrases")).json()
    assert res["total"] == 1
    assert res["recent"][0]["en"] == "Thank you"


async def test_freq_resync_and_sort_order(client, db_session):
    """freq 는 sync 마다 재집계되고, 활성 목록은 빈도 내림차순 (my-phrases.md)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "고마워요", "cid-freq001")
    await send(client, b.id, "고마워요", "cid-freq001b")
    await seed_translation(db_session, "고마워요", "Thank you")
    await send(client, b.id, "안녕하세요", "cid-freq002")
    await send(client, b.id, "안녕하세요", "cid-freq002b")
    await send(client, b.id, "안녕하세요", "cid-freq002c")
    await seed_translation(db_session, "안녕하세요", "Hello")

    items = (await client.get("/api/study/my-phrases/items")).json()["items"]
    assert [i["en_text"] for i in items] == ["Hello", "Thank you"]
    assert items[0]["freq"] == 3
    assert items[1]["freq"] == 2

    # 세 번째 발화 — 재동기화 시 freq 가 재집계된다
    await send(client, b.id, "고마워요", "cid-freq001c")
    items2 = (await client.get("/api/study/my-phrases/items")).json()["items"]
    by_text = {i["en_text"]: i["freq"] for i in items2}
    assert by_text["Thank you"] == 3
    assert by_text["Hello"] == 3


async def test_active_100_cap_and_graduation_topup(client, db_session):
    """활성 100 목표 — 101번째 후보는 대기하고, 장기기억 졸업으로 빈 자리가
    생기면 다음 sync 가 채운다 (my-phrases.md 활성 100개 순환 보충)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "seed", "cid-cap-seed")
    conv = await get_conversation(db_session, a.id, b.id)

    for i in range(101):
        text = f"문장 테스트 {i:03d} 내용입니다"
        for suffix in ("a", "b"):
            db_session.add(
                ChatMessage(
                    conversation_id=conv.id,
                    sender_id=a.id,
                    body=text,
                    client_msg_id=f"cid-cap-{i:03d}-{suffix}",
                )
            )
        await seed_translation(db_session, text, f"Test sentence {i:03d} content")
    await db_session.commit()

    res = (await client.get("/api/study/my-phrases")).json()
    assert res["active"] == 100
    assert res["total"] == 100
    assert res["graduated"] == 0

    items = (await client.get("/api/study/my-phrases/items")).json()
    assert len(items["items"]) == 100

    # 활성 항목 하나를 장기기억(stability 7일+) 도달로 만들어 졸업시킨다
    graduated_item_id = items["items"][0]["id"]
    db_session.add(
        ReviewCard(
            user_id=a.id,
            item_id=graduated_item_id,
            state="review",
            stability=8.0,
            due_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    # 재동기화(조회가 곧 sync) — 졸업으로 빈 자리(1개)를 101번째 후보가 채운다
    res2 = (await client.get("/api/study/my-phrases")).json()
    assert res2["active"] == 100
    assert res2["graduated"] == 1
    assert res2["total"] == 101


async def test_low_level_queue_gets_chat_sentence_assemble(client, db_session):
    """study_level=2(기본) 는 chat 덱 문장이 **청크 조립**으로 출제된다 —
    칩 최대 4개(+방해 1), WM 4±1 정합 (proposal/level-format-fit 형식 사다리)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "오늘 야근해야 할 것 같아", "cid-lvl001")
    await send(client, b.id, "오늘 야근해야 할 것 같아", "cid-lvl001b")
    await seed_translation(
        db_session, "오늘 야근해야 할 것 같아", "I think I have to work late today"
    )
    await client.get("/api/study/my-phrases")  # 동기화 — 기본 study_level=2 유지

    queue = (await client.get("/api/study/queue")).json()
    sentence_qs = [
        q for q in queue["questions"] if q.get("hint_answer") == "I think I have to work late today"
    ]
    assert len(sentence_qs) == 1
    question = sentence_qs[0]
    assert question["quiz_mode"] == "sentence_assemble"
    # 청크 조립 — 덱에 다른 문장이 없어 방해칩 0, 칩(청크)을 합치면 정답과 일치
    assert len(question["chips"]) <= 4
    assert sorted(" ".join(question["chips"]).split()) == sorted(question["hint_answer"].split())

    submit = await client.post(
        "/api/study/answer",
        json={
            "card_id": question["card_id"],
            "quiz_mode": "sentence_assemble",
            "answer": question["hint_answer"],
        },
    )
    assert submit.status_code == 200
    assert submit.json()["correct"] is True


async def test_level1_sentence_choice_format(client, db_session):
    """study_level=1 은 chat 문장이 뜻 매칭 선다(recognition)로 출제된다 —
    같은 덱 문장 4개 중 번역문 선택 (proposal/level-format-fit 형식 사다리)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    phrases = [
        ("오늘 야근해야 할 것 같아", "I think I have to work late today"),
        ("확인하고 다시 연락드릴게요", "Let me check and get back to you"),
        ("주말에 등산 갈래요?", "Wanna go hiking this weekend?"),
        ("점심 뭐 먹을까요?", "What should we have for lunch?"),
    ]
    for i, (ko, en) in enumerate(phrases):
        await send(client, b.id, ko, f"cid-l1-{i}a")
        await send(client, b.id, ko, f"cid-l1-{i}b")
        await seed_translation(db_session, ko, en)
    await client.get("/api/study/my-phrases")
    await client.patch("/api/settings", json={"study_level": 1})

    queue = (await client.get("/api/study/queue")).json()
    target = [q for q in queue["questions"] if q.get("hint_answer") == phrases[0][1]]
    assert len(target) == 1
    question = target[0]
    assert question["quiz_mode"] == "choice_ko2en"
    assert len(question["choices"]) == 4
    assert phrases[0][1] in question["choices"]

    submit = await client.post(
        "/api/study/answer",
        json={
            "card_id": question["card_id"],
            "quiz_mode": "choice_ko2en",
            "answer": phrases[0][1],
        },
    )
    assert submit.status_code == 200
    assert submit.json()["correct"] is True


async def test_level3_word_assembly_two_decoys(client, db_session):
    """study_level=3 은 단어 칩 조립 — 정답 단어 전부 + 방해칩 최대 2개
    (proposal/level-format-fit: 기존 3개에서 축소)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    for i, (ko, en) in enumerate(
        [
            ("오늘 야근해야 할 것 같아", "I think I have to work late today"),
            ("확인하고 다시 연락드릴게요", "Let me check and get back to you"),
        ]
    ):
        await send(client, b.id, ko, f"cid-l3-{i}a")
        await send(client, b.id, ko, f"cid-l3-{i}b")
        await seed_translation(db_session, ko, en)
    await client.get("/api/study/my-phrases")
    await client.patch("/api/settings", json={"study_level": 3})

    queue = (await client.get("/api/study/queue")).json()
    target = [
        q for q in queue["questions"] if q.get("hint_answer") == "I think I have to work late today"
    ]
    assert len(target) == 1
    question = target[0]
    assert question["quiz_mode"] == "sentence_assemble"
    words = question["hint_answer"].split()
    assert set(words) <= set(question["chips"])
    assert len(question["chips"]) <= len(words) + 2


async def test_low_level_gate_excludes_long_sentences(client, db_session):
    """레벨 1~2 큐는 9단어+ chat 문장을 제외한다(길이 게이트 8단어) —
    일반·덱 한정 모두. 레벨 3부터 다시 출제 (proposal/level-format-fit)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    long_en = "Could you please send me the updated file before tomorrow morning"  # 11단어
    await send(client, b.id, "내일 아침 전에 수정된 파일 보내줄 수 있어요", "cid-gate1")
    await send(client, b.id, "내일 아침 전에 수정된 파일 보내줄 수 있어요", "cid-gate1b")
    await seed_translation(db_session, "내일 아침 전에 수정된 파일 보내줄 수 있어요", long_en)
    deck_id = (await client.get("/api/study/my-phrases")).json()["content_id"]

    queue = (await client.get("/api/study/queue")).json()
    assert not [q for q in queue["questions"] if q.get("hint_answer") == long_en]
    deck_queue = (await client.get(f"/api/study/queue?content_id={deck_id}")).json()
    assert not [q for q in deck_queue["questions"] if q.get("hint_answer") == long_en]

    await client.patch("/api/settings", json={"study_level": 3})
    queue3 = (await client.get("/api/study/queue")).json()
    assert [q for q in queue3["questions"] if q.get("hint_answer") == long_en]


async def test_sentence_page_cap_general_queue(client, db_session):
    """레벨 ≤2 일반 큐는 페이지당 문장 카드 최대 5개(선다 리듬 유지) —
    덱 한정 세션은 캡 없음 (proposal/level-format-fit 혼합 캡)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    for i in range(7):
        ko = f"오늘 회의 {i}번째 안건 정리했어요"
        en = f"I organized agenda item number {i} today"
        await send(client, b.id, ko, f"cid-cap7-{i}a")
        await send(client, b.id, ko, f"cid-cap7-{i}b")
        await seed_translation(db_session, ko, en)
    deck_id = (await client.get("/api/study/my-phrases")).json()["content_id"]

    queue = (await client.get("/api/study/queue")).json()
    sentence_qs = [q for q in queue["questions"] if q["quiz_mode"] == "sentence_assemble"]
    assert len(sentence_qs) == 5

    deck_queue = (await client.get(f"/api/study/queue?content_id={deck_id}")).json()
    deck_sentence_qs = [q for q in deck_queue["questions"] if q["quiz_mode"] == "sentence_assemble"]
    assert len(deck_sentence_qs) == 7


async def test_chat_deck_subscribe_toggle_preserves_deck(client, db_session):
    """문서함 담기/빼기 — 빼기는 구독만 해지(큐·게임 제외), 덱 본체·수집분은
    보존되고 재담기 시 그대로 복귀한다 (2026-08-18 요청)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "오늘 야근해야 할 것 같아", "cid-sub01")
    await send(client, b.id, "오늘 야근해야 할 것 같아", "cid-sub01b")
    await seed_translation(
        db_session, "오늘 야근해야 할 것 같아", "I think I have to work late today"
    )
    summary = (await client.get("/api/study/my-phrases")).json()
    deck_id = summary["content_id"]
    assert summary["subscribed"] is True

    # 빼기 — 본체 삭제 없이 구독만 해지
    res = await client.delete(f"/api/my/contents/{deck_id}")
    assert res.status_code == 204
    deck_row = await db_session.get(Content, deck_id)
    assert deck_row is not None  # 개인 콘텐츠 삭제 경로에서 chat 덱은 보호
    occ = (
        (
            await db_session.execute(
                select(ItemOccurrence).where(ItemOccurrence.content_id == deck_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(occ) == 1  # 수집분 보존

    # 큐에서 제외 + 덱 한정 학습은 404
    queue = (await client.get("/api/study/queue")).json()
    assert not [
        q for q in queue["questions"] if q.get("hint_answer") == "I think I have to work late today"
    ]
    assert (await client.get(f"/api/study/queue?content_id={deck_id}")).status_code == 404

    # lazy sync(카드 재조회)가 몰래 재구독하지 않는다 — 빼기 의사 존중
    summary2 = (await client.get("/api/study/my-phrases")).json()
    assert summary2["subscribed"] is False
    assert summary2["content_id"] == deck_id

    # 재담기 — 내 chat 덱은 private 여도 담기 허용, 카드 진행 그대로 복귀
    res = await client.post(f"/api/my/contents/{deck_id}/subscribe")
    assert res.status_code == 202
    assert (await client.get("/api/study/my-phrases")).json()["subscribed"] is True
    queue2 = (await client.get("/api/study/queue")).json()
    assert [
        q
        for q in queue2["questions"]
        if q.get("hint_answer") == "I think I have to work late today"
    ]


async def test_chat_deck_subscribe_rejects_other_users_deck(client, db_session):
    """타인의 chat 덱은 담기 불가 — 존재 여부도 흘리지 않는 404."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, b)
    await send(client, a.id, "제가 먼저 확인해볼게요", "cid-sub02")
    await send(client, a.id, "제가 먼저 확인해볼게요", "cid-sub02b")
    await seed_translation(db_session, "제가 먼저 확인해볼게요", "Let me check it first")
    other_deck_id = (await client.get("/api/study/my-phrases")).json()["content_id"]

    await login(client, db_session, a)
    res = await client.post(f"/api/my/contents/{other_deck_id}/subscribe")
    assert res.status_code == 404


async def test_assemble_pool_stays_within_my_deck(client, db_session):
    """전역 dedup 으로 같은 문장 항목이 타인 덱에도 걸릴 때, 선다·방해칩 재료는
    **내 덱에서만** 뽑는다 — 타인 채팅 번역 노출 방지 (2026-08-18 전수 점검)."""
    from app.api.study import _chat_deck_sentences
    from app.models import User

    me = User(google_sub="g-pool-a", email="pool-a@example.com", name="A", nickname="A")
    other = User(google_sub="g-pool-b", email="pool-b@example.com", name="B", nickname="B")
    db_session.add_all([me, other])
    await db_session.flush()

    shared = LearningItem(
        item_type="sentence",
        en_text="That sounds good to me",
        ko_text="저는 좋아요",
        normalized_key="that sounds good to me",
    )
    db_session.add(shared)
    my_deck = Content(
        source="chat", visibility="private", title="내 덱", status="ready", created_by=me.id
    )
    other_deck = Content(
        source="chat", visibility="private", title="남 덱", status="ready", created_by=other.id
    )
    db_session.add_all([my_deck, other_deck])
    await db_session.flush()
    db_session.add(ItemOccurrence(item_id=shared.id, content_id=my_deck.id))
    db_session.add(ItemOccurrence(item_id=shared.id, content_id=other_deck.id))
    secret = LearningItem(
        item_type="sentence",
        en_text="My secret salary is huge",
        ko_text="비밀 연봉 이야기",
        normalized_key="my secret salary is huge",
    )
    db_session.add(secret)
    await db_session.flush()
    db_session.add(ItemOccurrence(item_id=secret.id, content_id=other_deck.id))
    await db_session.commit()

    pools = await _chat_deck_sentences(db_session, [shared], me.id)
    assert pools[shared.id] == ["That sounds good to me"]


async def test_weak_mode_includes_chat_sentence_at_low_level(client, db_session):
    """레벨 ≤2 에서 틀린 chat 문장이 오답 정리(배지·세션)에 들어온다 — 큐의
    chat 예외를 오답 정리에도 일관 적용 (2026-08-18 전수 점검)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "오늘 야근해야 할 것 같아", "cid-wk01")
    await send(client, b.id, "오늘 야근해야 할 것 같아", "cid-wk01b")
    await seed_translation(
        db_session, "오늘 야근해야 할 것 같아", "I think I have to work late today"
    )
    await client.get("/api/study/my-phrases")

    queue = (await client.get("/api/study/queue")).json()
    question = next(
        q for q in queue["questions"] if q.get("hint_answer") == "I think I have to work late today"
    )
    submit = await client.post(
        "/api/study/answer",
        json={
            "card_id": question["card_id"],
            "quiz_mode": question["quiz_mode"],
            "answer": "totally wrong",
        },
    )
    assert submit.json()["correct"] is False

    stats = (await client.get("/api/study/stats")).json()
    assert stats["weak_count"] == 1
    weak_queue = (await client.get("/api/study/queue?mode=weak")).json()
    assert [
        q
        for q in weak_queue["questions"]
        if q.get("hint_answer") == "I think I have to work late today"
    ]


async def test_stats_due_excludes_gated_long_sentence(client, db_session):
    """길이 게이트로 대기 중인 9단어+ 문장의 due 카드도 due_count 에서 빠지고
    levels[].locked_due 로 잡힌다 — 레벨 3 승급 시 복귀 (level-format-fit)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    long_en = "Could you please send me the updated file before tomorrow morning"
    await send(client, b.id, "내일 아침 전에 수정된 파일 보내줄 수 있어요", "cid-stat1")
    await send(client, b.id, "내일 아침 전에 수정된 파일 보내줄 수 있어요", "cid-stat1b")
    await seed_translation(db_session, "내일 아침 전에 수정된 파일 보내줄 수 있어요", long_en)
    await client.get("/api/study/my-phrases")
    item_id = (
        await db_session.execute(select(LearningItem.id).where(LearningItem.en_text == long_en))
    ).scalar_one()
    db_session.add(
        ReviewCard(user_id=a.id, item_id=item_id, state="review", due_at=datetime.now(UTC))
    )
    await db_session.commit()

    stats = (await client.get("/api/study/stats")).json()  # 기본 study_level=2
    assert stats["due_count"] == 0
    sentence_row = next(lv for lv in stats["levels"] if lv["item_type"] == "sentence")
    assert sentence_row["locked_due"] == 1

    await client.patch("/api/settings", json={"study_level": 3})
    stats3 = (await client.get("/api/study/stats")).json()
    assert stats3["due_count"] == 1
    sentence_row3 = next(lv for lv in stats3["levels"] if lv["item_type"] == "sentence")
    assert sentence_row3["locked_due"] == 0


async def test_items_flag_level_gated(client, db_session):
    """편집 목록이 길이 게이트 대기 문장에 level_gated 를 표시한다 —
    '레벨 3부터' 배지 재료 (proposal/level-format-fit)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    long_en = "Could you please send me the updated file before tomorrow morning"
    await send(client, b.id, "내일 아침 전에 수정된 파일 보내줄 수 있어요", "cid-flag1")
    await send(client, b.id, "내일 아침 전에 수정된 파일 보내줄 수 있어요", "cid-flag1b")
    await seed_translation(db_session, "내일 아침 전에 수정된 파일 보내줄 수 있어요", long_en)
    await send(client, b.id, "확인하고 연락드릴게요", "cid-flag2")
    await send(client, b.id, "확인하고 연락드릴게요", "cid-flag2b")
    await seed_translation(db_session, "확인하고 연락드릴게요", "Let me check and get back to you")
    await client.get("/api/study/my-phrases")

    items = (await client.get("/api/study/my-phrases/items")).json()
    flags = {it["en_text"]: it["level_gated"] for it in items["items"]}
    assert flags[long_en] is True
    assert flags["Let me check and get back to you"] is False

    await client.patch("/api/settings", json={"study_level": 3})
    items3 = (await client.get("/api/study/my-phrases/items")).json()
    assert all(not it["level_gated"] for it in items3["items"])


async def test_level4_still_uses_typing_format(client, db_session):
    """study_level=4 는 chat 덱 문장도 기존 전체 타이핑(compose)으로 출제된다."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "내일 회의 몇 시에 시작해?", "cid-lvl401")
    await send(client, b.id, "내일 회의 몇 시에 시작해?", "cid-lvl401b")
    await seed_translation(
        db_session, "내일 회의 몇 시에 시작해?", "What time does the meeting start tomorrow?"
    )
    await client.get("/api/study/my-phrases")
    await client.patch("/api/settings", json={"study_level": 4})

    queue = (await client.get("/api/study/queue")).json()
    sentence_qs = [
        q
        for q in queue["questions"]
        if q.get("hint_answer") == "What time does the meeting start tomorrow?"
    ]
    assert len(sentence_qs) == 1
    assert sentence_qs[0]["quiz_mode"] == "compose"
    assert "chips" not in sentence_qs[0]


async def test_items_flow_into_typing_pool_privately(client, db_session, wired_db):  # noqa: F811
    """수집 항목은 문장 게임 풀에 자동 포함 — 본인에게만 (private 가시성)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "이번 주말에 등산 갈래?", "cid-mp00031")
    await send(client, b.id, "이번 주말에 등산 갈래?", "cid-mp00031b")
    await seed_translation(db_session, "이번 주말에 등산 갈래?", "Wanna go hiking this weekend?")
    assert (await client.get("/api/study/my-phrases")).json()["total"] == 1

    mine = await load_sentence_pool(a.id)
    assert any(s["en"] == "Wanna go hiking this weekend?" for s in mine)
    theirs = await load_sentence_pool(b.id)
    assert not any(s["en"] == "Wanna go hiking this weekend?" for s in theirs)


async def test_queue_introduces_my_phrases(client, db_session):
    """복습 큐 신규 도입에 내 표현이 편입된다 (sentence 레벨 활성 시)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "내일 회의 몇 시에 시작해?", "cid-mp00041")
    await send(client, b.id, "내일 회의 몇 시에 시작해?", "cid-mp00041b")
    await seed_translation(
        db_session, "내일 회의 몇 시에 시작해?", "What time does the meeting start tomorrow?"
    )
    await client.get("/api/study/my-phrases")
    # 문장 타입 학습 활성 (기본 levels 1,2 는 단어·숙어)
    await client.patch("/api/settings", json={"levels_enabled": [1, 2, 3, 4]})

    queue = (await client.get("/api/study/queue")).json()
    # 문장 문항은 compose/sentence_assemble (prompt_ko=내 원문, hint_answer=학습언어 번역문)
    answers = {q.get("hint_answer") or "" for q in queue["questions"]}
    assert any("meeting" in t for t in answers)


async def test_deck_study_works_with_default_levels(client, db_session):
    """기본 레벨(단어·숙어)이어도 내 말투 덱 한정 학습은 문장이 나온다 (2026-08-12 빈 세션 보고)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "오늘 야근해야 할 것 같아", "cid-mp00061")
    await send(client, b.id, "오늘 야근해야 할 것 같아", "cid-mp00061b")
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
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "이 문장은 빼고 싶어요", "cid-mp00071")
    await send(client, b.id, "이 문장은 빼고 싶어요", "cid-mp00071b")
    await seed_translation(db_session, "이 문장은 빼고 싶어요", "I want to remove this one")
    items = (await client.get("/api/study/my-phrases/items")).json()["items"]
    assert len(items) == 1

    res = await client.delete(f"/api/study/my-phrases/{items[0]['id']}")
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


async def test_new_item_anonymizes_names_in_original(client, db_session, monkeypatch):
    """학습 카드 원문의 실명은 평범한 이름으로 치환 — 직급은 유지 (2026-08-12 요청)."""
    from app.services import translation as translation_service

    async def fake_anonymize(text, lang):
        assert lang == "ko"
        return text.replace("혜인", "민지")

    monkeypatch.setattr(translation_service, "anonymize_names", fake_anonymize)

    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "혜인 팀장님 오늘 회의 몇 시예요?", "cid-mp00081")
    await send(client, b.id, "혜인 팀장님 오늘 회의 몇 시예요?", "cid-mp00081b")
    await seed_translation(
        db_session, "혜인 팀장님 오늘 회의 몇 시예요?", "Hailey, what time is the meeting today?"
    )

    res = (await client.get("/api/study/my-phrases")).json()
    assert res["recent"][0]["ko"] == "민지 팀장님 오늘 회의 몇 시예요?"  # 이름만 치환, 직급 유지


async def test_refresh_updates_texts_in_place(client, db_session, monkeypatch):
    """품질 새로고침 — 항목 ID 유지한 채 실명 치환 + 재번역으로 텍스트 갱신."""
    from app.services import translation as translation_service

    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "혜인님 담에 커피 마셔요", "cid-mp00091")
    await send(client, b.id, "혜인님 담에 커피 마셔요", "cid-mp00091b")
    await seed_translation(
        db_session, "혜인님 담에 커피 마셔요", "Let's have coffee tomorrow, Hye-in"
    )
    first = (await client.get("/api/study/my-phrases/items")).json()["items"]
    old_id = first[0]["id"]

    async def fake_anonymize(text, lang):
        return text.replace("혜인", "민지")

    async def fake_chain(text, target):
        return "Let's grab coffee next time, Hailey", "haiku"

    monkeypatch.setattr(translation_service, "anonymize_names", fake_anonymize)
    monkeypatch.setattr(translation_service, "_translate_via_chain", fake_chain)

    res = await client.post("/api/study/my-phrases/refresh")
    assert res.status_code == 200
    assert res.json()["updated"] == 1

    items = (await client.get("/api/study/my-phrases/items")).json()["items"]
    assert items[0]["id"] == old_id  # ID 유지 — 복습 진행도 보존
    assert items[0]["en_text"] == "Let's grab coffee next time, Hailey"
    assert items[0]["ko_text"] == "민지님 담에 커피 마셔요"


async def test_deck_item_reuses_global_normalized_key(client, db_session):
    """같은 번역문이 이미 전역 항목으로 있으면 재사용 — Occurrence 만 연결."""
    a, b = await learn_pair(client, db_session)
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
    await send(client, b.id, "정말 고마워 친구야", "cid-mp00051b")
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


async def test_one_time_message_not_collected(client, db_session):
    """길어도 1회 발화는 미채택 — 빈도 2회 이상만 (2026-08-12 기획 점검)."""
    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "이 문장은 충분히 길지만 한 번만 쓴 말입니다", "cid-mp00101")
    await seed_translation(
        db_session, "이 문장은 충분히 길지만 한 번만 쓴 말입니다", "Long but said only once"
    )
    assert (await client.get("/api/study/my-phrases")).json()["total"] == 0


async def test_game_pool_excludes_long_term_mastered(client, db_session, wired_db):  # noqa: F811
    """장기기억(stability 7일+) 도달 문장은 게임 풀에서 제외 (2026-08-12 기획)."""
    from datetime import UTC, datetime

    from app.models import ReviewCard

    a, b = await learn_pair(client, db_session)
    await login(client, db_session, a)
    await send(client, b.id, "이 표현은 이미 익혔어요", "cid-mp00111")
    await send(client, b.id, "이 표현은 이미 익혔어요", "cid-mp00111b")
    await seed_translation(db_session, "이 표현은 이미 익혔어요", "I already mastered this one")
    assert (await client.get("/api/study/my-phrases")).json()["total"] == 1

    pool = await load_sentence_pool(a.id)
    target = next(s for s in pool if s["en"] == "I already mastered this one")

    # 장기기억 도달 (stability 8일) — 풀에서 빠진다
    db_session.add(
        ReviewCard(
            user_id=a.id,
            item_id=target["item_id"],
            state="review",
            stability=8.0,
            due_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    pool_after = await load_sentence_pool(a.id)
    assert not any(s["en"] == "I already mastered this one" for s in pool_after)
