"""데일리 단어 퍼즐 — 채점·결정성·API 흐름 (docs/specs/daily-puzzle.md)."""

from app.models import LearningItem
from app.services import daily_puzzle as dp
from tests.test_study import login


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
    db_session.add_all(
        [
            LearningItem(
                item_type="word",
                en_text=w,
                ko_text=f"{w}뜻",
                normalized_key=w,
                review_status="approved",
            )
            for w in ("apple", "brave", "chair")
        ]
    )
    await db_session.commit()

    state = (await client.get("/api/game/puzzle")).json()
    assert state["available"] is True and state["max_tries"] == 6
    length = state["length"]
    assert state["answer"] is None  # 진행 중엔 정답 비공개

    # 길이 불일치 → 422
    bad = await client.post("/api/game/puzzle/guess", json={"word": "a" * (length + 1)})
    assert bad.status_code == 422

    # 오답 5번 + 마지막 오답 → 종료 + 정답 공개
    wrong = "z" * length
    for _ in range(6):
        res = await client.post("/api/game/puzzle/guess", json={"word": wrong})
        assert res.status_code == 200
    final = res.json()
    assert final["finished"] is True and final["solved"] is False
    assert final["answer"] is not None and final["answer_ko"].endswith("뜻")
    assert len(final["guesses"]) == 6

    # 끝난 뒤 추가 추측 → 409
    res = await client.post("/api/game/puzzle/guess", json={"word": wrong})
    assert res.status_code == 409
