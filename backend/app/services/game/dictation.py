"""받아쓰기 배틀 — 유튜브 원음 듣고 문장 받아쓰기, 1~4인 (docs/specs/dictation-battle.md).

어순 레이스와 같은 동기 진행 모델. 차이: 정답 문장을 클라이언트에 내리지
않고 **서버가 채점**한다 (단어 단위 유사도). 라운드 종료 시 정답 공개.
"""

import asyncio
import difflib
import logging
import re
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import get_session_factory
from app.models import Content, DictationRace, ItemOccurrence, LearningItem, TranscriptSegment
from app.services.game.manager import WordPoolError, review_items
from app.services.game.typing_race import pick_sentences
from app.services.visibility import visible_item_clause

logger = logging.getLogger(__name__)

Sender = Callable[[dict], Awaitable[None]]

SENTENCE_COUNT = 6
SENTENCE_SECONDS = 60.0  # 듣기 반복 + 타이핑 시간 — 문장형 게임 공통 최대 1분 (2026-08-10)
REVEAL_SECONDS = 4.0  # 라운드 사이 정답 공개 시간
COUNTDOWN_SECONDS = 3.0
TICK = 0.1
MAX_PLAYERS = 4
MIN_SENTENCES = 5
MAX_SENTENCE_CHARS = 120

BASE_MAX = 100  # 정확도 100% = 100
TIME_BONUS_MAX = 50  # 정확도 90%+ 만 시간 보너스
BONUS_MIN_ACCURACY = 0.9


def normalize_words(text: str) -> list[str]:
    return [w for w in re.sub(r"[^a-z0-9' ]", " ", text.lower()).split() if w]


def word_accuracy(answer: str, attempt: str) -> float:
    """단어 단위 유사도 (0~1) — 대소문자·문장부호 무시."""
    target, got = normalize_words(answer), normalize_words(attempt)
    if not target:
        return 0.0
    return round(difflib.SequenceMatcher(None, target, got).ratio(), 3)


def sentence_score(accuracy: float, elapsed: float) -> int:
    base = int(round(accuracy * BASE_MAX))
    if accuracy < BONUS_MIN_ACCURACY:
        return base
    ratio = max(0.0, 1.0 - elapsed / SENTENCE_SECONDS)
    return base + int(TIME_BONUS_MAX * ratio)


def rank_players(players: list["DictatorState"]) -> tuple[str | None, int | None]:
    """승자 = 점수 多 → 평균 정확도 高 → 누적 시간 少."""
    if len(players) < 2:
        return None, None
    ordered = sorted(players, key=lambda p: (-p.score, -p.accuracy_sum, p.total_ms))
    top, second = ordered[0], ordered[1]
    if (top.score, top.accuracy_sum, top.total_ms) == (
        second.score,
        second.accuracy_sum,
        second.total_ms,
    ):
        return None, None
    return top.name, top.user_id


async def load_dictation_pool(user_id: int) -> list[dict]:
    """유튜브 구간이 있는 문장만 — {en, video_id, start_ms, end_ms}."""
    async with get_session_factory()() as db:
        rows = (
            await db.execute(
                select(
                    LearningItem.id,
                    LearningItem.en_text,
                    LearningItem.ko_text,
                    Content.youtube_video_id,
                    TranscriptSegment.start_ms,
                    TranscriptSegment.end_ms,
                )
                .join(ItemOccurrence, ItemOccurrence.item_id == LearningItem.id)
                .join(Content, Content.id == ItemOccurrence.content_id)
                .join(TranscriptSegment, TranscriptSegment.id == ItemOccurrence.segment_id)
                .where(
                    LearningItem.item_type == "sentence",
                    visible_item_clause(user_id),
                    Content.youtube_video_id.is_not(None),
                    TranscriptSegment.start_ms.is_not(None),
                )
                .distinct()
                .limit(300)
            )
        ).all()
    pool = []
    for item_id, en, ko, video_id, start_ms, end_ms in rows:
        en = (en or "").strip()
        if en and len(en) <= MAX_SENTENCE_CHARS:
            pool.append(
                {
                    "item_id": item_id,
                    "en": en,
                    "ko": (ko or "").strip(),
                    "video_id": video_id,
                    "start_ms": start_ms,
                    "end_ms": end_ms or start_ms + 5000,
                }
            )
    return pool


