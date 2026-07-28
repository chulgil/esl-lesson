"""데일리 단어 퍼즐 — 채점·결정성·API 흐름 (docs/specs/daily-puzzle.md)."""

from sqlalchemy import select

from app.models import Content, ContentSubscription, ItemOccurrence, LearningItem, User
from app.services import daily_puzzle as dp
from tests.test_study import login


async def seed_puzzle_words(db, words):
    """답 풀은 담기(구독) 가시성을 따른다 — 공용 콘텐츠 출처 + 전 사용자 구독으로 시드."""
    content = Content(source="manual", title="퍼즐 소재", visibility="public", status="ready")
    db.add(content)
    await db.flush()
    for user_id in (await db.execute(select(User.id))).scalars().all():
        db.add(ContentSubscription(content_id=content.id, user_id=user_id))
    for w in words:
        item = LearningItem(
            item_type="word",
            en_text=w,
            ko_text=f"{w}뜻",
            normalized_key=w,
            review_status="approved",
        )
        db.add(item)
        await db.flush()
        db.add(ItemOccurrence(item_id=item.id, content_id=content.id))
    await db.commit()
    return content


def test_grade_duplicate_letters():
    # 정답 "apple": p 두 개 — guess "puppy" 는 p 하나만 y, 나머지 x
    assert dp.grade("apple", "apple") == ["g"] * 5
    assert dp.grade("apple", "plane") == ["y", "y", "y", "x", "g"]
    # p 두 개 중 하나는 g(정위치), 나머지 p 는 y 하나만 — 초과분은 x
    assert dp.grade("apple", "puppy") == ["y", "x", "g", "x", "x"]


def test_pick_word_deterministic_and_stable():
    words = ["apple", "brave", "chair", "dream"]
    first = dp.pick_word(words, "2026-07-15")
    assert dp.pick_word(words, "2026-07-15") == first  # 같은 날 = 같은 답
    # 단어가 추가되어도 답이 잘 안 바뀐다 (랑데부 해싱) — 바뀌지 않는 케이스 검증
    assert dp.pick_word([*words, "zzzzz"], "2026-07-15") in {first, "zzzzz"}


async def test_puzzle_api_flow(client, db_session):
    await login(client, db_session)
    await seed_puzzle_words(db_session, ["apple", "brave", "chair"])

    state = (await client.get("/api/game/puzzle")).json()
    assert state["available"] is True and state["max_tries"] == 6
    length = state["length"]
    assert state["answer"] is None  # 진행 중엔 정답 비공개
    assert state["hint_ko"].endswith("뜻")  # 뜻 힌트는 처음부터 (열람은 UI 버튼 opt-in)
    assert state["hint_first"] is None  # 첫 글자 힌트는 4번 시도부터

    # 길이 불일치 → 422
    bad = await client.post("/api/game/puzzle/guess", json={"word": "a" * (length + 1)})
    assert bad.status_code == 422

    # 오답 5번 + 마지막 오답 → 종료 + 정답 공개
    wrong = "z" * length
    for n in range(6):
        res = await client.post("/api/game/puzzle/guess", json={"word": wrong})
        assert res.status_code == 200
        body = res.json()
        assert body["hint_ko"] is not None
        # 첫 글자 힌트는 4번 시도부터 열림 (정답 단어는 여전히 비공개)
        assert (body["hint_first"] is not None) == (
            body["finished"] or n + 1 >= dp.FIRST_LETTER_AFTER_TRIES
        )
        if not body["finished"]:
            assert body["answer"] is None
    final = res.json()
    assert final["finished"] is True and final["solved"] is False
    assert final["answer"] is not None and final["answer_ko"].endswith("뜻")
    assert final["hint_first"] == final["answer"][0]
    assert len(final["guesses"]) == 6

    # 끝난 뒤 추가 추측 → 409
    res = await client.post("/api/game/puzzle/guess", json={"word": wrong})
    assert res.status_code == 409


