"""장기 기억 도달 마이크로 보상 — answer 응답 long_term_reached.

기획: docs/proposal/user-journey-motivation-2026-08.md P0 ① / 스펙: learning.md
"""

from datetime import UTC, datetime, timedelta

from app.services.fsrs_service import crossed_long_term
from tests.test_study import login, seed_items


def test_crossed_long_term_boundary():
    # 처음부터 임계 이상으로 굳음 (Easy 첫 리뷰 등)
    assert crossed_long_term(None, 15.0, True) is True
    # 임계 아래에서 위로 교차
    assert crossed_long_term(6.0, 8.0, True) is True
    # 이미 장기 기억이던 카드 — 재도달 아님
    assert crossed_long_term(8.0, 20.0, True) is False
    # 아직 임계 미만
    assert crossed_long_term(None, 3.0, True) is False
    # 오답은 굳음이 아니다
    assert crossed_long_term(6.0, 8.0, False) is False


async def test_answer_reports_no_long_term_on_first_review(client, db_session):
    """새 카드 첫 정답(Good, 안정도 ~3일)은 아직 장기 기억이 아니다."""
    await login(client, db_session)
    await seed_items(db_session, count=1)

    queue = (await client.get("/api/study/queue")).json()
    question = queue["questions"][0]
    item_ko = (
        await client.post(
            "/api/study/answer",
            json={
                "card_id": question["card_id"],
                "quiz_mode": question["quiz_mode"],
                "answer": "오답이어도무방",
                "duration_ms": 8000,
            },
        )
    ).json()
    assert item_ko["long_term_reached"] is False


async def test_answer_reports_long_term_when_crossing(client, db_session):
    """임계 직전(stability<7) 카드가 정답 리뷰로 임계를 넘으면 true."""
    from fsrs import Card, Rating, Scheduler

    from app.models import ReviewCard

    user = await login(client, db_session)
    items = await seed_items(db_session, count=1)

    now = datetime.now(UTC)
    # fsrs 상태는 Easy 1회(안정도 ~15일)로 만들어 다음 정답 후에도 임계 이상 유지,
    # 프로젝션 stability 는 임계 미만으로 두어 "교차" 조건을 결정적으로 만든다
    fsrs_card = Card(due=now - timedelta(days=30))
    fsrs_card, _ = Scheduler().review_card(
        fsrs_card, Rating.Easy, review_datetime=now - timedelta(days=30)
    )
    card = ReviewCard(
        user_id=user.id,
        item_id=items[0].id,
        state="review",
        due_at=now,
        stability=5.0,
        reps=1,
        fsrs_json={"card": fsrs_card.to_dict()},
    )
    db_session.add(card)
    await db_session.commit()

    res = (
        await client.post(
            "/api/study/answer",
            json={
                "card_id": card.id,
                "quiz_mode": "choice_en2ko",
                "answer": items[0].ko_text,
                "duration_ms": 8000,
            },
        )
    ).json()
    assert res["correct"] is True
    assert res["long_term_reached"] is True
