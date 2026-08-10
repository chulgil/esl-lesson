"""리스닝 빙고 — 원어민 음성/TTS 단어 빙고, 1~4인 (docs/specs/listening-bingo.md).

서버가 단어를 하나씩 부르면(클라이언트가 음성 재생) 각자 4x4 보드에서 찾아 탭.
전원 같은 16단어, 배치만 다름 — 듣고 인지(recognition)가 학습 본체.
"""

import asyncio
import logging
import random
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import get_session_factory
from app.models import BingoMatch, Content, ItemOccurrence, TranscriptSegment
from app.services.game.manager import (
    Sender,
    WordPoolError,
    load_word_pool,
    review_items,
    safe_priority_items,
)

logger = logging.getLogger(__name__)

BOARD_CELLS = 16  # 4x4
ROUND_SECONDS = 10.0
REVEAL_SECONDS = 1.5
COUNTDOWN_SECONDS = 3.0
TICK = 0.1
MAX_PLAYERS = 4

# 빙고 줄 — 4행 + 4열 + 대각 2 (인덱스 0..15, row=i//4 col=i%4)
BINGO_LINES: list[frozenset[int]] = [
    *[frozenset(range(r * 4, r * 4 + 4)) for r in range(4)],
    *[frozenset(range(c, 16, 4)) for c in range(4)],
    frozenset({0, 5, 10, 15}),
    frozenset({3, 6, 9, 12}),
]


def pick_board_words(
    pool: list[tuple[int, str, str]],
    seed: int,
    priority: set[int] | frozenset[int] = frozenset(),
    media_ids: set[int] | frozenset[int] = frozenset(),
) -> list[tuple[int, str, str]]:
    """보드 16단어 선정 — due·오답 우선 → 원어민 구간 보유 우선 → 나머지.

    셔플 뒤 안정 정렬이라 파티션 안 순서는 시드 셔플 그대로 (결정적).
    """
    rng = random.Random(seed)
    shuffled = list(pool)
    rng.shuffle(shuffled)
    shuffled.sort(key=lambda w: (w[0] not in priority, w[0] not in media_ids))
    return shuffled[:BOARD_CELLS]


def has_bingo(arrangement: list[int], filled: set[int]) -> bool:
    """가로/세로/대각 1줄 완성 여부 — arrangement 는 내 배치의 item_id 16개."""
    idx_filled = {i for i, item_id in enumerate(arrangement) if item_id in filled}
    return any(line <= idx_filled for line in BINGO_LINES)


async def load_media_map(item_ids: list[int]) -> dict[int, dict]:
    """항목별 원어민 발화 구간 — 학습 문항 media 와 동일 규칙 (첫 출처 사용)."""
    if not item_ids:
        return {}
    async with get_session_factory()() as db:
        rows = (
            await db.execute(
                select(
                    ItemOccurrence.item_id,
                    Content.youtube_video_id,
                    TranscriptSegment.start_ms,
                    TranscriptSegment.end_ms,
                )
                .join(Content, Content.id == ItemOccurrence.content_id)
                .join(TranscriptSegment, TranscriptSegment.id == ItemOccurrence.segment_id)
                .where(
                    ItemOccurrence.item_id.in_(item_ids),
                    Content.youtube_video_id.is_not(None),
                    TranscriptSegment.start_ms.is_not(None),
                )
            )
        ).all()
    media: dict[int, dict] = {}
    for item_id, video_id, start_ms, end_ms in rows:
        if item_id not in media:
            media[item_id] = {
                "video_id": video_id,
                "start_ms": start_ms,
                "end_ms": end_ms or start_ms + 5000,
            }
    return media


@dataclass
class BingoPlayer:
    user_id: int
    name: str
    send: Sender | None = None
    arrangement: list[int] = field(default_factory=list)  # 내 배치 (item_id 16개)
    filled: set[int] = field(default_factory=set)  # 맞힌 item_id
    wrong: int = 0
    bingo_round: int | None = None
    done_current: bool = False
    missed: list[int] = field(default_factory=list)  # 놓친 라운드의 item_id


@dataclass
class BingoSession:
    match_id: int
    code: str | None
    host_id: int
    mode: str  # solo | room
    players: list[BingoPlayer]
    words: dict[int, tuple[str, str]] = field(default_factory=dict)  # item_id -> (en, ko)
    call_order: list[int] = field(default_factory=list)
    media: dict[int, dict] = field(default_factory=dict)
    started: bool = False
    round_no: int = -1
    round_started: float = 0.0
    task: asyncio.Task | None = None


