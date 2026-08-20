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
from app.services.game.history import ServedHistory
from app.services.game.manager import (
    DEFAULT_GAME_LANG,
    Sender,
    WordPoolError,
    load_word_pool,
    review_items,
    safe_priority_items,
)
from app.services.game.profiles import safe_player_badges
from app.services.langs import SUPPORTED_LANGS

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
    lang: str = DEFAULT_GAME_LANG
    started: bool = False
    round_no: int = -1
    round_started: float = 0.0
    task: asyncio.Task | None = None
    # 방 게임 종료 후 재대결 대기 상태 — begin 이 새 매치로 리셋한다 (다시하기)
    completed: bool = False


RECENT_WORDS_PER_USER = BOARD_CELLS * 3  # 최근 3판 단어는 보드에서 제외 (중복 방지)


class BingoManager:
    def __init__(self) -> None:
        self.sessions: dict[int, BingoSession] = {}
        self.rooms: dict[str, int] = {}
        self.by_user: dict[int, int] = {}
        # 최근 출제 단어 기록 — 연속 판 중복 방지 (services/game/history.py)
        self.history = ServedHistory(RECENT_WORDS_PER_USER)

    # --- 진입 ---

    async def solo(
        self, user_id: int, name: str, send: Sender, lang: str = DEFAULT_GAME_LANG
    ) -> BingoSession:
        await self._leave_if_idle(user_id)
        await self._pool(user_id, lang)  # 시작 전에 단어 부족을 미리 알림
        session = await self._new_session(user_id, name, send, "solo", None, lang)
        await self._start(session)
        return session

    async def create(
        self, user_id: int, name: str, send: Sender, lang: str = DEFAULT_GAME_LANG
    ) -> str:
        await self._leave_if_idle(user_id)
        await self._pool(user_id, lang)
        code = secrets.token_hex(3).upper()
        session = await self._new_session(user_id, name, send, "room", code, lang)
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
        await self._leave_if_idle(user_id)
        session.players.append(BingoPlayer(user_id=user_id, name=name, send=send))
        self.by_user[user_id] = session.match_id
        await self._broadcast_room(session)

    async def begin(self, user_id: int) -> None:
        """호스트만 시작 (2인 이상). 솔로는 자동 시작이라 불필요.

        종료된 방(completed)이면 재대결 — 새 매치 행으로 리셋 후 시작
        (다시하기 = 재입장 없이 같은 멤버로 다음 판, 2026-08-20 목표)."""
        session = self._session_of(user_id)
        if (
            session is None
            or session.started
            or session.host_id != user_id
            or len(session.players) < 2
        ):
            return
        if session.completed:
            await self._reset_for_rematch(session)
            if len(session.players) < 2:
                # 전원 이탈 — 혼자 재대결은 시작하지 않고 안내 (교차 리뷰 2026-08-20)
                await self._broadcast(session, {"t": "error", "code": "room_not_enough_players"})
                return
        if session.code:
            self.rooms.pop(session.code, None)
        await self._start(session)

    async def _reset_for_rematch(self, session: BingoSession) -> None:
        """재대결 리셋 — 새 매치 행 발급 + 매핑 재키 + 플레이어 상태 초기화."""
        old_id = session.match_id
        async with get_session_factory()() as db:
            row = BingoMatch(mode=session.mode, status="waiting", player1_id=session.host_id)
            db.add(row)
            await db.commit()
            session.match_id = row.id
        self.sessions.pop(old_id, None)
        self.sessions[session.match_id] = session
        if session.code:
            self.rooms[session.code] = session.match_id
        # 결과 화면에서 이탈한 사람은 제외 — 남은 매핑을 되돌리면 그가 새로
        # 시작한 판(혼자 한 번 더 → 솔로)을 가로챈다 (교차 리뷰 2026-08-20)
        session.players = [p for p in session.players if p.send is not None]
        for p in session.players:
            self.by_user[p.user_id] = session.match_id
            p.arrangement = []
            p.filled = set()
            p.wrong = 0
            p.bingo_round = None
            p.done_current = False
            p.missed = []
        session.words = {}
        session.call_order = []
        session.media = {}
        session.round_no = -1
        session.completed = False

    # --- 플레이 ---

    async def tap(self, user_id: int, no: int, item_id: int) -> None:
        """보드 칸 탭 — 서버 권위 판정. 오답은 재시도 허용 (클라가 1초 잠금).

        no < 0 가드 (2026-08-10 리뷰): round_no 는 카운트다운·정답 공개 동안 -1 —
        기본값 no=-1 탭이 음수 인덱스로 마지막 호출 단어를 선채움하던 구멍.
        """
        session = self._session_of(user_id)
        if session is None or not session.started or no < 0 or no != session.round_no:
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

    async def attach(self, user_id: int, send: Sender) -> BingoSession | None:
        """재접속: 진행 중인 빙고가 있으면 sender 재바인딩 + 현재 상태(내 보드) 재전송."""
        session = self._session_of(user_id)
        if session is None or not (session.started or session.completed):
            return None
        player = next((p for p in session.players if p.user_id == user_id), None)
        if player is None:
            return None
        player.send = send
        if session.completed:
            # 결과 화면 중 재접속 — 클라이언트가 이미 결과를 가지고 있어 재바인딩만
            return session
        await self._safe_send(
            player,
            {
                "t": "bg.start",
                "board": [{"item_id": i, "en": session.words[i][0]} for i in player.arrangement],
                "total": len(session.call_order),
                "lang": session.lang,
                "round_seconds": ROUND_SECONDS,
                "countdown": 0,
                "players": [p.name for p in session.players],
                # 재접속 상태 복원 — 없으면 보드가 빈 판으로 보인다 (2026-08-20 튕김 보고)
                "filled": sorted(player.filled),
                "marks": {p.name: len(p.filled) for p in session.players},
            },
        )
        if 0 <= session.round_no < len(session.call_order):
            item_id = session.call_order[session.round_no]
            await self._safe_send(
                player,
                {
                    "t": "bg.round",
                    "no": session.round_no,
                    "total": len(session.call_order),
                    "media": session.media.get(item_id),
                    "tts": session.words[item_id][0],
                },
            )
        return session

    async def detach(self, user_id: int) -> None:
        session = self._session_of(user_id)
        if session is None:
            return
        # completed(재대결 대기)는 진행 중과 같은 경로 — 결과 화면의 순간 끊김이
        # 방을 없애지 않게 매핑 유지, 전원 이탈 시에만 정리 (2026-08-20)
        if not session.started and not session.completed:
            self.by_user.pop(user_id, None)
            session.players = [p for p in session.players if p.user_id != user_id]
            if session.host_id == user_id or not session.players:
                # 남은 대기 플레이어에게 방 종료를 알린다 — 안 알리면 화면이 멈춘다 (버그 2)
                await self._broadcast(session, {"t": "error", "code": "room_closed"})
                self._cleanup(session)
            return
        # 진행 중 매치는 by_user 매핑 유지 — WS 재접속(attach) 이 세션을 찾을 수 있어야 한다
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
        pool = await self._pool(session.host_id, session.lang)
        # 최근 판 단어 제외 — 연달아 해도 같은 단어가 반복되지 않게. 풀이
        # 부족하면 전체 풀로 폴백 (작은 풀은 반복 불가피 — 게임 히스토리)
        user_ids = [p.user_id for p in session.players]
        pool = self.history.filter_fresh(user_ids, pool, key=lambda w: w[0], minimum=BOARD_CELLS)
        priority = await safe_priority_items(user_ids)
        media_all = await load_media_map([w[0] for w in pool])
        seed = secrets.randbits(32)
        board = pick_board_words(pool, seed, priority, set(media_all))
        self.history.note(user_ids, [w[0] for w in board])
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
                    "lang": session.lang,
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
                # 라운드 마감 — 정답 공개(reveal) 동안의 탭이 정답 처리되던 구멍
                # (2026-08-10 리뷰: 공개 후 1.5초간 공짜 크레딧 + missed/filled 이중 기록)
                session.round_no = -1
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
        # 방 게임은 방을 유지한 채 재대결 대기 — 다시하기 = 재입장 없이 다음 판
        # (2026-08-20 목표). 솔로·크래시 종료는 종전대로 정리.
        if session.mode == "room" and not aborted:
            session.players = [p for p in session.players if p.send is not None]
            for gone in {uid for uid, mid in self.by_user.items() if mid == session.match_id} - {
                p.user_id for p in session.players
            }:
                self.by_user.pop(gone, None)
            if not session.players:
                self._cleanup(session)
                return
            if all(p.user_id != session.host_id for p in session.players):
                session.host_id = session.players[0].user_id  # 방장 이탈 — 첫 플레이어 승계
            session.started = False
            session.completed = True
            session.round_no = -1
            session.task = None
            if session.code:
                self.rooms[session.code] = session.match_id
            return
        self._cleanup(session)

    # --- 헬퍼 ---

    async def _pool(self, user_id: int, lang: str) -> list[tuple[int, str, str]]:
        if lang not in SUPPORTED_LANGS:
            raise WordPoolError("invalid_lang")
        pool = await load_word_pool(user_id, lang)
        if len(pool) < BOARD_CELLS:
            raise WordPoolError("words_insufficient")
        return pool

    async def _new_session(
        self,
        user_id: int,
        name: str,
        send: Sender,
        mode: str,
        code: str | None,
        lang: str = DEFAULT_GAME_LANG,
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
            lang=lang,
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
                "lang": session.lang,
                "host": session.players[0].name if session.players else "",
                "players": [p.name for p in session.players],
                "profiles": await self._profiles(session),
            },
        )

    async def _profiles(self, session) -> dict:
        """이름 -> {mascot, title} — 대기실·결과의 플레이어 배지 (mascot-shop.md)."""
        badges = await safe_player_badges([p.user_id for p in session.players])
        return {p.name: badges[p.user_id] for p in session.players if p.user_id in badges}

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

    async def _leave_if_idle(self, user_id: int) -> None:
        session = self._session_of(user_id)
        if session is not None and not session.started:
            await self.detach(user_id)


caller = BingoManager()
