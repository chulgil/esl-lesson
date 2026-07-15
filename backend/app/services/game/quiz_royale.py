"""스피드 퀴즈 로얄 — 최대 4인 라운드제 버저 퀴즈 (docs/proposal/quiz-royale.md).

테트리스와 달리 실시간 낙하 tick 이 없다 — 라운드 이벤트 기반이라
방 하나당 asyncio 태스크 1개 + 0.05초 폴링으로 충분히 가볍다.
"""

import asyncio
import logging
import math
import random
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import get_session_factory
from app.models import LearningItem, QuizRoyaleMatch, QuizRoyalePlayer
from app.services import embeddings
from app.services.game.manager import WordPoolError, select_word_pool
from app.services.visibility import visible_item_clause

logger = logging.getLogger(__name__)

Sender = Callable[[dict], Awaitable[None]]

ROUNDS = 10
ROUND_SECONDS = 10.0
REVEAL_SECONDS = 3.0
TICK = 0.05
MAX_PLAYERS = 4
MIN_POOL = 15  # 정답 10 + 오답 선지 겹침 여유
BOT_NAMES = ("봇 알파", "봇 브라보", "봇 찰리")


@dataclass
class Question:
    prompt: str
    choices: list[str]
    answer: str


@dataclass
class QuizPlayer:
    user_id: int | None  # None = 봇
    name: str
    send: Sender | None = None
    score: int = 0
    bot_level: int = 0


@dataclass
class QuizSession:
    match_id: int
    code: str | None
    host_id: int
    mode: str  # solo | room
    players: list[QuizPlayer]
    variant: str = "meaning"  # meaning | nuance (임베딩 odd-one-out)
    content_ids: list[int] | None = None
    questions: list[Question] = field(default_factory=list)
    started: bool = False
    round_no: int = -1
    round_started: float = 0.0
    # player index -> (정답 여부, 경과 초)
    answers: dict[int, tuple[bool, float]] = field(default_factory=dict)
    task: asyncio.Task | None = None
    rng: random.Random = field(default_factory=random.Random)


def build_questions(
    pool: list[tuple[int, str, str]], rounds: int, rng: random.Random
) -> list[Question]:
    """(id, en, ko) 풀에서 4지선다 생성 — 방향 랜덤, 오답은 같은 풀의 같은 언어."""
    picks = rng.sample(pool, min(rounds, len(pool)))
    questions = []
    for item_id, en, ko in picks:
        en2ko = rng.random() < 0.5
        answer = ko if en2ko else en
        others = [p for p in pool if p[0] != item_id]
        rng.shuffle(others)
        distractors: list[str] = []
        for _, o_en, o_ko in others:
            value = o_ko if en2ko else o_en
            if value != answer and value not in distractors:
                distractors.append(value)
            if len(distractors) == 3:
                break
        choices = [answer, *distractors]
        rng.shuffle(choices)
        questions.append(Question(prompt=en if en2ko else ko, choices=choices, answer=answer))
    return questions


MIN_NUANCE_WORDS = 20


async def build_nuance_questions(
    db, user_id: int, rounds: int, rng: random.Random
) -> list["Question"]:
    """뉘앙스 저격 — 임베딩 최근접 2개+앵커(비슷한 3) vs 먼 단어 1 (odd-one-out)."""
    if not embeddings.enabled(db):
        raise WordPoolError("nuance_unavailable")
    rows = (
        await db.execute(
            select(LearningItem.id, LearningItem.en_text)
            .where(LearningItem.item_type == "word", visible_item_clause(user_id))
            .limit(300)
        )
    ).all()
    if len(rows) < MIN_NUANCE_WORDS:
        raise WordPoolError("words_insufficient")
    order = list(rows)
    rng.shuffle(order)
    questions: list[Question] = []
    for item_id, en in order:
        try:
            sims = await embeddings.similar_items(db, item_id, k=2)
        except Exception:
            logger.exception("nuance similar_items failed item=%s", item_id)
            break
        if len(sims) < 2:
            continue
        similar = [en, sims[0]["en_text"], sims[1]["en_text"]]
        sim_ids = {item_id, sims[0]["id"], sims[1]["id"]}
        far = [r for r in rows if r[0] not in sim_ids and r[1] not in similar]
        if not far:
            continue
        odd = far[rng.randrange(len(far))]
        choices = [*similar, odd[1]]
        rng.shuffle(choices)
        questions.append(
            Question(prompt="넷 중 뜻이 가장 다른 하나는?", choices=choices, answer=odd[1])
        )
        if len(questions) == rounds:
            break
    if len(questions) < 3:
        raise WordPoolError("nuance_unavailable")
    return questions