class BingoManager:
    def __init__(self) -> None:
        self.sessions: dict[int, BingoSession] = {}
        self.rooms: dict[str, int] = {}
        self.by_user: dict[int, int] = {}

    # --- 진입 ---

    async def solo(self, user_id: int, name: str, send: Sender) -> BingoSession:
        self._leave_if_idle(user_id)
        await self._pool(user_id)  # 시작 전에 단어 부족을 미리 알림
        session = await self._new_session(user_id, name, send, "solo", None)
        await self._start(session)
        return session

    async def create(self, user_id: int, name: str, send: Sender) -> str:
        self._leave_if_idle(user_id)
        await self._pool(user_id)
        code = secrets.token_hex(3).upper()
        session = await self._new_session(user_id, name, send, "room", code)
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
        session.players.append(BingoPlayer(user_id=user_id, name=name, send=send))
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
        if session.code:
            self.rooms.pop(session.code, None)
        await self._start(session)

    # --- 플레이 ---

    async def tap(self, user_id: int, no: int, item_id: int) -> None:
        """보드 칸 탭 — 서버 권위 판정. 오답은 재시도 허용 (클라가 1초 잠금)."""
        session = self._session_of(user_id)
        if session is None or not session.started or no != session.round_no:
            return
        player = next((p for p in session.players if p.user_id == user_id), None)
        if player is None or player.done_current:
            return
        current = session.call_order[no]
        if item_id == current:
            player.filled.add(current)
            player.done_current = True
            await self._safe_send(player, {"t": "bg.tap_result", "ok": True, "item_id": current})
            await self._broadcast(
                session,
                {"t": "bg.mark", "name": player.name, "filled": len(player.filled)},
                exclude=user_id,
            )
        else:
            player.wrong += 1
            await self._safe_send(player, {"t": "bg.tap_result", "ok": False, "item_id": item_id})

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
            player.done_current = True  # 이탈자가 라운드를 막지 않게
        if all(p.send is None for p in session.players):
            if session.task:
                session.task.cancel()
            self._cleanup(session)

    # --- 루프 ---

    async def _start(self, session: BingoSession) -> None:
        pool = await self._pool(session.host_id)
        priority = await safe_priority_items([p.user_id for p in session.players])
        media_all = await load_media_map([w[0] for w in pool])
        seed = secrets.randbits(32)
        board = pick_board_words(pool, seed, priority, set(media_all))
        session.words = {i: (en, ko) for i, en, ko in board}
        session.media = {i: m for i, m in media_all.items() if i in session.words}
        order = [w[0] for w in board]
        random.Random(seed + 1).shuffle(order)
        session.call_order = order
        for player in session.players:
            arrangement = [w[0] for w in board]
            random.Random(f"{seed}:{player.user_id}").shuffle(arrangement)
            player.arrangement = arrangement
        session.started = True
        await self._save(session, status="playing")
        for player in session.players:
            await self._safe_send(
                player,
                {
                    "t": "bg.start",
                    "board": [
                        {"item_id": i, "en": session.words[i][0]} for i in player.arrangement
                    ],
                    "total": len(session.call_order),
                    "round_seconds": ROUND_SECONDS,
                    "countdown": COUNTDOWN_SECONDS,
                    "players": [p.name for p in session.players],
                },
            )
        session.task = asyncio.create_task(self._run(session))

    async def _run(self, session: BingoSession) -> None:
        try:
            await asyncio.sleep(COUNTDOWN_SECONDS)
            for round_no, item_id in enumerate(session.call_order):
                session.round_no = round_no
                session.round_started = time.monotonic()
                for p in session.players:
                    p.done_current = p.send is None  # 이탈자는 자동 통과
                await self._broadcast(
                    session,
                    {
                        "t": "bg.round",
                        "no": round_no,
                        "total": len(session.call_order),
                        # 원어민 구간(있으면) — 클라이언트가 재생 버튼 노출, TTS 는 tts 텍스트로
                        "media": session.media.get(item_id),
                        "tts": session.words[item_id][0],
                    },
                )
                deadline = session.round_started + ROUND_SECONDS
                while time.monotonic() < deadline and not all(
                    p.done_current for p in session.players
                ):
                    await asyncio.sleep(TICK)
                for p in session.players:
                    if item_id not in p.filled:
                        p.missed.append(item_id)
                    if p.bingo_round is None and has_bingo(p.arrangement, p.filled):
                        p.bingo_round = round_no
                en, ko = session.words[item_id]
                await self._broadcast(
                    session,
                    {
                        "t": "bg.reveal",
                        "no": round_no,
                        "en": en,
                        "ko": ko,
                        "bingo": [p.name for p in session.players if p.bingo_round == round_no],
                    },
                )
                await asyncio.sleep(REVEAL_SECONDS)
                if any(p.bingo_round is not None for p in session.players):
                    break  # 빙고 달성 라운드에서 종료
            await self._finish(session, aborted=False)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("bingo crashed match=%s", session.match_id)
            await self._finish(session, aborted=True)

    async def _finish(self, session: BingoSession, aborted: bool) -> None:
        def rank_key(p: BingoPlayer) -> tuple:
            return (p.bingo_round is None, p.bingo_round or 0, -len(p.filled), p.wrong)

        ordered = sorted(session.players, key=rank_key)
        winner = None
        if len(ordered) > 1 and rank_key(ordered[0]) != rank_key(ordered[1]):
            winner = ordered[0]
        results = [
            {
                "name": p.name,
                "filled": len(p.filled),
                "wrong": p.wrong,
                "bingo_round": p.bingo_round,
            }
            for p in ordered
        ]
        await self._save(
            session,
            "aborted" if aborted else "finished",
            winner.user_id if winner else None,
            results,
        )
        if not aborted:
            # 놓친 단어는 본인에게만 — 결과 화면 원탭 학습 추가 (전 게임 공통 패턴)
            for p in session.players:
                items = review_items(
                    [
                        {
                            "item_id": i,
                            "en": session.words[i][0],
                            "ko": session.words[i][1],
                        }
                        for i in p.missed
                    ]
                )
                if items:
                    await self._safe_send(p, {"t": "bg.review", "items": items})
        await self._broadcast(
            session,
            {
                "t": "bg.end",
                "results": results,
                "winner": winner.name if winner else None,
                "aborted": aborted,
            },
        )
        self._cleanup(session)

    # --- 헬퍼 ---

    async def _pool(self, user_id: int) -> list[tuple[int, str, str]]:
        pool = await load_word_pool(user_id)
        if len(pool) < BOARD_CELLS:
            raise WordPoolError("words_insufficient")
        return pool

    async def _new_session(
        self, user_id: int, name: str, send: Sender, mode: str, code: str | None
    ) -> BingoSession:
        async with get_session_factory()() as db:
            row = BingoMatch(mode=mode, status="waiting", player1_id=user_id)
            db.add(row)
            await db.commit()
            match_id = row.id
        session = BingoSession(
            match_id=match_id,
            code=code,
            host_id=user_id,
            mode=mode,
            players=[BingoPlayer(user_id=user_id, name=name, send=send)],
        )
        self.sessions[match_id] = session
        self.by_user[user_id] = match_id
        return session

    async def _save(
        self,
        session: BingoSession,
        status: str,
        winner_id: int | None = None,
        results: list[dict] | None = None,
    ) -> None:
        try:
            async with get_session_factory()() as db:
                row = await db.get(BingoMatch, session.match_id)
                if row is None:
                    return
                row.status = status
                if len(session.players) > 1:
                    row.player2_id = session.players[1].user_id
                if results is not None:
                    row.winner_id = winner_id
                    row.stats = {f"p{i + 1}": r for i, r in enumerate(results)}
                    row.ended_at = datetime.now(UTC)
                await db.commit()
        except Exception:
            logger.exception("failed to save bingo match %s", session.match_id)

    async def _broadcast_room(self, session: BingoSession) -> None:
        await self._broadcast(
            session,
            {
                "t": "bg.room",
                "code": session.code,
                "host": session.players[0].name if session.players else "",
                "players": [p.name for p in session.players],
            },
        )

    async def _broadcast(
        self, session: BingoSession, message: dict, exclude: int | None = None
    ) -> None:
        for player in session.players:
            if player.user_id == exclude:
                continue
            await self._safe_send(player, message)

    @staticmethod
    async def _safe_send(player: BingoPlayer, message: dict) -> None:
        if player.send is None:
            return
        try:
            await player.send(message)
        except Exception:
            player.send = None  # 전송 실패 = 이탈 간주, 게임은 계속

    def _cleanup(self, session: BingoSession) -> None:
        for player in session.players:
            if self.by_user.get(player.user_id) == session.match_id:
                del self.by_user[player.user_id]
        if session.code:
            self.rooms.pop(session.code, None)
        self.sessions.pop(session.match_id, None)

    def _session_of(self, user_id: int) -> BingoSession | None:
        match_id = self.by_user.get(user_id)
        return self.sessions.get(match_id) if match_id is not None else None

    def _leave_if_idle(self, user_id: int) -> None:
        session = self._session_of(user_id)
        if session is not None and not session.started:
            self.detach(user_id)


caller = BingoManager()
