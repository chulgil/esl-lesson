"""매치 매니저 — 방/대기열/게임 루프/저장 (docs/specs/word-tetris.md).

전송 계층(WebSocket)과 분리: 플레이어에게는 send(dict) 콜러블로만 통신한다.
단일 프로세스 인메모리 상태 (tech-stack.md 결정).
"""

import asyncio
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import get_session_factory
from app.models import (
    Content,
    ContentSubscription,
    GameMatch,
    ItemOccurrence,
    LearningItem,
    ReviewCard,
)
from app.services.game import records
from app.services.game.bots import Bot
from app.services.game.engine import Board, Match, build_word_queue
from app.services.visibility import visible_item_clause

logger = logging.getLogger(__name__)

TICK_SECONDS = 0.1
STATE_BROADCAST_EVERY = 1  # 틱마다 전송 (페이로드 소형)
RECONNECT_GRACE_SECONDS = 10.0
COUNTDOWN_SECONDS = 3.0
WORD_POOL_MIN = 40
WORD_LEN_RANGE = (3, 12)

Sender = Callable[[dict], Awaitable[None]]


@dataclass
class PlayerSlot:
    user_id: int
    name: str
    send: Sender | None = None
    disconnected_at: float | None = None


@dataclass
class MatchSession:
    match_id: int  # game_matches.id
    mode: str  # pvp | pve
    quiz: str  # en | ko2en
    match: Match
    players: dict[int, PlayerSlot]  # 1, 2 (pve 는 2 없음)
    bot: Bot | None = None
    room_code: str | None = None
    content_ids: list[int] | None = None  # 방장이 선택한 소재 콘텐츠 (None=공용/기본)
    started: bool = False
    task: asyncio.Task | None = None
    input_seq: dict[int, int] = field(default_factory=dict)
    # PvE 이탈 몰수 — 봇전 중도 이탈은 패 대신 기록 제외 (aborted)
    abandoned: bool = False


