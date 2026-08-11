"""리텐션 팩 — 책갈피(스트릭 보호) + 오늘의 미션 (docs/proposal/retention-plan.md).

메커니즘은 타 서비스에서 검증된 것을 차용하되(아이디어 영역),
명칭·문구·표현은 노트 테마의 자체 언어를 쓴다 (저작권 안전선).
"""

import hashlib
from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BingoMatch,
    DailyPuzzlePlay,
    DictationRace,
    GameMatch,
    QuestCompletion,
    QuizRoyaleMatch,
    QuizRoyalePlayer,
    ReviewCard,
    ReviewLog,
    ScrambleRace,
    StreakSaverUse,
    TypingRace,
    UserSettings,
)

KST = timezone(timedelta(hours=9))
SAVER_MAX = 2
STREAK_WINDOW_DAYS = 400  # api/study.py stats 의 daily 잔디 조회 창(400일)과 동일 —
# 단일 근거로 맞춰야 그 경계에서 스트릭이 강제 절단되지 않는다 (2026-08-11 픽스,
# 2026-08-03 잔디 확장 시 60일로 미동기화됐던 값 동기화)


def iso_week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def try_award_saver(settings: UserSettings, reviews_today: int, today: date) -> bool:
    """오늘 목표 달성 시 책갈피 지급 — 같은 ISO 주 1개, 최대 SAVER_MAX.

    호출자는 변경 시 commit 책임. 경합해도 같은 값으로 수렴(주 가드)이라 안전.
    """
    if reviews_today < settings.daily_goal:
        return False
    week = iso_week(today)
    if settings.saver_award_week == week or settings.streak_savers >= SAVER_MAX:
        return False
    settings.streak_savers += 1
    settings.saver_award_week = week
    return True


async def streak_with_savers(
    db: AsyncSession, user_id: int, settings: UserSettings, daily: dict[str, int], today: date
) -> tuple[int, list[str]]:
    """스트릭 계산 + 공백은 보유 책갈피로 자동 소모해 이어붙임.

    책갈피 날은 +0 (리셋만 방지, 공짜 진행 없음). 공백 너머(과거 방향)에
    학습일이 있을 때만 소모한다 — 이어질 스트릭이 없으면 낭비라 아낀다.
    returns (streak_days, 보호된 날짜 iso 목록 — 잔디 표기용)
    """
    since = today - timedelta(days=STREAK_WINDOW_DAYS)
    used: set[str] = {
        d.isoformat()
        for d in (
            await db.execute(
                select(StreakSaverUse.day).where(
                    StreakSaverUse.user_id == user_id, StreakSaverUse.day >= since
                )
            )
        ).scalars()
    }

    new_uses: list[date] = []
    savers = settings.streak_savers
    streak = 0
    cursor = today
    if daily.get(cursor.isoformat(), 0) == 0:
        cursor -= timedelta(days=1)  # 오늘은 아직 안 끝났으니 소모 대상이 아니다

    while cursor >= since:
        key = cursor.isoformat()
        if daily.get(key, 0) > 0:
            streak += 1
            cursor -= timedelta(days=1)
            continue
        if key in used:
            cursor -= timedelta(days=1)  # 책갈피로 보호된 날 — 연속 유지, +0
            continue
        # 공백 구간 — 소모 가능 길이인지, 너머에 학습일이 있는지 확인
        gap: list[date] = []
        probe = cursor
        while (
            probe >= since
            and daily.get(probe.isoformat(), 0) == 0
            and probe.isoformat() not in used
            and len(gap) <= savers
        ):
            gap.append(probe)
            probe -= timedelta(days=1)
        anchor_alive = daily.get(probe.isoformat(), 0) > 0 or probe.isoformat() in used
        if gap and len(gap) <= savers and anchor_alive:
            for day in gap:
                used.add(day.isoformat())
                new_uses.append(day)
            savers -= len(gap)
            cursor = probe
            continue
        break

    if new_uses:
        settings.streak_savers = savers
        for day in new_uses:
            db.add(StreakSaverUse(user_id=user_id, day=day))
        try:
            await db.commit()
        except IntegrityError:
            # 동시 stats 호출 경합 — 먼저 저장된 쪽을 채택하고 이번 계산값은 유지.
            # rollback 이 settings 를 만료시키므로 재로드 — 호출자(stats)가 이어서
            # settings 필드를 읽어도 안전 (MissingGreenlet 방지, 2026-08-05 스윕)
            await db.rollback()
            await db.refresh(settings)

    saved_days = sorted(d for d in used)
    return streak, saved_days


# ---------- 오늘의 미션 ----------

# key: (제목, 설명, 목표, XP)
QUEST_DEFS: dict[str, tuple[str, str, int, int]] = {
    "review_10": ("복습 10개", "오늘 복습 10개를 완료해요", 10, 20),
    "accuracy_80": ("정확도 사수", "정답률 80% 이상으로 10개 복습해요", 10, 30),
    "game_1": ("게임 1판", "아무 게임이나 1판 즐겨요", 1, 30),
    "puzzle_try": ("데일리 퍼즐", "오늘의 단어 퍼즐에 도전해요", 1, 20),
    "new_cards_5": ("새 카드 5개", "새 카드 5개를 만나요", 5, 20),
}
CORE_QUEST = "review_10"  # 코어 루프(복습)는 매일 고정
ALL_DONE_KEY = "all_done"
ALL_DONE_XP = 30


