"""데일리 단어 퍼즐 — 하루 1판 워들 (docs/specs/daily-puzzle.md).

전원 같은 단어(날짜 결정적) — 친구와 "몇 번 만에 맞혔나" 비교가 리텐션 훅.
정답은 클라이언트에 내리지 않고 서버가 채점한다.
"""

import hashlib
from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LearningItem

KST = timezone(timedelta(hours=9))
MAX_TRIES = 6
MIN_LEN, MAX_LEN = 4, 8
HINT_AFTER_TRIES = 2  # 뜻 힌트 해금 — 막힌 사람 구제, 정답 단어는 계속 비공개


def today_kst() -> date:
    return datetime.now(UTC).astimezone(KST).date()


def pick_word(words: list[str], day: str) -> str:
    """날짜 결정적 선택 (랑데부 해싱) — 풀에 단어가 추가되어도 답이 거의 안 바뀐다."""
    return min(words, key=lambda w: hashlib.md5(f"{day}:{w}".encode()).hexdigest())


def grade(answer: str, guess: str) -> list[str]:
    """워들 채점 g/y/x — 중복 글자는 남은 개수만큼만 y."""
    marks = ["x"] * len(answer)
    remaining: dict[str, int] = {}
    for i, ch in enumerate(answer):
        if guess[i] == ch:
            marks[i] = "g"
        else:
            remaining[ch] = remaining.get(ch, 0) + 1
    for i, ch in enumerate(guess):
        if marks[i] == "g":
            continue
        if remaining.get(ch, 0) > 0:
            marks[i] = "y"
            remaining[ch] -= 1
    return marks


async def candidates(db: AsyncSession) -> dict[str, str]:
    """퍼즐 후보 — 승인된 단어 중 4~8자 순수 알파벳. {word: 뜻}."""
    rows = (
        await db.execute(
            select(LearningItem.en_text, LearningItem.ko_text).where(
                LearningItem.item_type == "word",
                LearningItem.review_status == "approved",
            )
        )
    ).all()
    words: dict[str, str] = {}
    for en, ko in rows:
        w = (en or "").strip().lower()
        if w.isascii() and w.isalpha() and MIN_LEN <= len(w) <= MAX_LEN:
            words.setdefault(w, ko or "")
    return words


async def puzzle_of_day(db: AsyncSession, day: date) -> tuple[str, str] | None:
    """(정답, 뜻) — 후보가 없으면 None."""
    pool = await candidates(db)
    if not pool:
        return None
    word = pick_word(sorted(pool), day.isoformat())
    return word, pool[word]
