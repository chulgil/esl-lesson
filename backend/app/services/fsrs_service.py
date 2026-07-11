"""FSRS 스케줄링 래퍼 (docs/specs/learning.md).

review_cards.fsrs_json 에 py-fsrs Card 직렬화본을 원본으로 저장하고,
due_at/state/reps/lapses 컬럼은 조회용 프로젝션으로 동기화한다.
"""

from datetime import UTC, datetime

from fsrs import Card, Rating, Scheduler, State

from app.models import ReviewCard

STATE_NAMES = {
    State.Learning: "learning",
    State.Review: "review",
    State.Relearning: "relearning",
}

# 응답 시간 기준 (ms) — 선다형 / 입력형
CHOICE_SLOW_MS = 12_000
CHOICE_FAST_MS = 4_000
TYPED_SLOW_MS = 40_000
TYPED_FAST_MS = 15_000

TYPED_MODES = ("compose",)


def compute_rating(
    correct: bool, duration_ms: int | None, quiz_mode: str, fast_streak: int
) -> tuple[int, int]:
    """퀴즈 결과 -> FSRS rating 자동 산출. (rating, 새 fast_streak) 반환."""
    if not correct:
        return Rating.Again.value, 0
    if duration_ms is None:
        return Rating.Good.value, 0

    typed = quiz_mode in TYPED_MODES
    slow = TYPED_SLOW_MS if typed else CHOICE_SLOW_MS
    fast = TYPED_FAST_MS if typed else CHOICE_FAST_MS

    if duration_ms > slow:
        return Rating.Hard.value, 0
    if duration_ms < fast:
        streak = fast_streak + 1
        if streak >= 2:
            return Rating.Easy.value, streak
        return Rating.Good.value, streak
    return Rating.Good.value, 0


def apply_review(
    card_row: ReviewCard,
    rating: int,
    desired_retention: float,
    now: datetime | None = None,
) -> dict:
    """FSRS 리뷰 적용: fsrs_json 갱신 + 프로젝션 컬럼 동기화. 로그 필드 반환."""
    now = now or datetime.now(UTC)
    scheduler = Scheduler(desired_retention=desired_retention)

    stored = card_row.fsrs_json or {}
    if stored.get("card"):
        card = Card.from_dict(stored["card"])
    else:
        card = Card(due=now)

    state_before = card_row.state
    # 자기평가 보정(/study/rate)용 직전 스냅샷 (docs/specs/learning.md 레벨 4)
    prev = {
        "card": stored.get("card"),
        "state": card_row.state,
        "reps": card_row.reps,
        "lapses": card_row.lapses,
        "last_review_at": card_row.last_review_at.isoformat() if card_row.last_review_at else None,
    }
    card, _log = scheduler.review_card(card, Rating(rating), review_datetime=now)

    scheduled_days = (card.due - now).total_seconds() / 86400
    elapsed_days = (
        (now - card_row.last_review_at).total_seconds() / 86400 if card_row.last_review_at else 0.0
    )

    card_row.fsrs_json = {**stored, "card": card.to_dict(), "prev": prev}
    card_row.state = STATE_NAMES[card.state]
    card_row.due_at = card.due
    card_row.stability = card.stability
    card_row.difficulty = card.difficulty
    card_row.reps += 1
    if rating == Rating.Again.value:
        card_row.lapses += 1
    card_row.last_review_at = now

    return {
        "state_before": state_before,
        "scheduled_days": scheduled_days,
        "elapsed_days": elapsed_days,
    }


def get_fast_streak(card_row: ReviewCard) -> int:
    return int((card_row.fsrs_json or {}).get("fast_streak", 0))


def set_fast_streak(card_row: ReviewCard, streak: int) -> None:
    card_row.fsrs_json = {**(card_row.fsrs_json or {}), "fast_streak": streak}
