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
from app.services.game.history import ServedHistory
from app.services.game.manager import DEFAULT_GAME_LANG, WordPoolError, review_items
from app.services.game.profiles import safe_player_badges
from app.services.langs import SUPPORTED_LANGS
from app.services.visibility import lang_item_clause, visible_item_clause

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
RECENT_SENTENCES_PER_USER = SENTENCE_COUNT * 3  # 최근 3판 문장은 제외 (중복 방지)


def wrong_threshold(sentence_len: int) -> int:
    """복습 추천 기준 오타 수 — 문장 길이의 5% (최소 2).

    오타 1개(수정 후 완성)도 "틀린 문장"으로 분류돼 문장 전체가 틀린 것처럼
    보였다 (2026-08-11 보고 — 학습 동기 저하). 한둘 실수는 완성으로 인정하고,
    오타가 잦았던 문장만 복습으로 회수한다. 시간 초과는 기존대로 회수.
    """
    return max(2, round(sentence_len * 0.05))


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


def mastered_item_clause(user_id: int):
    """이미 장기기억(stability 7일+)에 도달한 항목 제외 — 아직 익히는 중인
    표현 위주로 출제 (2026-08-12 기획: 정착한 문장의 반복 노출은 지루함만 남긴다)."""
    from app.models import ReviewCard
    from app.services.fsrs_service import LONG_TERM_STABILITY_DAYS

    return LearningItem.id.not_in(
        select(ReviewCard.item_id).where(
            ReviewCard.user_id == user_id,
            ReviewCard.stability >= LONG_TERM_STABILITY_DAYS,
        )
    )


