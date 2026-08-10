"""영문 타자연습 — 문장 동기 레이스, 1~4인 (docs/specs/typing-race.md).

모두가 같은 문장을 치고, 전원이 완성하면 다음 문장으로 넘어간다.
문장당 제한시간이 있어 한 명이 멈춰도 레이스는 진행된다.
"""

import asyncio
import logging
import random
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import get_session_factory
from app.models import Content, ItemOccurrence, LearningItem, TypingRace
from app.services.game.manager import WordPoolError, review_items
from app.services.visibility import visible_item_clause

logger = logging.getLogger(__name__)

Sender = Callable[[dict], Awaitable[None]]

SENTENCE_COUNT = 10
SENTENCE_SECONDS = 60.0  # 문장당 제한 최대 1분 — 한 명이 멈춰도 레이스 진행 (2026-08-10 30→60)
COUNTDOWN_SECONDS = 3.0
TICK = 0.1
MAX_PLAYERS = 4
MIN_SENTENCES = 5
MAX_SENTENCE_CHARS = (
    80  # 긴 문장 금지 (2026-08-10 사용자) — 1분 안에 느린 타이피스트도 완주 가능한 길이
)


def wpm_for(chars: int, seconds: float) -> float:
    """표준 WPM = (정타 수 / 5) / 분."""
    if seconds <= 0:
        return 0.0
    return round((chars / 5.0) / (seconds / 60.0), 1)


def accuracy_for(chars: int, errors: int) -> float:
    total = chars + errors
    if total == 0:
        return 1.0
    return round(chars / total, 3)


def pick_sentences(pool: list[str], count: int, seed: int) -> list[str]:
    """풀에서 count 개 선택 — 부족하면 순환 (짧은 풀도 레이스 가능)."""
    rng = random.Random(seed)
    shuffled = list(pool)
    rng.shuffle(shuffled)
    picked: list[str] = []
    while len(picked) < count:
        picked.extend(shuffled[: count - len(picked)])
    return picked[:count]


def rank_players(players: list["RacerState"]) -> tuple[str | None, int | None]:
    """승자 = 완성 문장 多 → 정타 多 → 누적 시간 少. 전 기준 동률이면 무승부."""
    if len(players) < 2:
        return None, None
    ordered = sorted(players, key=lambda p: (-p.sentences, -p.chars, p.total_ms))
    top, second = ordered[0], ordered[1]
    if (top.sentences, top.chars, top.total_ms) == (
        second.sentences,
        second.chars,
        second.total_ms,
    ):
        return None, None
    return top.name, top.user_id


async def load_sentence_pool(user_id: int) -> list[dict]:
    """가시성 규칙(공용 승인 ∪ 내 개인)을 지키는 (영문, 뜻) 문장 풀."""
    async with get_session_factory()() as db:
        rows = (
            await db.execute(
                select(LearningItem.id, LearningItem.en_text, LearningItem.ko_text)
                .join(ItemOccurrence, ItemOccurrence.item_id == LearningItem.id)
                .join(Content, Content.id == ItemOccurrence.content_id)
                .where(
                    LearningItem.item_type == "sentence",
                    visible_item_clause(user_id),
                )
                .distinct()
                .limit(300)
            )
        ).all()
    return [
        {"item_id": item_id, "en": en.strip(), "ko": (ko or "").strip()}
        for item_id, en, ko in rows
        if en and len(en.strip()) <= MAX_SENTENCE_CHARS
    ]


@dataclass
class RacerState:
    user_id: int
    name: str
    send: Sender | None = None
    chars: int = 0
    errors: int = 0
    sentences: int = 0
    total_ms: int = 0
    # 현재 문장 진행 (정타 prefix 길이) — 다른 플레이어 줄에 표시
    live_chars: int = 0
    done_current: bool = False
    peak_cpm: float = 0.0  # 최고 타속 (타/분) — 결과 화면용
    wrong: list[int] = field(default_factory=list)  # 오타·시간초과 문장 인덱스


@dataclass
class RaceSession:
    match_id: int
    code: str | None
    host_id: int
    mode: str  # solo | race
    players: list[RacerState]
    sentences: list[str] = field(default_factory=list)
    started: bool = False
    race_started: float = 0.0
    round_no: int = -1
    round_started: float = 0.0
    task: asyncio.Task | None = None