class GameManager:
    def __init__(self) -> None:
        self.sessions: dict[int, MatchSession] = {}  # match_id -> session
        self.by_user: dict[int, int] = {}  # user_id -> match_id
        self.pvp_queue: list[tuple[int, str, str, Sender]] = []  # (user_id, name, quiz, send)
        self.rooms: dict[str, int] = {}  # room_code -> match_id

    # --- 진입점 ---

    def _guard_not_in_match(self, user_id: int) -> None:
        session = self._session_of(user_id)
        if session is not None and not session.match.finished:
            raise WordPoolError("already_in_match")

    async def join_pve(
        self,
        user_id: int,
        name: str,
        quiz: str,
        bot_level: int,
        send: Sender,
        content_ids: list[int] | None = None,
    ) -> MatchSession:
        self._guard_not_in_match(user_id)
        words = await select_word_pool(user_id, content_ids)
        seed = secrets.randbits(32)
        session = MatchSession(
            match_id=await self._create_match_row("pve", user_id, None, bot_level),
            mode="pve",
            quiz=quiz,
            match=Match(
                board1=Board(word_queue=build_word_queue(words, seed), _rng_seed=seed),
                board2=Board(word_queue=build_word_queue(words, seed), _rng_seed=seed + 1),
            ),
            players={1: PlayerSlot(user_id=user_id, name=name, send=send)},
            bot=Bot.create(bot_level, seed),
        )
        self._register(session)
        await self._start(session, opponent_name=f"봇 Lv.{session.bot.level}")
        return session

    async def join_pvp_queue(self, user_id: int, name: str, quiz: str, send: Sender) -> None:
        self._guard_not_in_match(user_id)
        waiting = next((w for w in self.pvp_queue if w[2] == quiz and w[0] != user_id), None)
        if waiting is None:
            self.pvp_queue.append((user_id, name, quiz, send))
            await send({"t": "queue.waiting"})
            return
        self.pvp_queue.remove(waiting)
        await self._start_pvp(waiting[0], waiting[1], waiting[3], user_id, name, send, quiz)

    async def create_room(
        self,
        user_id: int,
        name: str,
        quiz: str,
        send: Sender,
        content_ids: list[int] | None = None,
    ) -> str:
        self._guard_not_in_match(user_id)
        # 소재 유효성(소유/공용, 최소 단어 수)은 방 생성 시점에 검증
        await select_word_pool(user_id, content_ids)
        code = secrets.token_hex(3).upper()
        match_id = await self._create_match_row("pvp", user_id, None, None, room_code=code)
        session = MatchSession(
            match_id=match_id,
            mode="pvp",
            quiz=quiz,
            match=Match(board1=Board(word_queue=[]), board2=Board(word_queue=[])),
            players={1: PlayerSlot(user_id=user_id, name=name, send=send)},
            room_code=code,
            content_ids=content_ids,
        )
        self._register(session)
        self.rooms[code] = match_id
        await send({"t": "room.created", "code": code})
        return code

    async def join_room(self, user_id: int, name: str, code: str, send: Sender) -> None:
        self._guard_not_in_match(user_id)
        match_id = self.rooms.get(code.upper())
        session = self.sessions.get(match_id) if match_id else None
        if session is None or session.started or 2 in session.players:
            await send({"t": "error", "code": "room_not_found"})
            return
        words = await select_word_pool(session.players[1].user_id, session.content_ids)
        seed = secrets.randbits(32)
        session.match.board1.word_queue = build_word_queue(words, seed)
        session.match.board2.word_queue = build_word_queue(words, seed)
        session.players[2] = PlayerSlot(user_id=user_id, name=name, send=send)
        self.by_user[user_id] = session.match_id
        del self.rooms[code.upper()]
        await self._update_match_row(session, player2_id=user_id)
        await self._start(session)

    async def _start_pvp(
        self, uid1: int, name1: str, send1: Sender, uid2: int, name2: str, send2: Sender, quiz: str
    ) -> None:
        words = await load_public_word_pool()
        seed = secrets.randbits(32)
        session = MatchSession(
            match_id=await self._create_match_row("pvp", uid1, uid2, None),
            mode="pvp",
            quiz=quiz,
            match=Match(
                board1=Board(word_queue=build_word_queue(words, seed), _rng_seed=seed),
                board2=Board(word_queue=build_word_queue(words, seed), _rng_seed=seed + 1),
            ),
            players={
                1: PlayerSlot(user_id=uid1, name=name1, send=send1),
                2: PlayerSlot(user_id=uid2, name=name2, send=send2),
            },
        )
        self._register(session)
        await self._start(session)

    def _register(self, session: MatchSession) -> None:
        self.sessions[session.match_id] = session
        for slot in session.players.values():
            self.by_user[slot.user_id] = session.match_id

    async def _start(self, session: MatchSession, opponent_name: str | None = None) -> None:
        session.started = True
        for player_no, slot in session.players.items():
            other = session.players.get(3 - player_no)
            await self._safe_send(
                slot,
                {
                    "t": "match.found",
                    "match_id": session.match_id,
                    "mode": session.mode,
                    "quiz": session.quiz,
                    "you": player_no,
                    "opponent": other.name if other else (opponent_name or "봇"),
                    "countdown": int(COUNTDOWN_SECONDS),
                },
            )
        session.task = asyncio.create_task(self._run_loop(session))

    # --- 게임 루프 ---

    async def _run_loop(self, session: MatchSession) -> None:
        try:
            await asyncio.sleep(COUNTDOWN_SECONDS)  # 카운트다운
            last = time.monotonic()
            while not session.match.finished:
                await asyncio.sleep(TICK_SECONDS)
                now = time.monotonic()
                dt, last = now - last, now
                await self._step(session, dt)
            await self._finish(session, aborted=session.abandoned)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("game loop crashed match=%s", session.match_id)
            session.match.finished = True
            await self._finish(session, aborted=True)

    async def _step(self, session: MatchSession, dt: float) -> None:
        events = session.match.tick(dt)

        if session.bot is not None and not session.match.finished:
            text = session.bot.act(session.match.board2)
            if text is not None:
                session.match.submit(2, text)

        # 이탈 유예 초과 → 몰수. 봇전은 혼자 연습이라 몰수패 대신 기록 제외
        for player_no, slot in session.players.items():
            if (
                slot.disconnected_at
                and time.monotonic() - slot.disconnected_at > RECONNECT_GRACE_SECONDS
            ):
                if session.bot is not None:
                    session.abandoned = True
                session.match.forfeit(player_no)

        await self._broadcast_state(session, events)

    async def _broadcast_state(self, session: MatchSession, events: dict[int, list[str]]) -> None:
        for player_no, slot in session.players.items():
            me = session.match.board1 if player_no == 1 else session.match.board2
            op = session.match.board2 if player_no == 1 else session.match.board1
            await self._safe_send(
                slot,
                {
                    "t": "state",
                    "elapsed": round(session.match.elapsed, 1),
                    "me": me.snapshot(),
                    "op": op.snapshot(),
                    "events": {
                        "me": events.get(player_no, []),
                        "op": events.get(3 - player_no, []),
                    },
                },
            )

    # --- 입력 ---

    async def handle_input(self, user_id: int, text: str, seq: int) -> None:
        session = self._session_of(user_id)
        if session is None or not session.started or session.match.finished:
            return
        player_no = self._player_no(session, user_id)
        result = session.match.submit(player_no, text)
        slot = session.players[player_no]
        await self._safe_send(
            slot,
            {
                "t": "clear.result",
                "seq": seq,
                "ok": result.ok,
                "brick_id": result.brick_id,
                "combo": result.combo,
                "effects": result.effects,
                "score_gained": result.score_gained,
            },
        )
        if result.item_gained:
            await self._safe_send(slot, {"t": "item.gained", "item": result.item_gained})
        if result.attack:
            other = session.players.get(3 - player_no)
            if other:
                await self._safe_send(other, {"t": "attack.recv", "count": result.attack})

    async def handle_item(self, user_id: int, kind: str) -> None:
        """아이템 사용 (docs/specs/word-tetris.md). 힌트는 요청자에게만 정답 전송."""
        session = self._session_of(user_id)
        if session is None or not session.started or session.match.finished:
            return
        player_no = self._player_no(session, user_id)
        result = session.match.use_item(player_no, kind)
        slot = session.players[player_no]
        if result is None:
            await self._safe_send(slot, {"t": "item.result", "item": kind, "ok": False})
            return
        await self._safe_send(slot, {"t": "item.result", "ok": True, **result})

    # --- 접속 관리 ---

    async def attach(self, user_id: int, send: Sender) -> MatchSession | None:
        """재접속: 활성 세션이 있으면 복귀시킨다."""
        session = self._session_of(user_id)
        if session is None:
            return None
        player_no = self._player_no(session, user_id)
        slot = session.players[player_no]
        slot.send = send
        slot.disconnected_at = None
        other = session.players.get(3 - player_no)
        await self._safe_send(
            slot,
            {
                "t": "match.found",
                "match_id": session.match_id,
                "mode": session.mode,
                "quiz": session.quiz,
                "you": player_no,
                "opponent": other.name
                if other
                else f"봇 Lv.{session.bot.level if session.bot else '?'}",
                "countdown": 0,
                "rejoined": True,
            },
        )
        return session

    def detach(self, user_id: int) -> None:
        session = self._session_of(user_id)
        if session is None:
            return
        # 대기열/대기방 정리
        self.pvp_queue = [w for w in self.pvp_queue if w[0] != user_id]
        if not session.started:
            if session.room_code:
                self.rooms.pop(session.room_code, None)
            self._cleanup(session)
            return
        player_no = self._player_no(session, user_id)
        slot = session.players[player_no]
        slot.send = None
        slot.disconnected_at = time.monotonic()

    def leave_queue(self, user_id: int) -> None:
        self.pvp_queue = [w for w in self.pvp_queue if w[0] != user_id]

    # --- 종료/저장 ---

    async def _finish(self, session: MatchSession, aborted: bool = False) -> None:
        match = session.match
        winner_no = match.winner
        stats = {
            "p1": _board_stats(match.board1),
            "p2": _board_stats(match.board2),
            "duration": round(match.elapsed, 1),
        }
        winner_user_id = None
        if winner_no is not None:
            slot = session.players.get(winner_no)
            winner_user_id = slot.user_id if slot else None

        # 개인 최고 기록 경신 판정 — 이번 결과 저장 "전"의 과거 기록과 비교 (P3)
        records_by_player: dict[int, list[str]] = {}
        if not aborted:
            for player_no, slot in session.players.items():
                if slot.user_id is None:
                    continue
                try:
                    prev = await self._previous_bests(slot.user_id)
                    records_by_player[player_no] = records.new_records(prev, stats[f"p{player_no}"])
                except Exception:
                    logger.exception("records check failed user=%s", slot.user_id)

        await self._save_result(session, winner_user_id, stats, aborted)

        for player_no, slot in session.players.items():
            outcome = "draw"
            if winner_no is not None:
                outcome = "win" if player_no == winner_no else "lose"
            await self._safe_send(
                slot,
                {
                    "t": "match.end",
                    "winner": outcome,
                    "stats": stats,
                    "aborted": aborted,
                    "records": records_by_player.get(player_no, []),
                },
            )
        self._cleanup(session)

    def _cleanup(self, session: MatchSession) -> None:
        for slot in session.players.values():
            if self.by_user.get(slot.user_id) == session.match_id:
                del self.by_user[slot.user_id]
        self.sessions.pop(session.match_id, None)

    # --- DB ---

    async def _create_match_row(
        self,
        mode: str,
        player1_id: int,
        player2_id: int | None,
        bot_level: int | None,
        room_code: str | None = None,
    ) -> int:
        async with get_session_factory()() as db:
            row = GameMatch(
                mode=mode,
                status="waiting",
                player1_id=player1_id,
                player2_id=player2_id,
                bot_level=bot_level,
                room_code=room_code,
            )
            db.add(row)
            await db.commit()
            return row.id

    async def _previous_bests(self, user_id: int) -> dict:
        async with get_session_factory()() as db:
            rows = (
                await db.execute(
                    select(
                        GameMatch.player1_id,
                        GameMatch.p1_score,
                        GameMatch.p2_score,
                        GameMatch.stats,
                    ).where(
                        (GameMatch.player1_id == user_id) | (GameMatch.player2_id == user_id),
                        GameMatch.status == "finished",
                    )
                )
            ).all()
        return records.bests_from_matches(user_id, rows)

    async def _update_match_row(self, session: MatchSession, player2_id: int) -> None:
        async with get_session_factory()() as db:
            row = await db.get(GameMatch, session.match_id)
            if row:
                row.player2_id = player2_id
                await db.commit()

    async def _save_result(
        self, session: MatchSession, winner_user_id: int | None, stats: dict, aborted: bool
    ) -> None:
        try:
            async with get_session_factory()() as db:
                row = await db.get(GameMatch, session.match_id)
                if row is None:
                    return
                row.status = "aborted" if aborted else "finished"
                row.winner_id = winner_user_id
                row.p1_score = session.match.board1.score
                row.p2_score = session.match.board2.score
                row.stats = stats
                row.started_at = row.started_at or datetime.now(UTC)
                row.ended_at = datetime.now(UTC)
                await db.commit()
        except Exception:
            logger.exception("failed to save match result %s", session.match_id)

    # --- 헬퍼 ---

    def _session_of(self, user_id: int) -> MatchSession | None:
        match_id = self.by_user.get(user_id)
        return self.sessions.get(match_id) if match_id else None

    @staticmethod
    def _player_no(session: MatchSession, user_id: int) -> int:
        for player_no, slot in session.players.items():
            if slot.user_id == user_id:
                return player_no
        raise ValueError("player not in session")

    @staticmethod
    async def _safe_send(slot: PlayerSlot, message: dict) -> None:
        if slot.send is None:
            return
        try:
            await slot.send(message)
        except Exception:
            slot.send = None  # 전송 실패 = 연결 끊김으로 간주
            slot.disconnected_at = slot.disconnected_at or time.monotonic()