def score_for(elapsed: float, limit: float | None = None) -> int:
    """정답 점수 = 50 + ⌈50 x 남은시간/제한⌉ (50~100). 오답/미제출은 호출부에서 0."""
    limit = limit or ROUND_SECONDS
    remaining = max(0.0, limit - elapsed)
    return 50 + math.ceil(50 * remaining / limit)


def ranking(players: list[QuizPlayer]) -> list[dict]:
    """점수 내림차순 + 동점 공동 순위."""
    ordered = sorted(players, key=lambda p: -p.score)
    result: list[dict] = []
    prev_score: int | None = None
    prev_rank = 0
    for i, p in enumerate(ordered, start=1):
        rank = prev_rank if p.score == prev_score else i
        result.append(
            {
                "user_id": p.user_id,
                "name": p.name,
                "score": p.score,
                "rank": rank,
                "is_bot": p.user_id is None,
            }
        )
        prev_score, prev_rank = p.score, rank
    return result


def _bot_plan(level: int, rng: random.Random) -> tuple[float, bool]:
    """봇의 (응답 시각, 정답 여부) — 레벨이 높을수록 빠르고 정확."""
    delay = min(max(rng.gauss(7.5 - level, 1.5), 1.0), ROUND_SECONDS - 0.5)
    correct = rng.random() < 0.35 + 0.1 * level
    return delay, correct