async def test_practice_mode_flow(client, db_session):
    """연습 모드 — 무상태 서명 토큰, 무제한, 기록 미저장 (하루 1판 가혹함 완화)."""
    await login(client, db_session)
    await seed_puzzle_words(db_session, ["apple", "brave", "chair", "dream"])

    start = (await client.get("/api/game/puzzle/practice")).json()
    assert start["available"] is True and start["max_tries"] == 6
    assert start["token"] and start["hint_ko"].endswith("뜻")
    # 첫 글자 힌트 — 무상태라 시작 응답에 포함, 노출 시점은 클라이언트 게이트
    assert len(start["hint_first"]) == 1
    length = start["length"]
    token = start["token"]

    # 오답 — 채점만, 정답 비공개
    wrong = "z" * length
    res = await client.post("/api/game/puzzle/practice/guess", json={"token": token, "word": wrong})
    assert res.status_code == 200
    body = res.json()
    assert body["correct"] is False and len(body["marks"]) == length
    assert body["answer"] is None

    # 마지막 시도(final) → 정답·뜻 공개
    res = await client.post(
        "/api/game/puzzle/practice/guess",
        json={"token": token, "word": wrong, "final": True},
    )
    final = res.json()
    assert final["answer"] is not None and final["answer_ko"].endswith("뜻")
    assert final["answer"].startswith(start["hint_first"])

    # 정답 제출 → correct + 공개
    res = await client.post(
        "/api/game/puzzle/practice/guess",
        json={"token": token, "word": final["answer"]},
    )
    body = res.json()
    assert body["correct"] is True and body["marks"] == ["g"] * length
    assert body["answer"] == final["answer"]

    # 길이 불일치 → 422, 토큰 위조 → 400
    res = await client.post(
        "/api/game/puzzle/practice/guess",
        json={"token": token, "word": "a" * (length + 1)},
    )
    assert res.status_code == 422
    res = await client.post(
        "/api/game/puzzle/practice/guess",
        json={"token": token + "x", "word": wrong},
    )
    assert res.status_code == 400


async def test_unsubscribed_words_leave_puzzle_pool(client, db_session):
    """라이브러리에서 뺀 콘텐츠의 단어는 새 퍼즐(데일리·연습) 답 풀에서 빠진다."""
    await login(client, db_session)
    content = await seed_puzzle_words(db_session, ["apple", "brave", "chair"])

    assert (await client.get("/api/game/puzzle")).json()["available"] is True

    # 유일한 소재를 빼면 답 풀이 비어 퍼즐 자체가 내려간다
    assert (await client.delete(f"/api/my/contents/{content.id}")).status_code == 204
    assert (await client.get("/api/game/puzzle")).json()["available"] is False
    assert (await client.get("/api/game/puzzle/practice")).json()["available"] is False

    # 다시 담으면 그대로 복귀
    assert (await client.post(f"/api/my/contents/{content.id}/subscribe")).status_code == 202
    assert (await client.get("/api/game/puzzle")).json()["available"] is True


async def test_started_play_keeps_fixed_answer_after_unsubscribe(client, db_session):
    """이미 시작한 오늘 판은 구독을 빼도 유지 — 정답·뜻 힌트가 플레이 행에 고정."""
    await login(client, db_session)
    content = await seed_puzzle_words(db_session, ["apple", "brave", "chair"])

    length = (await client.get("/api/game/puzzle")).json()["length"]
    first = await client.post("/api/game/puzzle/guess", json={"word": "z" * length})
    assert first.status_code == 200

    assert (await client.delete(f"/api/my/contents/{content.id}")).status_code == 204
    after = (await client.get("/api/game/puzzle")).json()
    assert after["available"] is True
    assert len(after["guesses"]) == 1
    assert after["hint_ko"].endswith("뜻")  # 뜻 힌트도 무필터 조회로 유지
    res = await client.post("/api/game/puzzle/guess", json={"word": "z" * length})
    assert res.status_code == 200  # 진행 중 판은 계속 추측 가능