@dataclass
class DictatorState:
    user_id: int
    name: str
    send: Sender | None = None
    sentences: int = 0
    accuracy_sum: float = 0.0
    score: int = 0
    total_ms: int = 0
    done_current: bool = False
    wrong: list[int] = field(default_factory=list)  # 부정확·미제출 문장 인덱스


@dataclass
class DictationSession:
    match_id: int
    code: str | None
    host_id: int
    mode: str  # solo | race
    players: list[DictatorState]
    rounds: list[dict] = field(default_factory=list)
    started: bool = False
    round_no: int = -1
    round_started: float = 0.0
    task: asyncio.Task | None = None


class DictationManager:
    def __init__(self) -> None:
        self.sessions: dict[int, DictationSession] = {}
        self.rooms: dict[str, int] = {}
        self.by_user: dict[int, int] = {}

    # --- 진입 (어순 레이스와 동일 패턴) ---

    async def solo(self, user_id: int, name: str, send: Sender) -> DictationSession:
        self._leave_if_idle(user_id)
        pool = await self._pool(user_id)
        session = await self._new_session(user_id, name, send, "solo", None)
        await self._start(session, pool)
        return session

    async def create(self, user_id: int, name: str, send: Sender) -> str:
        self._leave_if_idle(user_id)
        await self._pool(user_id)
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
        session.players.append(DictatorState(user_id=user_id, name=name, send=send))
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

    async def submit(self, user_id: int, idx: int, text: str) -> None:
        """받아쓰기 제출 — 서버 채점 (정답은 클라이언트에 없음)."""
        session = self._session_of(user_id)
        if session is None or not session.started or idx != session.round_no:
            return
        player = next((p for p in session.players if p.user_id == user_id), None)
        if player is None or player.done_current:
            return
        answer = session.rounds[idx]["en"]
        elapsed = time.monotonic() - session.round_started
        accuracy = word_accuracy(answer, text[:300])
        gained = sentence_score(accuracy, elapsed)
        player.done_current = True
        player.sentences += 1
        player.accuracy_sum += accuracy
        if accuracy < 1.0:
            player.wrong.append(idx)
        player.score += gained
        player.total_ms += int(elapsed * 1000)
        await self._broadcast(
            session,
            {
                "t": "dt.done_mark",
                "name": player.name,
                "idx": idx,
                "accuracy": accuracy,
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
            player.done_current = True
        if all(p.send is None for p in session.players):
            if session.task:
                session.task.cancel()
            self._cleanup(session)

    # --- 루프 ---

    async def _start(self, session: DictationSession, pool: list[dict]) -> None:
        session.rounds = pick_sentences(pool, SENTENCE_COUNT, secrets.randbits(32))
        session.started = True
        await self._save(session, status="playing")
        await self._broadcast(
            session,
            {
                "t": "dt.start",
                # 정답(en)은 내리지 않는다 — 클립 정보만
                "clips": [
                    {
                        "video_id": r["video_id"],
                        "start_ms": r["start_ms"],
                        "end_ms": r["end_ms"],
                    }
                    for r in session.rounds
                ],
                "total": len(session.rounds),
                "sentence_seconds": SENTENCE_SECONDS,
                "countdown": COUNTDOWN_SECONDS,
                "players": [p.name for p in session.players],
            },
        )
        session.task = asyncio.create_task(self._run(session))

    async def _run(self, session: DictationSession) -> None:
        try:
            await asyncio.sleep(COUNTDOWN_SECONDS)
            for round_no in range(len(session.rounds)):
                session.round_no = round_no
                session.round_started = time.monotonic()
                for p in session.players:
                    p.done_current = p.send is None
                await self._broadcast(session, {"t": "dt.sentence", "idx": round_no})
                deadline = session.round_started + SENTENCE_SECONDS
                while time.monotonic() < deadline and not all(
                    p.done_current for p in session.players
                ):
                    await asyncio.sleep(TICK)
                for p in session.players:
                    if not p.done_current:
                        p.wrong.append(round_no)
                # 정답 공개 — 학습 순간 (미제출자는 0점 통과)
                session.round_no = -1  # 공개 중 제출 차단
                await self._broadcast(
                    session,
                    {"t": "dt.reveal", "idx": round_no, "en": session.rounds[round_no]["en"]},
                )
                await asyncio.sleep(REVEAL_SECONDS)
            await self._finish(session, aborted=False)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("dictation battle crashed match=%s", session.match_id)
            await self._finish(session, aborted=True)

    async def _finish(self, session: DictationSession, aborted: bool) -> None:
        results = [
            {
                "name": p.name,
                "sentences": p.sentences,
                "accuracy": round(p.accuracy_sum / max(1, p.sentences), 3),
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
                    await self._safe_send(p, {"t": "dt.review", "items": items})
        await self._broadcast(
            session,
            {"t": "dt.end", "results": results, "winner": winner, "aborted": aborted},
        )
        self._cleanup(session)

    # --- 헬퍼 ---

    async def _pool(self, user_id: int) -> list[dict]:
        pool = await load_dictation_pool(user_id)
        if len(pool) < MIN_SENTENCES:
            raise WordPoolError("sentences_insufficient")
        return pool

    async def _new_session(
        self, user_id: int, name: str, send: Sender, mode: str, code: str | None
    ) -> DictationSession:
        async with get_session_factory()() as db:
            row = DictationRace(mode=mode, status="waiting", player1_id=user_id)
            db.add(row)
            await db.commit()
            match_id = row.id
        session = DictationSession(
            match_id=match_id,
            code=code,
            host_id=user_id,
            mode=mode,
            players=[DictatorState(user_id=user_id, name=name, send=send)],
        )
        self.sessions[match_id] = session
        self.by_user[user_id] = match_id
        return session

    async def _save(
        self,
        session: DictationSession,
        status: str,
        winner_id: int | None = None,
        results: list[dict] | None = None,
    ) -> None:
        try:
            async with get_session_factory()() as db:
                row = await db.get(DictationRace, session.match_id)
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
            logger.exception("failed to save dictation battle %s", session.match_id)

    async def _broadcast_room(self, session: DictationSession) -> None:
        await self._broadcast(
            session,
            {
                "t": "dt.room",
                "code": session.code,
                "host": session.players[0].name if session.players else "",
                "players": [p.name for p in session.players],
            },
        )

    async def _broadcast(
        self, session: DictationSession, message: dict, exclude: int | None = None
    ) -> None:
        for player in session.players:
            if player.user_id == exclude:
                continue
            await self._safe_send(player, message)

    @staticmethod
    async def _safe_send(player: DictatorState, message: dict) -> None:
        if player.send is None:
            return
        try:
            await player.send(message)
        except Exception:
            player.send = None

    def _cleanup(self, session: DictationSession) -> None:
        for player in session.players:
            if self.by_user.get(player.user_id) == session.match_id:
                del self.by_user[player.user_id]
        if session.code:
            self.rooms.pop(session.code, None)
        self.sessions.pop(session.match_id, None)

    def _session_of(self, user_id: int) -> DictationSession | None:
        match_id = self.by_user.get(user_id)
        return self.sessions.get(match_id) if match_id is not None else None

    def _leave_if_idle(self, user_id: int) -> None:
        session = self._session_of(user_id)
        if session is not None and not session.started:
            self.detach(user_id)


dictator = DictationManager()