def pick_quests(user_id: int, day: str) -> list[str]:
    """복습 코어 1 + 풀에서 2개 — 날짜·유저 결정적 (랑데부 해싱, 데일리 퍼즐 패턴)."""
    pool = [k for k in QUEST_DEFS if k != CORE_QUEST]
    extras = sorted(pool, key=lambda k: hashlib.md5(f"{day}:{user_id}:{k}".encode()).hexdigest())
    return [CORE_QUEST, *extras[:2]]


async def _quest_progress(
    db: AsyncSession, user_id: int, keys: list[str], day_start: datetime, today: date
) -> dict[str, int]:
    """미션 진행도 — 전부 기존 로그에서 파생 (별도 추적 테이블 없음)."""
    progress: dict[str, int] = {}
    if "review_10" in keys or "accuracy_80" in keys:
        rows = (
            await db.execute(
                select(ReviewLog.correct).where(
                    ReviewLog.user_id == user_id, ReviewLog.reviewed_at >= day_start
                )
            )
        ).scalars()
        results = list(rows)
        total = len(results)
        correct = sum(1 for c in results if c)
        progress["review_10"] = total
        # 정확도 미션: 10개 이상 + 80% — current 는 "조건을 지키며 진행한 수"
        acc_ok = total > 0 and correct / total >= 0.8
        progress["accuracy_80"] = min(total, QUEST_DEFS["accuracy_80"][2]) if acc_ok else 0
    if "game_1" in keys:
        counts = []
        for stmt in (
            select(func.count(GameMatch.id)).where(
                or_(GameMatch.player1_id == user_id, GameMatch.player2_id == user_id),
                GameMatch.status == "finished",
                GameMatch.created_at >= day_start,
            ),
            select(func.count(TypingRace.id)).where(
                or_(TypingRace.player1_id == user_id, TypingRace.player2_id == user_id),
                TypingRace.status == "finished",
                TypingRace.created_at >= day_start,
            ),
            select(func.count(ScrambleRace.id)).where(
                or_(ScrambleRace.player1_id == user_id, ScrambleRace.player2_id == user_id),
                ScrambleRace.status == "finished",
                ScrambleRace.created_at >= day_start,
            ),
            select(func.count(DictationRace.id)).where(
                or_(DictationRace.player1_id == user_id, DictationRace.player2_id == user_id),
                DictationRace.status == "finished",
                DictationRace.created_at >= day_start,
            ),
            select(func.count(BingoMatch.id)).where(
                or_(BingoMatch.player1_id == user_id, BingoMatch.player2_id == user_id),
                BingoMatch.status == "finished",
                BingoMatch.created_at >= day_start,
            ),
            select(func.count(QuizRoyalePlayer.id))
            .join(QuizRoyaleMatch, QuizRoyaleMatch.id == QuizRoyalePlayer.match_id)
            .where(
                QuizRoyalePlayer.user_id == user_id,
                QuizRoyaleMatch.status == "finished",
                QuizRoyaleMatch.created_at >= day_start,
            ),
        ):
            counts.append((await db.execute(stmt)).scalar_one())
        progress["game_1"] = sum(counts)
    if "puzzle_try" in keys:
        played = (
            await db.execute(
                select(func.count(DailyPuzzlePlay.id)).where(
                    DailyPuzzlePlay.user_id == user_id, DailyPuzzlePlay.day == today
                )
            )
        ).scalar_one()
        progress["puzzle_try"] = played
    if "new_cards_5" in keys:
        progress["new_cards_5"] = (
            await db.execute(
                select(func.count(ReviewCard.id)).where(
                    ReviewCard.user_id == user_id, ReviewCard.created_at >= day_start
                )
            )
        ).scalar_one()
    return progress


async def compute_quests(db: AsyncSession, user_id: int, now: datetime | None = None) -> dict:
    """오늘의 미션 상태 계산 + 새로 완료된 미션을 원장에 적립 (멱등)."""
    now = now or datetime.now(UTC)
    today = now.astimezone(KST).date()
    day_start = datetime.combine(today, datetime.min.time(), tzinfo=KST).astimezone(UTC)

    keys = pick_quests(user_id, today.isoformat())
    progress = await _quest_progress(db, user_id, keys, day_start, today)

    recorded: set[str] = {
        k
        for k in (
            await db.execute(
                select(QuestCompletion.quest_key).where(
                    QuestCompletion.user_id == user_id, QuestCompletion.day == today
                )
            )
        ).scalars()
    }

    items = []
    new_rows: list[QuestCompletion] = []
    for key in keys:
        title, desc, target, xp = QUEST_DEFS[key]
        current = progress.get(key, 0)
        done = current >= target
        if done and key not in recorded:
            new_rows.append(QuestCompletion(user_id=user_id, day=today, quest_key=key, xp=xp))
        items.append(
            {
                "key": key,
                "title": title,
                "desc": desc,
                "target": target,
                "current": min(current, target),
                "done": done,
                "xp": xp,
            }
        )

    all_done = all(item["done"] for item in items)
    if all_done and ALL_DONE_KEY not in recorded:
        new_rows.append(
            QuestCompletion(user_id=user_id, day=today, quest_key=ALL_DONE_KEY, xp=ALL_DONE_XP)
        )

    if new_rows:
        for row in new_rows:
            db.add(row)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()  # 동시 호출 경합 — 먼저 적립된 쪽을 채택

    return {
        "date": today.isoformat(),
        "items": items,
        "all_done": all_done,
        "all_done_xp": ALL_DONE_XP,
    }


async def quest_bonus_xp(db: AsyncSession, user_id: int) -> int:
    """미션 보너스 XP 누계 — stats XP 에 합산."""
    return (
        await db.execute(
            select(func.coalesce(func.sum(QuestCompletion.xp), 0)).where(
                QuestCompletion.user_id == user_id
            )
        )
    ).scalar_one()
