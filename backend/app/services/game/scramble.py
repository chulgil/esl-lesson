"""어순 조립 레이스 — 문장 어순 퍼즐 동기 레이스, 1~4인 (docs/specs/scramble-race.md).

타자 레이스와 같은 진행 모델: 전원 동일 문장, 전원 완성(또는 제한시간) 시
다음 문장. 입력만 다르다 — 타이핑 대신 섞인 단어 칩을 올바른 어순으로 탭.
"""

import asyncio
import logging
import random
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.core.db import get_session_factory
from app.models import ScrambleRace
from app.services.game.manager import WordPoolError, review_items
from app.services.game.typing_race import load_sentence_pool, pick_sentences

logger = logging.getLogger(__name__)

Sender = Callable[[dict], Awaitable[None]]

SENTENCE_COUNT = 8
SENTENCE_SECONDS = 60.0  # 어순 판단 사고 시간 — 문장형 게임 공통 최대 1분 (2026-08-10)
COUNTDOWN_SECONDS = 3.0
TICK = 0.1
MAX_PLAYERS = 4
MIN_SENTENCES = 5
MIN_CHIPS = 4  # 너무 짧은 문장은 퍼즐이 안 됨
MAX_CHIPS = 12  # 너무 길면 칩이 화면을 넘침

BASE_SCORE = 100
TIME_BONUS_MAX = 100
MISTAKE_PENALTY = 10
PERFECT_BONUS = 30  # 무실수 완성 — "PERFECT!" 연출과 세트 (게임다움 기획 2026-07-15)
MIN_SENTENCE_SCORE = 30  # 실수 많아도 완성하면 최소 보장 — 포기 방지


def scramble_chips(words: list[str], rng: random.Random) -> list[str]:
    """정답 어순과 다르게 섞는다 (전 단어 동일 등 불가능한 경우만 그대로)."""
    chips = list(words)
    if len(set(words)) < 2:
        return chips
    for _ in range(10):
        rng.shuffle(chips)
        if chips != words:
            return chips
    return chips


def sentence_score(elapsed: float, mistakes: int) -> int:
    """완성 = 기본 100 + 시간 보너스(최대 100) - 실수 10/개 + 무실수 30, 최소 30 보장."""
    bonus = max(0.0, 1.0 - elapsed / SENTENCE_SECONDS)
    raw = BASE_SCORE + int(TIME_BONUS_MAX * bonus) - mistakes * MISTAKE_PENALTY
    if mistakes == 0:
        raw += PERFECT_BONUS
    return max(MIN_SENTENCE_SCORE, raw)


def rank_players(players: list["ScramblerState"]) -> tuple[str | None, int | None]:
    """승자 = 점수 多 → 실수 少 → 누적 시간 少. 전 기준 동률이면 무승부."""
    if len(players) < 2:
        return None, None
    ordered = sorted(players, key=lambda p: (-p.score, p.mistakes, p.total_ms))
    top, second = ordered[0], ordered[1]
    if (top.score, top.mistakes, top.total_ms) == (
        second.score,
        second.mistakes,
        second.total_ms,
    ):
        return None, None
    return top.name, top.user_id


def build_rounds(pool: list[dict], count: int, seed: int) -> list[dict]:
    """문장 → {answer(정답 어순), chips(섞임), ko}. 칩 수 범위 밖 문장은 제외."""
    rng = random.Random(seed)
    fits = [s for s in pool if MIN_CHIPS <= len(s["en"].split()) <= MAX_CHIPS]
    picked = pick_sentences(fits, count, seed)
    rounds = []
    for sentence in picked:
        words = sentence["en"].split()
        rounds.append(
            {
                "answer": words,
                "chips": scramble_chips(words, rng),
                "ko": sentence.get("ko", ""),
                # 오답 복습용 학습 항목 — 정답 텍스트는 answer 로 이미 클라이언트에 있음
                "item_id": sentence.get("item_id", 0),
                "en": sentence["en"],
            }
        )
    return rounds


@dataclass
class ScramblerState:
    user_id: int
    name: str
    send: Sender | None = None
    sentences: int = 0
    mistakes: int = 0
    score: int = 0
    total_ms: int = 0
    placed: int = 0  # 현재 문장에서 맞춘 칩 수 — 상대 진행 표시
    done_current: bool = False
    wrong: list[int] = field(default_factory=list)  # 실수·시간초과 문장 인덱스


