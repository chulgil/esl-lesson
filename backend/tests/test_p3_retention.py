"""P3 리텐션 — 개인 기록 경신 판정 + 유사단어 원탭 학습 추가."""

from sqlalchemy import select

from app.models import ReviewCard
from app.services.game import records
from tests.test_study import login, seed_items


def test_bests_from_matches_both_sides():
    """p1/p2 어느 쪽이든 본인 기록만 집계."""
    rows = [
        # (player1_id, p1_score, p2_score, stats)
        (7, 100, 50, {"p1": {"max_combo": 5, "wpm": 30}, "p2": {"max_combo": 9, "wpm": 99}}),
        (3, 80, 120, {"p1": {"max_combo": 2, "wpm": 10}, "p2": {"max_combo": 7, "wpm": 41}}),
    ]
    bests = records.bests_from_matches(7, rows)
    assert bests["score"] == 120  # 두 번째 판은 p2 로 참가
    assert bests["max_combo"] == 7
    assert bests["wpm"] == 41


def test_new_records_only_when_beaten():
    prev = {"score": 100, "max_combo": 7, "wpm": 41}
    assert records.new_records(prev, {"score": 150, "max_combo": 7, "wpm": 42}) == [
        "score",
        "wpm",
    ]
    assert records.new_records(prev, {"score": 100, "max_combo": 3, "wpm": 10}) == []
    # 첫 판(이전 0)이라도 0 점은 경신 아님
    assert records.new_records({"score": 0, "max_combo": 0, "wpm": 0}, {"score": 0}) == []


async def test_add_card_one_tap(client, db_session):
    """유사단어 원탭 추가 — 신규 생성, 중복은 기존 카드 반환, 미승인 404."""
    user = await login(client, db_session)
    items = await seed_items(db_session, count=1)

    res = await client.post("/api/cards", json={"item_id": items[0].id})
    assert res.status_code == 200
    body = res.json()
    assert body["added"] is True

    again = await client.post("/api/cards", json={"item_id": items[0].id})
    assert again.json() == {"added": False, "card_id": body["card_id"]}

    cards = (
        (await db_session.execute(select(ReviewCard).where(ReviewCard.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(cards) == 1

    missing = await client.post("/api/cards", json={"item_id": 999_999})
    assert missing.status_code == 404