def _board_stats(board) -> dict:
    minutes = max(board.elapsed / 60.0, 1e-6)
    return {
        "score": board.score,
        "cleared": board.cleared_words,
        "misses": board.misses,
        "max_combo": board.max_combo,
        "wpm": round(board.cleared_words / minutes, 1),
        "accuracy": round(board.cleared_words / max(1, board.cleared_words + board.misses), 3),
    }


class WordPoolError(Exception):
    """소재 콘텐츠가 유효하지 않거나 단어가 부족할 때."""


def _playable(item: LearningItem) -> bool:
    lo, hi = WORD_LEN_RANGE
    return lo <= len(item.en_text) <= hi and " " not in item.en_text


CONTENT_POOL_MIN = 10  # 콘텐츠 선택 대전의 최소 단어 수


async def select_word_pool(
    user_id: int, content_ids: list[int] | None
) -> list[tuple[int, str, str]]:
    """소재 선택: content_ids 지정 시 해당 콘텐츠 단어, 아니면 기본 풀 (word-tetris.md)."""
    if content_ids:
        return await load_word_pool_from_contents(user_id, content_ids)
    pool = await load_word_pool(user_id)
    if len(pool) < CONTENT_POOL_MIN:
        # 빈 보드로 시작하는 크래시 방지 (2026-07-11 운영 실측) — 시작 전에 안내
        raise WordPoolError("words_insufficient")
    return pool