class TypingRaceManager:
    def __init__(self) -> None:
        self.sessions: dict[int, RaceSession] = {}
        self.rooms: dict[str, int] = {}
        self.by_user: dict[int, int] = {}

    # --- 진입 ---

    async def solo(self, user_id: int, name: str, send: Sender) -> RaceSession:
        self._leave_if_idle(user_id)
        pool = await self._pool(user_id)
        session = await self._new_session(user_id, name, send, "solo", None)
        await self._start(session, pool)
        return session

    async def create(self, user_id: int, name: str, send: Sender) -> str:
        self._leave_if_idle(user_id)
        await self._pool(user_id)  # 시작 전에 문장 부족을 미리 알림
        code = secrets.token_hex(3).upper()
        session = await self._new_session(user_id, name, send, "race", code)
        self.rooms[code] = session.match_id
        await self._broadcast_room(session)
        return code

    async def join(self, user_id: int, name: str, send: Sender, code: str) -> None:
        session = self.sessions.get(self.rooms.get(code.upper(), -1))
        if session is None or session.started:
            await send({"t": "error", "code": "room_not_found"})
            return
        if len(session.players) >= MAX_PLAYERS:
            await send({"t": "error", "code": "room_full"})
            return
        self._leave_if_idle(user_id)
        session.players.append(RacerState(user_id=user_id, name=name, send=send))
        self.by_user[user_id] = session.match_id
        await self._broadcast_room(session)

    async def begin(self, user_id: int) -> None:
        """호스트만 시작 (2인 이상). 솔로는 자동 시작이라 불필요."""
        session = self._session_of(user_id)
        if (
            session is None
            or session.started
            or session.host_id != user_id
            or len(session.players) < 2
        ):
            return
        pool = await self._pool(session.host_id)
        if session.code:
            self.rooms.pop(session.code, None)
        await self._start(session, pool)

    # --- 플레이 ---

    async def typing(self, user_id: int, idx: int, chars: int) -> None:
        """진행 보고 (정타 prefix 길이) — 다른 플레이어 줄에 실시간 표시."""
        session = self._session_of(user_id)
        if session is None or not session.started or idx != session.round_no:
            return
        racer = next((p for p in session.players if p.user_id == user_id), None)
        if racer is None or racer.done_current:
            return
        limit = len(session.sentences[idx]["en"])
        racer.live_chars = min(max(chars, 0), limit)
        racer.peak_cpm = max(racer.peak_cpm, self._live_wpm(session, racer) * 5)
        await self._broadcast(
            session,
            {
                "t": "tp.typing",
                "name": racer.name,
                "chars": racer.live_chars,
                "wpm": self._live_wpm(session, racer),
            },
            exclude=user_id,
        )

    async def done(self, user_id: int, idx: int, chars: int, errors: int) -> None:
        """현재 문장 완성 — 전원 완성 시 루프가 다음 문장으로 넘긴다."""
        session = self._session_of(user_id)
        if session is None or not session.started or idx != session.round_no:
            return
        racer = next((p for p in session.players if p.user_id == user_id), None)
        if racer is None or racer.done_current:
            return
        sentence_len = len(session.sentences[idx]["en"])
        racer.done_current = True
        racer.live_chars = sentence_len
        racer.chars += min(max(chars, 0), sentence_len)
        racer.errors += max(errors, 0)
        if errors > 0:
            racer.wrong.append(idx)
        racer.sentences += 1
        racer.total_ms += int((time.monotonic() - session.round_started) * 1000)
        racer.peak_cpm = max(racer.peak_cpm, self._live_wpm(session, racer) * 5)
        await self._broadcast(
            session,
            {
                "t": "tp.done_mark",
                "name": racer.name,
                "idx": idx,
                "wpm": self._live_wpm(session, racer),
            },
        )

    def detach(self, user_id: int) -> None:
        session = self._session_of(user_id)
        if session is None:
            return
        self.by_user.pop(user_id, None)
        if not session.started:
            session.players = [p for p in session.players if p.user_id != user_id]
            if session.host_id == user_id or not session.players:
                if session.code:
                    self.rooms.pop(session.code, None)
                self.sessions.pop(session.match_id, None)
            return
        racer = next((p for p in session.players if p.user_id == user_id), None)
        if racer is not None:
            racer.send = None
            racer.done_current = True  # 이탈자가 진행을 막지 않게
        if all(p.send is None for p in session.players):
            if session.task:
                session.task.cancel()
            self._cleanup(session)

    # --- 루프 ---

    async def _start(self, session: RaceSession, pool: list[str]) -> None:
        session.sentences = pick_sentences(pool, SENTENCE_COUNT, secrets.randbits(32))
        session.started = True
        await self._save(session, status="playing")
        await self._broadcast(
            session,
            {
                "t": "tp.start",
                "sentences": session.sentences,
                "total": len(session.sentences),
                "sentence_seconds": SENTENCE_SECONDS,
                "countdown": COUNTDOWN_SECONDS,
                "players": [p.name for p in session.players],
            },
        )
        session.task = asyncio.create_task(self._run(session))

    async def _run(self, session: RaceSession) -> None:
        try:
            await asyncio.sleep(COUNTDOWN_SECONDS)
            session.race_started = time.monotonic()
            for round_no in range(len(session.sentences)):
                session.round_no = round_no
                session.round_started = time.monotonic()
                for p in session.players:
                    p.done_current = p.send is None  # 이탈자는 자동 통과
                    p.live_chars = 0
                await self._broadcast(session, {"t": "tp.sentence", "idx": round_no})
                deadline = session.round_started + SENTENCE_SECONDS
                # 전원 완성 or 문장 제한시간 → 다음 문장
                while time.monotonic() < deadline and not all(
                    p.done_current for p in session.players
                ):
                    await asyncio.sleep(TICK)
                for p in session.players:
                    if not p.done_current:
                        # 시간 초과 — 부분 진행(정타 prefix)만 인정
                        p.chars += p.live_chars
                        p.total_ms += int(SENTENCE_SECONDS * 1000)
                        p.wrong.append(round_no)
            await self._finish(session, aborted=False)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("typing race crashed match=%s", session.match_id)
            await self._finish(session, aborted=True)

    async def _finish(self, session: RaceSession, aborted: bool) -> None:
        results = [
            {
                "name": p.name,
                "chars": p.chars,
                "sentences": p.sentences,
                "wpm": wpm_for(p.chars, max(0.1, p.total_ms / 1000)) if p.total_ms else 0.0,
                "accuracy": accuracy_for(p.chars, p.errors),
            }
            for p in session.players
        ]
        winner, winner_id = rank_players(session.players)
        await self._save(session, "aborted" if aborted else "finished", winner_id, results)
        if not aborted:
            # 오답 복습은 본인에게만 — 결과 화면 원탭 학습 추가용
            for p in session.players:
                items = review_items([session.sentences[i] for i in p.wrong])
                if items:
                    await self._safe_send(p, {"t": "tp.review", "items": items})
        await self._broadcast(
            session,
            {"t": "tp.end", "results": results, "winner": winner, "aborted": aborted},
        )
        self._cleanup(session)

    # --- 헬퍼 ---

    @staticmethod
    def _live_wpm(session: RaceSession, racer: RacerState) -> float:
        elapsed = max(0.5, time.monotonic() - (session.race_started or time.monotonic()))
        return wpm_for(racer.chars + racer.live_chars, elapsed)

    async def _pool(self, user_id: int) -> list[str]:
        pool = await load_sentence_pool(user_id)
        if len(pool) < MIN_SENTENCES:
            raise WordPoolError("sentences_insufficient")
        return pool

    async def _new_session(
        self, user_id: int, name: str, send: Sender, mode: str, code: str | None
    ) -> RaceSession:
        async with get_session_factory()() as db:
            row = TypingRace(mode=mode, status="waiting", player1_id=user_id)
            db.add(row)
            await db.commit()
            match_id = row.id
        session = RaceSession(
            match_id=match_id,
            code=code,
            host_id=user_id,
            mode=mode,
            players=[RacerState(user_id=user_id, name=name, send=send)],
        )
        self.sessions[match_id] = session
        self.by_user[user_id] = match_id
        return session

    async def _save(
        self,
        session: RaceSession,
        status: str,
        winner_id: int | None = None,
        results: list[dict] | None = None,
    ) -> None:
        try:
            async with get_session_factory()() as db:
                row = await db.get(TypingRace, session.match_id)
                if row is None:
                    return
                row.status = status
                if len(session.players) > 1:
                    row.player2_id = session.players[1].user_id
                if results is not None:
                    row.winner_id = winner_id
                    row.p1_chars = session.players[0].chars
                    if len(session.players) > 1:
                        row.p2_chars = session.players[1].chars
                    row.stats = {f"p{i + 1}": r for i, r in enumerate(results)}
                    row.ended_at = datetime.now(UTC)
                await db.commit()
        except Exception:
            logger.exception("failed to save typing race %s", session.match_id)

    async def _broadcast_room(self, session: RaceSession) -> None:
        await self._broadcast(
            session,
            {
                "t": "tp.room",
                "code": session.code,
                "host": session.players[0].name if session.players else "",
                "players": [p.name for p in session.players],
            },
        )

    async def _broadcast(
        self, session: RaceSession, message: dict, exclude: int | None = None
    ) -> None:
        for player in session.players:
            if player.user_id == exclude:
                continue
            await self._safe_send(player, message)

    @staticmethod
    async def _safe_send(player: RacerState, message: dict) -> None:
        if player.send is None:
            return
        try:
            await player.send(message)
        except Exception:
            player.send = None  # 전송 실패 = 이탈 간주, 레이스는 계속

    def _cleanup(self, session: RaceSession) -> None:
        for player in session.players:
            if self.by_user.get(player.user_id) == session.match_id:
                del self.by_user[player.user_id]
        if session.code:
            self.rooms.pop(session.code, None)
        self.sessions.pop(session.match_id, None)

    def _session_of(self, user_id: int) -> RaceSession | None:
        match_id = self.by_user.get(user_id)
        return self.sessions.get(match_id) if match_id is not None else None

    def _leave_if_idle(self, user_id: int) -> None:
        session = self._session_of(user_id)
        if session is not None and not session.started:
            self.detach(user_id)


racer = TypingRaceManager()