@dataclass
class ScrambleSession:
    match_id: int
    code: str | None
    host_id: int
    mode: str  # solo | race
    players: list[ScramblerState]
    rounds: list[dict] = field(default_factory=list)
    started: bool = False
    round_no: int = -1
    round_started: float = 0.0
    task: asyncio.Task | None = None


class ScrambleManager:
    def __init__(self) -> None:
        self.sessions: dict[int, ScrambleSession] = {}
        self.rooms: dict[str, int] = {}
        self.by_user: dict[int, int] = {}

    # --- 진입 ---

    async def solo(self, user_id: int, name: str, send: Sender) -> ScrambleSession:
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
        session.players.append(ScramblerState(user_id=user_id, name=name, send=send))
        self.by_user[user_id] = session.match_id
        await self._broadcast_room(session)

    async def begin(self, user_id: int) -> None:
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

    async def progress(self, user_id: int, idx: int, placed: int) -> None:
        """맞춘 칩 수 보고 — 상대 진행 바에 표시."""
        session = self._session_of(user_id)
        if session is None or not session.started or idx != session.round_no:
            return
        player = next((p for p in session.players if p.user_id == user_id), None)
        if player is None or player.done_current:
            return
        limit = len(session.rounds[idx]["answer"])
        player.placed = min(max(placed, 0), limit)
        await self._broadcast(
            session,
            {"t": "sc.progress", "name": player.name, "placed": player.placed, "total": limit},
            exclude=user_id,
        )

    async def done(self, user_id: int, idx: int, mistakes: int) -> None:
        """문장 완성 — 점수는 서버 시계 기준으로 계산."""
        session = self._session_of(user_id)
        if session is None or not session.started or idx != session.round_no:
            return
        player = next((p for p in session.players if p.user_id == user_id), None)
        if player is None or player.done_current:
            return
        elapsed = time.monotonic() - session.round_started
        gained = sentence_score(elapsed, max(0, mistakes))
        player.done_current = True
        player.placed = len(session.rounds[idx]["answer"])
        player.sentences += 1
        player.mistakes += max(0, mistakes)
        if mistakes > 0:
            player.wrong.append(idx)
        player.score += gained
        player.total_ms += int(elapsed * 1000)
        await self._broadcast(
            session,
            {
                "t": "sc.done_mark",
                "name": player.name,
                "idx": idx,
                "gained": gained,
                "score": player.score,
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
        player = next((p for p in session.players if p.user_id == user_id), None)
        if player is not None:
            player.send = None
            player.done_current = True  # 이탈자가 진행을 막지 않게
        if all(p.send is None for p in session.players):
            if session.task:
                session.task.cancel()
            self._cleanup(session)

    # --- 루프 ---

    async def _start(self, session: ScrambleSession, pool: list[dict]) -> None:
        session.rounds = build_rounds(pool, SENTENCE_COUNT, secrets.randbits(32))
        session.started = True
        await self._save(session, status="playing")
        await self._broadcast(
            session,
            {
                "t": "sc.start",
                "rounds": session.rounds,
                "total": len(session.rounds),
                "sentence_seconds": SENTENCE_SECONDS,
                "countdown": COUNTDOWN_SECONDS,
                "players": [p.name for p in session.players],
            },
        )
        session.task = asyncio.create_task(self._run(session))

    async def _run(self, session: ScrambleSession) -> None:
        try:
            await asyncio.sleep(COUNTDOWN_SECONDS)
            for round_no in range(len(session.rounds)):
                session.round_no = round_no
                session.round_started = time.monotonic()
                for p in session.players:
                    p.done_current = p.send is None  # 이탈자는 자동 통과
                    p.placed = 0
                await self._broadcast(session, {"t": "sc.sentence", "idx": round_no})
                deadline = session.round_started + SENTENCE_SECONDS
                while time.monotonic() < deadline and not all(
                    p.done_current for p in session.players
                ):
                    await asyncio.sleep(TICK)
                # 시간 초과자는 점수 없음 — 다음 문장에서 재도전
                for p in session.players:
                    if not p.done_current:
                        p.wrong.append(round_no)
            await self._finish(session, aborted=False)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("scramble race crashed match=%s", session.match_id)
            await self._finish(session, aborted=True)

    async def _finish(self, session: ScrambleSession, aborted: bool) -> None:
        results = [
            {
                "name": p.name,
                "sentences": p.sentences,
                "mistakes": p.mistakes,
                "score": p.score,
            }
            for p in session.players
        ]
        winner, winner_id = rank_players(session.players)
        await self._save(session, "aborted" if aborted else "finished", winner_id, results)
        if not aborted:
            # 오답 복습은 본인에게만 — 결과 화면 원탭 학습 추가용
            for p in session.players:
                items = review_items([session.rounds[i] for i in p.wrong])
                if items:
                    await self._safe_send(p, {"t": "sc.review", "items": items})
        await self._broadcast(
            session,
            {"t": "sc.end", "results": results, "winner": winner, "aborted": aborted},
        )
        self._cleanup(session)

    # --- 헬퍼 ---

    async def _pool(self, user_id: int) -> list[dict]:
        pool = await load_sentence_pool(user_id)
        fits = [s for s in pool if MIN_CHIPS <= len(s["en"].split()) <= MAX_CHIPS]
        if len(fits) < MIN_SENTENCES:
            raise WordPoolError("sentences_insufficient")
        return fits

    async def _new_session(
        self, user_id: int, name: str, send: Sender, mode: str, code: str | None
    ) -> ScrambleSession:
        async with get_session_factory()() as db:
            row = ScrambleRace(mode=mode, status="waiting", player1_id=user_id)
            db.add(row)
            await db.commit()
            match_id = row.id
        session = ScrambleSession(
            match_id=match_id,
            code=code,
            host_id=user_id,
            mode=mode,
            players=[ScramblerState(user_id=user_id, name=name, send=send)],
        )
        self.sessions[match_id] = session
        self.by_user[user_id] = match_id
        return session

    async def _save(
        self,
        session: ScrambleSession,
        status: str,
        winner_id: int | None = None,
        results: list[dict] | None = None,
    ) -> None:
        try:
            async with get_session_factory()() as db:
                row = await db.get(ScrambleRace, session.match_id)
                if row is None:
                    return
                row.status = status
                if len(session.players) > 1:
                    row.player2_id = session.players[1].user_id
                if results is not None:
                    row.winner_id = winner_id
                    row.p1_score = session.players[0].score
                    if len(session.players) > 1:
                        row.p2_score = session.players[1].score
                    row.stats = {f"p{i + 1}": r for i, r in enumerate(results)}
                    row.ended_at = datetime.now(UTC)
                await db.commit()
        except Exception:
            logger.exception("failed to save scramble race %s", session.match_id)

    async def _broadcast_room(self, session: ScrambleSession) -> None:
        await self._broadcast(
            session,
            {
                "t": "sc.room",
                "code": session.code,
                "host": session.players[0].name if session.players else "",
                "players": [p.name for p in session.players],
            },
        )

    async def _broadcast(
        self, session: ScrambleSession, message: dict, exclude: int | None = None
    ) -> None:
        for player in session.players:
            if player.user_id == exclude:
                continue
            await self._safe_send(player, message)

    @staticmethod
    async def _safe_send(player: ScramblerState, message: dict) -> None:
        if player.send is None:
            return
        try:
            await player.send(message)
        except Exception:
            player.send = None  # 전송 실패 = 이탈 간주, 레이스는 계속

    def _cleanup(self, session: ScrambleSession) -> None:
        for player in session.players:
            if self.by_user.get(player.user_id) == session.match_id:
                del self.by_user[player.user_id]
        if session.code:
            self.rooms.pop(session.code, None)
        self.sessions.pop(session.match_id, None)

    def _session_of(self, user_id: int) -> ScrambleSession | None:
        match_id = self.by_user.get(user_id)
        return self.sessions.get(match_id) if match_id is not None else None

    def _leave_if_idle(self, user_id: int) -> None:
        session = self._session_of(user_id)
        if session is not None and not session.started:
            self.detach(user_id)


scrambler = ScrambleManager()