def review_items(entries: list[dict]) -> list[dict]:
    """오답 복습 항목 목록 — item_id 중복 제거(순환 풀 대응), {item_id,en,ko} 만 유지.

    게임 종료 시 *.review 개인 메시지의 items 페이로드 (quiz-royale.md 오답 → 원탭 학습).
    """
    seen: set[int] = set()
    items: list[dict] = []
    for entry in entries:
        item_id = entry.get("item_id") or 0
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        items.append({"item_id": item_id, "en": entry.get("en", ""), "ko": entry.get("ko", "")})
    return items


async def load_word_pool_from_contents(
    user_id: int, content_ids: list[int]
) -> list[tuple[int, str, str]]:
    """선택한 콘텐츠(공용 또는 내 개인)의 word 항목만으로 풀 구성."""
    async with get_session_factory()() as db:
        contents = (
            (await db.execute(select(Content).where(Content.id.in_(content_ids)))).scalars().all()
        )
        if len(contents) != len(set(content_ids)):
            raise WordPoolError("content_not_found")
        private_ids = [c.id for c in contents if c.visibility == "private"]
        if private_ids:
            subscribed = set(
                (
                    await db.execute(
                        select(ContentSubscription.content_id).where(
                            ContentSubscription.content_id.in_(private_ids),
                            ContentSubscription.user_id == user_id,
                        )
                    )
                ).scalars()
            )
            if set(private_ids) - subscribed:
                raise WordPoolError("content_not_yours")
        items = (
            (
                await db.execute(
                    select(LearningItem)
                    .join(ItemOccurrence, ItemOccurrence.item_id == LearningItem.id)
                    .where(
                        ItemOccurrence.content_id.in_(content_ids),
                        LearningItem.item_type == "word",
                        LearningItem.review_status != "rejected",
                    )
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
    pool = [i for i in items if _playable(i)]
    if len(pool) < CONTENT_POOL_MIN:
        raise WordPoolError("words_insufficient")
    return _to_pool(pool)


async def load_public_word_pool() -> list[tuple[int, str, str]]:
    """빠른 대전용 공용 풀 — 공용 콘텐츠 출처가 있는 approved word."""
    async with get_session_factory()() as db:
        items = (
            (
                await db.execute(
                    select(LearningItem)
                    .join(ItemOccurrence, ItemOccurrence.item_id == LearningItem.id)
                    .join(Content, Content.id == ItemOccurrence.content_id)
                    .where(
                        Content.visibility == "public",
                        LearningItem.item_type == "word",
                        LearningItem.review_status == "approved",
                    )
                    .distinct()
                    .limit(300)
                )
            )
            .scalars()
            .all()
        )
    return _to_pool([i for i in items if _playable(i)])


async def load_word_pool(user_id: int) -> list[tuple[int, str, str]]:
    """기본 풀: 내가 학습한 word 우선(지금 담긴 것만), 부족하면 보이는 단어로 보충."""
    async with get_session_factory()() as db:
        learned = (
            (
                await db.execute(
                    select(LearningItem)
                    .join(ReviewCard, ReviewCard.item_id == LearningItem.id)
                    .where(
                        ReviewCard.user_id == user_id,
                        LearningItem.item_type == "word",
                        LearningItem.review_status != "rejected",
                        # 카드가 남아 있어도 구독 해제한 콘텐츠의 단어는 제외 —
                        # 학습 재료 = 담은 콘텐츠 (content-governance.md)
                        visible_item_clause(user_id),
                    )
                )
            )
            .scalars()
            .all()
        )
        pool = [i for i in learned if _playable(i)]
        if len(pool) < WORD_POOL_MIN:
            # 내게 보이는 단어 전체로 보충 (공용 승인 + 내 개인 콘텐츠 — visibility 규칙)
            extra = (
                (
                    await db.execute(
                        select(LearningItem)
                        .where(
                            LearningItem.item_type == "word",
                            visible_item_clause(user_id),
                        )
                        .distinct()
                        .limit(300)
                    )
                )
                .scalars()
                .all()
            )
            seen = {i.id for i in pool}
            pool += [i for i in extra if i.id not in seen and _playable(i)]
    return _to_pool(pool)


def _to_pool(items: list[LearningItem]) -> list[tuple[int, str, str]]:
    """(word_id, en, ko) — 방향은 브릭 스폰 시 레벨 구간으로 결정 (engine)."""
    return [(i.id, i.en_text, i.ko_text) for i in items]


manager = GameManager()