async def load_sentence_pool(user_id: int, lang: str = DEFAULT_GAME_LANG) -> list[dict]:
    """가시성 규칙(공용 승인 ∪ 내 개인)을 지키는 lang 콘텐츠의 (영문, 뜻) 문장 풀
    (게임 언어 분리 chat-language-rooms.md §게임 언어 분리)."""
    async with get_session_factory()() as db:
        rows = (
            await db.execute(
                select(LearningItem.id, LearningItem.en_text, LearningItem.ko_text)
                .join(ItemOccurrence, ItemOccurrence.item_id == LearningItem.id)
                .join(Content, Content.id == ItemOccurrence.content_id)
                .where(
                    LearningItem.item_type == "sentence",
                    visible_item_clause(user_id),
                    mastered_item_clause(user_id),
                    lang_item_clause(lang),
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
    lang: str = DEFAULT_GAME_LANG
    started: bool = False
    race_started: float = 0.0
    round_no: int = -1
    round_started: float = 0.0
    task: asyncio.Task | None = None
    # 방 게임 종료 후 재대결 대기 상태 — begin 이 새 매치로 리셋한다 (다시하기)
    completed: bool = False


class TypingRaceManager:
    def __init__(self) -> None:
        self.sessions: dict[int, RaceSession] = {}
        self.rooms: dict[str, int] = {}
        self.by_user: dict[int, int] = {}
        # 최근 출제 문장 기록 — 연속 판 중복 방지 (services/game/history.py)
        self.history = ServedHistory(RECENT_SENTENCES_PER_USER)

    # --- 진입 ---

    async def solo(
        self, user_id: int, name: str, send: Sender, lang: str = DEFAULT_GAME_LANG
    ) -> RaceSession:
        await self._leave_if_idle(user_id)
        pool = await self._pool(user_id, lang)
        session = await self._new_session(user_id, name, send, "solo", None, lang)
        await self._start(session, pool)
        return session

    async def create(
        self, user_id: int, name: str, send: Sender, lang: str = DEFAULT_GAME_LANG
    ) -> str:
        await self._leave_if_idle(user_id)
        await self._pool(user_id, lang)  # 시작 전에 문장 부족을 미리 알림
        code = secrets.token_hex(3).upper()
        session = await self._new_session(user_id, name, send, "race", code, lang)
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
        session.players.append(RacerState(user_id=user_id, name=name, send=send))
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
        pool = await self._pool(session.host_id, session.lang)
        if session.completed:
            await self._reset_for_rematch(session)
            if len(session.players) < 2:
                # 전원 이탈 — 혼자 재대결은 시작하지 않고 안내 (교차 리뷰 2026-08-20)
                await self._broadcast(
                    session, {"t": "error", "code": "room_not_enough_players"}
                )
                return
        if session.code:
            self.rooms.pop(session.code, None)
        await self._start(session, pool)

    async def _reset_for_rematch(self, session: RaceSession) -> None:
        """재대결 리셋 — 새 매치 행 발급 + 매핑 재키 + 플레이어 기록 초기화."""
        old_id = session.match_id
        async with get_session_factory()() as db:
            row = TypingRace(mode=session.mode, status="waiting", player1_id=session.host_id)
            db.add(row)
            await db.commit()
            session.match_id = row.id
        self.sessions.pop(old_id, None)
        self.sessions[session.match_id] = session
        if session.code:
            self.rooms[session.code] = session.match_id
        # 결과 화면에서 이탈한 사람은 제외 — 남은 매핑을 되돌리면 그가 새로 시작한
        # 판을 가로챈다 (혼자 한 번 더 → 솔로 세션)
        session.players = [p for p in session.players if p.send is not None]
        for p in session.players:
            self.by_user[p.user_id] = session.match_id
            p.chars = 0
            p.errors = 0
            p.sentences = 0
            p.total_ms = 0
            p.live_chars = 0
            p.done_current = False
            p.peak_cpm = 0.0
            p.wrong = []
        session.sentences = []
        session.race_started = 0.0
        session.round_no = -1
        session.completed = False

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
        if errors >= wrong_threshold(sentence_len):
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

    async def attach(self, user_id: int, send: Sender) -> RaceSession | None:
        """재접속: 진행 중인 레이스가 있으면 sender 재바인딩 + 현재 상태 재전송."""
        session = self._session_of(user_id)
        if session is None or not (session.started or session.completed):
            return None
        racer = next((p for p in session.players if p.user_id == user_id), None)
        if racer is None:
            return None
        racer.send = send
        if session.completed:
            # 결과 화면 중 재접속 — 클라이언트가 이미 결과를 가지고 있어 재바인딩만
            return session
        await self._safe_send(
            racer,
            {
                "t": "tp.start",
                "sentences": session.sentences,
                "total": len(session.sentences),
                "lang": session.lang,
                "sentence_seconds": SENTENCE_SECONDS,
                "countdown": 0,
                "players": [p.name for p in session.players],
                "profiles": await self._profiles(session),
            },
        )
        if 0 <= session.round_no < len(session.sentences):
            await self._safe_send(racer, {"t": "tp.sentence", "idx": session.round_no})
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
        # 최근 판 문장 제외 — 연달아 해도 같은 문장이 반복되지 않게. 풀이 부족하면
        # 전체 풀로 폴백 (작은 풀은 반복 불가피 — 게임 히스토리)
        user_ids = [p.user_id for p in session.players]
        pool = self.history.filter_fresh(
            user_ids, pool, key=lambda s: s["item_id"], minimum=SENTENCE_COUNT
        )
        session.sentences = pick_sentences(pool, SENTENCE_COUNT, secrets.randbits(32))
        self.history.note(user_ids, [s["item_id"] for s in session.sentences])
        session.started = True
        await self._save(session, status="playing")
        await self._broadcast(
            session,
            {
                "t": "tp.start",
                "sentences": session.sentences,
                "total": len(session.sentences),
                "lang": session.lang,
                "sentence_seconds": SENTENCE_SECONDS,
                "countdown": COUNTDOWN_SECONDS,
                "players": [p.name for p in session.players],
                "profiles": await self._profiles(session),
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
        results = []
        for p in session.players:
            wpm = wpm_for(p.chars, max(0.1, p.total_ms / 1000)) if p.total_ms else 0.0
            results.append(
                {
                    "name": p.name,
                    "chars": p.chars,
                    "sentences": p.sentences,
                    "wpm": wpm,
                    # 한국 사용자 준거는 "타"(타/분) — 결과 화면·히스토리 공용 (TpResult 계약)
                    "cpm": round(wpm * 5),
                    "peak_cpm": round(p.peak_cpm),
                    "accuracy": accuracy_for(p.chars, p.errors),
                }
            )
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
        if session.mode == "race" and not aborted:
            self._await_rematch(session)
            return
        self._cleanup(session)

    def _await_rematch(self, session: RaceSession) -> None:
        """방 게임은 방을 유지한 채 재대결 대기 — 다시하기 = 재입장 없이 다음 판
        (2026-08-20 목표). 솔로·크래시 종료는 종전대로 정리."""
        session.players = [p for p in session.players if p.send is not None]
        stale = {uid for uid, mid in self.by_user.items() if mid == session.match_id} - {
            p.user_id for p in session.players
        }
        for gone in stale:
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

    # --- 헬퍼 ---

    @staticmethod
    def _live_wpm(session: RaceSession, racer: RacerState) -> float:
        elapsed = max(0.5, time.monotonic() - (session.race_started or time.monotonic()))
        return wpm_for(racer.chars + racer.live_chars, elapsed)

    async def _pool(self, user_id: int, lang: str) -> list[str]:
        if lang not in SUPPORTED_LANGS:
            raise WordPoolError("invalid_lang")
        pool = await load_sentence_pool(user_id, lang)
        if len(pool) < MIN_SENTENCES:
            raise WordPoolError("sentences_insufficient")
        return pool

    async def _new_session(
        self,
        user_id: int,
        name: str,
        send: Sender,
        mode: str,
        code: str | None,
        lang: str = DEFAULT_GAME_LANG,
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
            lang=lang,
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
                "lang": session.lang,
                "host": session.players[0].name if session.players else "",
                "players": [p.name for p in session.players],
                "profiles": await self._profiles(session),
            },
        )

    async def _profiles(self, session: "RaceSession") -> dict:
        """이름 -> {mascot, title} — 대기실·결과에서 마스코트·칭호 표시 (플레이어 배지)."""
        badges = await safe_player_badges([p.user_id for p in session.players])
        return {p.name: badges[p.user_id] for p in session.players if p.user_id in badges}

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

    async def _leave_if_idle(self, user_id: int) -> None:
        session = self._session_of(user_id)
        if session is not None and not session.started:
            await self.detach(user_id)


racer = TypingRaceManager()