class QuizRoyaleManager:
    def __init__(self) -> None:
        self.sessions: dict[int, QuizSession] = {}
        self.rooms: dict[str, int] = {}  # code -> match_id
        self.by_user: dict[int, int] = {}

    # --- 진입 ---

    async def solo(
        self,
        user_id: int,
        name: str,
        send: Sender,
        bot_level: int = 3,
        bots: int = 1,
        content_ids: list[int] | None = None,
        variant: str = "meaning",
    ) -> QuizSession:
        """나 + 봇 1~3 — 만들자마자 바로 시작."""
        self._leave_if_idle(user_id)
        pool = [] if variant == "nuance" else await self._load_pool(user_id, content_ids)
        session = await self._new_session(user_id, name, send, "solo", None, content_ids)
        session.variant = variant
        for i in range(min(max(bots, 1), MAX_PLAYERS - 1)):
            session.players.append(QuizPlayer(user_id=None, name=BOT_NAMES[i], bot_level=bot_level))
        await self._broadcast_room(session)
        await self._begin(session, pool)
        return session

    async def create(
        self,
        user_id: int,
        name: str,
        send: Sender,
        content_ids: list[int] | None = None,
        variant: str = "meaning",
    ) -> str:
        self._leave_if_idle(user_id)
        if variant != "nuance":
            await self._load_pool(user_id, content_ids)  # 시작 전에 풀 부족을 미리 알림
        code = secrets.token_hex(3).upper()
        session = await self._new_session(user_id, name, send, "room", code, content_ids)
        session.variant = variant
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
        session.players.append(QuizPlayer(user_id=user_id, name=name, send=send))
        self.by_user[user_id] = session.match_id
        await self._broadcast_room(session)

    async def start(self, user_id: int) -> None:
        """호스트만 시작 가능. 2인 미만이면 무시."""
        session = self._session_of(user_id)
        if (
            session is None
            or session.started
            or session.host_id != user_id
            or len(session.players) < 2
        ):
            return
        pool = (
            []
            if session.variant == "nuance"
            else await self._load_pool(session.host_id, session.content_ids)
        )
        if session.code:
            self.rooms.pop(session.code, None)
        await self._begin(session, pool)

    # --- 플레이 ---

    async def answer(self, user_id: int, answer: str) -> None:
        session = self._session_of(user_id)
        if session is None or not session.started or session.round_no < 0:
            return
        idx = self._index_of(session, user_id)
        if idx is None or idx in session.answers:
            return
        elapsed = time.monotonic() - session.round_started
        if elapsed > ROUND_SECONDS:
            return
        question = session.questions[session.round_no]
        session.answers[idx] = (answer == question.answer, elapsed)
        await self._broadcast(session, {"t": "qr.answered", "name": session.players[idx].name})

    def detach(self, user_id: int) -> None:
        """접속 종료 — 대기실이면 제거, 진행 중이면 미제출로 계속."""
        session = self._session_of(user_id)
        if session is None:
            return
        self.by_user.pop(user_id, None)
        if not session.started:
            session.players = [p for p in session.players if p.user_id != user_id]
            humans = [p for p in session.players if p.user_id is not None]
            if session.host_id == user_id or not humans:
                if session.code:
                    self.rooms.pop(session.code, None)
                self.sessions.pop(session.match_id, None)
            return
        idx = self._index_of(session, user_id)
        if idx is not None:
            session.players[idx].send = None
        if all(p.send is None for p in session.players if p.user_id is not None):
            if session.task:
                session.task.cancel()
            self._cleanup(session)

    # --- 루프 ---

    async def _begin(self, session: QuizSession, pool: list[tuple[int, str, str]]) -> None:
        if session.variant == "nuance":
            async with get_session_factory()() as db:
                session.questions = await build_nuance_questions(
                    db, session.host_id, ROUNDS, session.rng
                )
        else:
            session.questions = build_questions(pool, ROUNDS, session.rng)
        session.started = True
        await self._save(session, status="playing")
        session.task = asyncio.create_task(self._run(session))

    async def _run(self, session: QuizSession) -> None:
        try:
            for round_no, question in enumerate(session.questions):
                session.round_no = round_no
                session.answers = {}
                session.round_started = time.monotonic()
                plans = {
                    idx: _bot_plan(p.bot_level, session.rng)
                    for idx, p in enumerate(session.players)
                    if p.user_id is None
                }
                await self._broadcast(
                    session,
                    {
                        "t": "qr.round",
                        "no": round_no + 1,
                        "total": len(session.questions),
                        "prompt": question.prompt,
                        "choices": question.choices,
                        "seconds": ROUND_SECONDS,
                    },
                )
                deadline = session.round_started + ROUND_SECONDS
                while time.monotonic() < deadline and len(session.answers) < len(session.players):
                    now = time.monotonic() - session.round_started
                    for idx, (delay, correct) in plans.items():
                        if idx not in session.answers and now >= delay:
                            session.answers[idx] = (correct, delay)
                            await self._broadcast(
                                session, {"t": "qr.answered", "name": session.players[idx].name}
                            )
                    await asyncio.sleep(TICK)

                gains: dict[str, int] = {}
                for idx, (correct, elapsed) in session.answers.items():
                    points = score_for(elapsed) if correct else 0
                    session.players[idx].score += points
                    gains[session.players[idx].name] = points
                await self._broadcast(
                    session,
                    {
                        "t": "qr.reveal",
                        "no": round_no + 1,
                        "answer": question.answer,
                        "gains": gains,
                        "scores": ranking(session.players),
                    },
                )
                await asyncio.sleep(REVEAL_SECONDS)
            await self._finish(session, aborted=False)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("quiz royale loop crashed match=%s", session.match_id)
            await self._finish(session, aborted=True)

    async def _finish(self, session: QuizSession, aborted: bool) -> None:
        final = ranking(session.players)
        await self._save(session, status="aborted" if aborted else "finished", ranking_=final)
        await self._broadcast(session, {"t": "qr.end", "ranking": final, "aborted": aborted})
        self._cleanup(session)

    # --- 헬퍼 ---

    async def _new_session(
        self,
        user_id: int,
        name: str,
        send: Sender,
        mode: str,
        code: str | None,
        content_ids: list[int] | None,
    ) -> QuizSession:
        async with get_session_factory()() as db:
            row = QuizRoyaleMatch(host_id=user_id, mode=mode, status="waiting")
            db.add(row)
            await db.commit()
            match_id = row.id
        session = QuizSession(
            match_id=match_id,
            code=code,
            host_id=user_id,
            mode=mode,
            players=[QuizPlayer(user_id=user_id, name=name, send=send)],
            content_ids=content_ids,
        )
        self.sessions[match_id] = session
        self.by_user[user_id] = match_id
        return session

    async def _load_pool(
        self, user_id: int, content_ids: list[int] | None
    ) -> list[tuple[int, str, str]]:
        pool = await select_word_pool(user_id, content_ids)
        if len(pool) < MIN_POOL:
            raise WordPoolError("words_insufficient")
        return pool

    async def _save(
        self, session: QuizSession, status: str, ranking_: list[dict] | None = None
    ) -> None:
        try:
            async with get_session_factory()() as db:
                row = await db.get(QuizRoyaleMatch, session.match_id)
                if row is None:
                    return
                row.status = status
                if ranking_ is not None:
                    row.players = {"players": ranking_}
                    row.ended_at = datetime.now(UTC)
                    # 집계용 정규 행 — JSONB 풀스캔 대체 (봇 제외, DB 감사 2026-07-15)
                    for p in ranking_:
                        if p.get("user_id") is None:
                            continue
                        db.add(
                            QuizRoyalePlayer(
                                match_id=row.id,
                                user_id=p["user_id"],
                                score=int(p.get("score") or 0),
                                rank=p.get("rank"),
                            )
                        )
                await db.commit()
        except Exception:
            logger.exception("failed to save quiz royale %s", session.match_id)

    async def _broadcast_room(self, session: QuizSession) -> None:
        await self._broadcast(
            session,
            {
                "t": "qr.room",
                "code": session.code,
                "mode": session.mode,
                "host": session.players[0].name if session.players else "",
                "players": [{"name": p.name, "is_bot": p.user_id is None} for p in session.players],
            },
        )

    async def _broadcast(self, session: QuizSession, message: dict) -> None:
        for player in session.players:
            if player.send is None:
                continue
            try:
                await player.send(message)
            except Exception:
                player.send = None  # 전송 실패 = 이탈로 간주, 진행은 계속

    def _cleanup(self, session: QuizSession) -> None:
        for player in session.players:
            if player.user_id is not None and self.by_user.get(player.user_id) == session.match_id:
                del self.by_user[player.user_id]
        if session.code:
            self.rooms.pop(session.code, None)
        self.sessions.pop(session.match_id, None)

    def _session_of(self, user_id: int) -> QuizSession | None:
        match_id = self.by_user.get(user_id)
        return self.sessions.get(match_id) if match_id is not None else None

    def _index_of(self, session: QuizSession, user_id: int) -> int | None:
        for idx, player in enumerate(session.players):
            if player.user_id == user_id:
                return idx
        return None

    def _leave_if_idle(self, user_id: int) -> None:
        """시작 전 세션에 남아 있으면 정리 — 새 판 진입 허용."""
        session = self._session_of(user_id)
        if session is not None and not session.started:
            self.detach(user_id)


royale = QuizRoyaleManager()
