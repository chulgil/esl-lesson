"""게임 API — WS 대전 + REST 전적 (docs/specs/word-tetris.md)."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db, get_session_factory
from app.core.security import SESSION_COOKIE, decode_session_token, get_current_user
from app.models import (
    DailyPuzzlePlay,
    DictationRace,
    GameMatch,
    QuizRoyaleMatch,
    QuizRoyalePlayer,
    ScrambleRace,
    TypingRace,
    User,
)
from app.services import daily_puzzle
from app.services import push as push_service
from app.services.friends import are_friends
from app.services.game import records
from app.services.game.dictation import dictator
from app.services.game.invites import GAMES, invite_hub, invite_push_payload
from app.services.game.manager import WordPoolError, manager
from app.services.game.quiz_royale import royale
from app.services.game.scramble import scrambler
from app.services.game.spectate import spectate_hub
from app.services.game.typing_race import racer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game", tags=["game"])
ws_router = APIRouter()


@router.get("/profile")
async def game_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    played = (
        await db.execute(
            select(func.count(GameMatch.id)).where(
                (GameMatch.player1_id == user.id) | (GameMatch.player2_id == user.id),
                GameMatch.status == "finished",
            )
        )
    ).scalar_one()
    wins = (
        await db.execute(
            select(func.count(GameMatch.id)).where(
                GameMatch.winner_id == user.id, GameMatch.status == "finished"
            )
        )
    ).scalar_one()
    best_score = (
        await db.execute(
            select(
                func.max(
                    case(
                        (GameMatch.player1_id == user.id, GameMatch.p1_score),
                        else_=GameMatch.p2_score,
                    )
                )
            ).where(
                (GameMatch.player1_id == user.id) | (GameMatch.player2_id == user.id),
                GameMatch.status == "finished",
            )
        )
    ).scalar_one()
    stat_rows = (
        await db.execute(
            select(
                GameMatch.player1_id, GameMatch.p1_score, GameMatch.p2_score, GameMatch.stats
            ).where(
                (GameMatch.player1_id == user.id) | (GameMatch.player2_id == user.id),
                GameMatch.status == "finished",
            )
        )
    ).all()
    bests = records.bests_from_matches(user.id, stat_rows)
    return {
        "played": played,
        "wins": wins,
        "losses": played - wins,
        "best_score": best_score or 0,
        "best_combo": int(bests["max_combo"]),
        "best_wpm": round(bests["wpm"], 1),
    }


@router.get("/bests")
async def game_bests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """게임별 내 최고 기록 — 게임 허브 카드 배지용 (P1 데일리 루프)."""
    tetris = (
        await db.execute(
            select(
                func.max(
                    case(
                        (GameMatch.player1_id == user.id, GameMatch.p1_score),
                        else_=GameMatch.p2_score,
                    )
                )
            ).where(
                (GameMatch.player1_id == user.id) | (GameMatch.player2_id == user.id),
                GameMatch.status == "finished",
            )
        )
    ).scalar_one()

    quiz_best = (
        await db.execute(
            select(func.coalesce(func.max(QuizRoyalePlayer.score), 0))
            .join(QuizRoyaleMatch, QuizRoyaleMatch.id == QuizRoyalePlayer.match_id)
            .where(
                QuizRoyalePlayer.user_id == user.id,
                QuizRoyaleMatch.status == "finished",
            )
        )
    ).scalar_one()

    typing_best = 0
    typing_rows = (
        (
            await db.execute(
                select(TypingRace).where(
                    (TypingRace.player1_id == user.id) | (TypingRace.player2_id == user.id),
                    TypingRace.status == "finished",
                )
            )
        )
        .scalars()
        .all()
    )
    for row in typing_rows:
        slot = "p1" if row.player1_id == user.id else "p2"
        stats = (row.stats or {}).get(slot) or {}
        typing_best = max(typing_best, int(stats.get("peak_cpm") or 0))

    scramble_best = (
        await db.execute(
            select(
                func.coalesce(
                    func.max(
                        case(
                            (ScrambleRace.player1_id == user.id, ScrambleRace.p1_score),
                            else_=ScrambleRace.p2_score,
                        )
                    ),
                    0,
                )
            ).where(
                (ScrambleRace.player1_id == user.id) | (ScrambleRace.player2_id == user.id),
                ScrambleRace.status == "finished",
            )
        )
    ).scalar_one()

    dictation_best = (
        await db.execute(
            select(
                func.coalesce(
                    func.max(
                        case(
                            (DictationRace.player1_id == user.id, DictationRace.p1_score),
                            else_=DictationRace.p2_score,
                        )
                    ),
                    0,
                )
            ).where(
                (DictationRace.player1_id == user.id) | (DictationRace.player2_id == user.id),
                DictationRace.status == "finished",
            )
        )
    ).scalar_one()

    return {
        "tetris_best_score": tetris or 0,
        "quiz_best_score": quiz_best,
        "typing_best_cpm": typing_best,
        "scramble_best_score": scramble_best,
        "dictation_best_score": dictation_best,
    }


@router.get("/leaderboard")
async def leaderboard(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    """주간 리더보드: 최근 7일 점수 합산 상위 10."""
    since = datetime.now(UTC) - timedelta(days=7)
    p1 = select(GameMatch.player1_id.label("uid"), GameMatch.p1_score.label("score")).where(
        GameMatch.status == "finished", GameMatch.ended_at >= since
    )
    p2 = select(GameMatch.player2_id.label("uid"), GameMatch.p2_score.label("score")).where(
        GameMatch.status == "finished",
        GameMatch.ended_at >= since,
        GameMatch.player2_id.is_not(None),
    )
    union = p1.union_all(p2).subquery()
    rows = (
        await db.execute(
            select(User.nickname, func.sum(union.c.score).label("total"))
            .join(User, User.id == union.c.uid)
            .group_by(User.id, User.nickname)
            .order_by(func.sum(union.c.score).desc())
            .limit(10)
        )
    ).all()
    return {"items": [{"name": name, "score": int(total)} for name, total in rows]}


LEADERBOARD_TOP = 5


@router.get("/leaderboards")
async def weekly_leaderboards(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """게임별 주간 최고 기록 top5 — 게임 허브 표시 (P3). 봇 제외."""
    since = datetime.now(UTC) - timedelta(days=7)

    # 테트리스: 유저별 주간 최고 점수
    tetris_best: dict[int, int] = {}
    rows = (
        await db.execute(
            select(
                GameMatch.player1_id, GameMatch.player2_id, GameMatch.p1_score, GameMatch.p2_score
            ).where(GameMatch.status == "finished", GameMatch.ended_at >= since)
        )
    ).all()
    for p1_id, p2_id, s1, s2 in rows:
        tetris_best[p1_id] = max(tetris_best.get(p1_id, 0), s1 or 0)
        if p2_id is not None:
            tetris_best[p2_id] = max(tetris_best.get(p2_id, 0), s2 or 0)

    # 퀴즈 로얄: 정규 참가 기록 집계 (봇 없음 — 저장 시 제외)
    quiz_best = dict(
        (
            await db.execute(
                select(QuizRoyalePlayer.user_id, func.max(QuizRoyalePlayer.score))
                .join(QuizRoyaleMatch, QuizRoyaleMatch.id == QuizRoyalePlayer.match_id)
                .where(
                    QuizRoyaleMatch.status == "finished",
                    QuizRoyaleMatch.ended_at >= since,
                )
                .group_by(QuizRoyalePlayer.user_id)
            )
        ).all()
    )

    # 타자연습: 유저별 주간 최고 타 (peak_cpm)
    typing_best: dict[int, int] = {}
    for race in (
        (
            await db.execute(
                select(TypingRace).where(
                    TypingRace.status == "finished", TypingRace.ended_at >= since
                )
            )
        )
        .scalars()
        .all()
    ):
        for uid, slot in ((race.player1_id, "p1"), (race.player2_id, "p2")):
            if uid is None:
                continue
            peak = int(((race.stats or {}).get(slot) or {}).get("peak_cpm") or 0)
            typing_best[uid] = max(typing_best.get(uid, 0), peak)

    # 어순 레이스: 유저별 주간 최고 점수
    scramble_best: dict[int, int] = {}
    for p1_id, p2_id, s1, s2 in (
        await db.execute(
            select(
                ScrambleRace.player1_id,
                ScrambleRace.player2_id,
                ScrambleRace.p1_score,
                ScrambleRace.p2_score,
            ).where(ScrambleRace.status == "finished", ScrambleRace.ended_at >= since)
        )
    ).all():
        if p1_id is not None:
            scramble_best[p1_id] = max(scramble_best.get(p1_id, 0), s1 or 0)
        if p2_id is not None:
            scramble_best[p2_id] = max(scramble_best.get(p2_id, 0), s2 or 0)

    # 받아쓰기: 유저별 주간 최고 점수
    dictation_best: dict[int, int] = {}
    for p1_id, p2_id, s1, s2 in (
        await db.execute(
            select(
                DictationRace.player1_id,
                DictationRace.player2_id,
                DictationRace.p1_score,
                DictationRace.p2_score,
            ).where(DictationRace.status == "finished", DictationRace.ended_at >= since)
        )
    ).all():
        if p1_id is not None:
            dictation_best[p1_id] = max(dictation_best.get(p1_id, 0), s1 or 0)
        if p2_id is not None:
            dictation_best[p2_id] = max(dictation_best.get(p2_id, 0), s2 or 0)

    all_ids = (
        set(tetris_best)
        | set(quiz_best)
        | set(typing_best)
        | set(scramble_best)
        | set(dictation_best)
    )
    names: dict[int, str] = {}
    if all_ids:
        names = dict(
            (await db.execute(select(User.id, User.nickname).where(User.id.in_(all_ids)))).all()
        )

    def top(best: dict[int, int]) -> list[dict]:
        ranked = sorted(best.items(), key=lambda kv: (-kv[1], names.get(kv[0], "")))
        return [
            {"name": names.get(uid, "?"), "value": value, "me": uid == user.id}
            for uid, value in ranked[:LEADERBOARD_TOP]
            if value > 0
        ]

    return {
        "tetris": top(tetris_best),
        "quiz": top(quiz_best),
        "typing": top(typing_best),
        "scramble": top(scramble_best),
        "dictation": top(dictation_best),
    }


# --- 데일리 단어 퍼즐 (docs/specs/daily-puzzle.md) ---


def _puzzle_payload(answer: str, ko: str, guesses: list[str], solved: bool) -> dict:
    finished = solved or len(guesses) >= daily_puzzle.MAX_TRIES
    return {
        "available": True,
        "length": len(answer),
        "max_tries": daily_puzzle.MAX_TRIES,
        "guesses": [{"word": g, "marks": daily_puzzle.grade(answer, g)} for g in guesses],
        "solved": solved,
        "finished": finished,
        # 정답·뜻은 끝났을 때만 공개 — 끝나면 학습 모먼트로 뜻까지 보여준다
        "answer": answer if finished else None,
        "answer_ko": ko if finished else None,
        # 뜻 힌트는 2번 시도부터 해금 (정답 단어는 비공개 유지)
        "hint_ko": ko if (finished or len(guesses) >= daily_puzzle.HINT_AFTER_TRIES) else None,
    }


async def _load_play(db: AsyncSession, user_id: int, day) -> DailyPuzzlePlay | None:
    return (
        await db.execute(
            select(DailyPuzzlePlay).where(
                DailyPuzzlePlay.user_id == user_id, DailyPuzzlePlay.day == day
            )
        )
    ).scalar_one_or_none()


@router.get("/puzzle")
async def daily_puzzle_state(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    day = daily_puzzle.today_kst()
    play = await _load_play(db, user.id, day)
    if play is not None and play.answer:
        answer = play.answer
        ko = (await daily_puzzle.candidates(db)).get(answer, "")
    else:
        picked = await daily_puzzle.puzzle_of_day(db, day)
        if picked is None:
            return {"available": False}
        answer, ko = picked
    return {
        "day": day.isoformat(),
        **_puzzle_payload(
            answer, ko, list(play.guesses or []) if play else [], play.solved if play else False
        ),
    }


class PuzzleGuess(BaseModel):
    word: str


@router.post("/puzzle/guess")
async def daily_puzzle_guess(
    body: PuzzleGuess,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    day = daily_puzzle.today_kst()
    play = await _load_play(db, user.id, day)
    if play is None:
        picked = await daily_puzzle.puzzle_of_day(db, day)
        if picked is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "puzzle_unavailable")
        answer, ko = picked
        play = DailyPuzzlePlay(user_id=user.id, day=day, answer=answer, guesses=[])
        db.add(play)
    else:
        answer = play.answer
        ko = (await daily_puzzle.candidates(db)).get(answer, "")

    guesses = list(play.guesses or [])
    if play.solved or len(guesses) >= daily_puzzle.MAX_TRIES:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_finished")
    word = body.word.strip().lower()
    if len(word) != len(answer) or not (word.isascii() and word.isalpha()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_word")

    guesses.append(word)
    play.guesses = guesses
    if word == answer:
        play.solved = True
    try:
        await db.commit()
    except IntegrityError:
        # 동시 첫 추측 경합 (uq_puzzle_user_day) — 새로고침 후 재시도 유도
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "retry") from None
    return {"day": day.isoformat(), **_puzzle_payload(answer, ko, guesses, play.solved)}


def _parse_content_ids(msg: dict) -> list[int] | None:
    raw = msg.get("content_ids")
    if not raw or not isinstance(raw, list):
        return None
    ids = [int(v) for v in raw if str(v).isdigit()][:20]
    return ids or None


@ws_router.websocket("/ws/game")
async def game_ws(websocket: WebSocket) -> None:
    # 쿠키 JWT 인증 (docs/specs/auth.md — WS 는 핸드셰이크 쿠키 사용)
    token = websocket.cookies.get(SESSION_COOKIE)
    if not token:
        await websocket.close(code=4401)
        return
    try:
        claims = decode_session_token(token)
        user_id = int(claims["sub"])
    except (pyjwt.PyJWTError, KeyError, ValueError):
        await websocket.close(code=4401)
        return

    async with get_session_factory()() as db:
        user = await db.get(User, user_id)
    if user is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    async def send(message: dict) -> None:
        await websocket.send_json(message)

    # 프레즌스 등록 (친구 초대 수신용) + 진행 중이던 매치 자동 복귀
    invite_hub.attach(user_id, user.nickname, send)
    await manager.attach(user_id, send)

    try:
        while True:
            msg = await websocket.receive_json()
            t = msg.get("t")
            if t == "ping":
                await send({"t": "pong"})
            elif t == "queue.join":
                quiz = msg.get("quiz", "en")
                if msg.get("mode") == "pve":
                    try:
                        await manager.join_pve(
                            user_id,
                            user.nickname,
                            quiz,
                            int(msg.get("bot_level", 3)),
                            send,
                            content_ids=_parse_content_ids(msg),
                        )
                    except WordPoolError as exc:
                        await send({"t": "error", "code": str(exc)})
                else:
                    await manager.join_pvp_queue(user_id, user.nickname, quiz, send)
            elif t == "queue.leave":
                manager.leave_queue(user_id)
            elif t == "room.create":
                try:
                    await manager.create_room(
                        user_id,
                        user.nickname,
                        msg.get("quiz", "en"),
                        send,
                        content_ids=_parse_content_ids(msg),
                    )
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "room.join":
                try:
                    await manager.join_room(user_id, user.nickname, str(msg.get("code", "")), send)
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "input.submit":
                await manager.handle_input(
                    user_id, str(msg.get("text", "")), int(msg.get("seq", 0))
                )
            elif t == "item.use":
                await manager.handle_item(user_id, str(msg.get("item", "")))
            # --- 스피드 퀴즈 로얄 (docs/proposal/quiz-royale.md) ---
            elif t == "qr.solo":
                try:
                    await royale.solo(
                        user_id,
                        user.nickname,
                        send,
                        bot_level=int(msg.get("bot_level", 3)),
                        bots=int(msg.get("bots", 1)),
                        content_ids=_parse_content_ids(msg),
                        variant=str(msg.get("variant", "meaning")),
                    )
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "qr.create":
                try:
                    await royale.create(
                        user_id,
                        user.nickname,
                        send,
                        content_ids=_parse_content_ids(msg),
                        variant=str(msg.get("variant", "meaning")),
                    )
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "qr.join":
                await royale.join(user_id, user.nickname, send, str(msg.get("code", "")))
            elif t == "qr.start":
                try:
                    await royale.start(user_id)
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "qr.answer":
                await royale.answer(user_id, str(msg.get("answer", "")))
            elif t == "qr.leave":
                royale.detach(user_id)
            # --- 받아쓰기 배틀 (docs/specs/dictation-battle.md) ---
            elif t == "dt.solo":
                try:
                    await dictator.solo(user_id, user.nickname, send)
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "dt.create":
                try:
                    await dictator.create(user_id, user.nickname, send)
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "dt.join":
                try:
                    await dictator.join(user_id, user.nickname, send, str(msg.get("code", "")))
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "dt.begin":
                try:
                    await dictator.begin(user_id)
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "dt.submit":
                await dictator.submit(
                    user_id, idx=int(msg.get("idx", -1)), text=str(msg.get("text", ""))
                )
            elif t == "dt.leave":
                dictator.detach(user_id)
            # --- 어순 조립 레이스 (docs/specs/scramble-race.md) ---
            elif t == "sc.solo":
                try:
                    await scrambler.solo(user_id, user.nickname, send)
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "sc.create":
                try:
                    await scrambler.create(user_id, user.nickname, send)
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "sc.join":
                try:
                    await scrambler.join(user_id, user.nickname, send, str(msg.get("code", "")))
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "sc.begin":
                try:
                    await scrambler.begin(user_id)
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "sc.progress":
                await scrambler.progress(
                    user_id, idx=int(msg.get("idx", -1)), placed=int(msg.get("placed", 0))
                )
            elif t == "sc.done":
                await scrambler.done(
                    user_id, idx=int(msg.get("idx", -1)), mistakes=int(msg.get("mistakes", 0))
                )
            elif t == "sc.leave":
                scrambler.detach(user_id)
            # --- 영문 타자연습 (docs/specs/typing-race.md) ---
            elif t == "tp.solo":
                try:
                    await racer.solo(user_id, user.nickname, send)
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "tp.create":
                try:
                    await racer.create(user_id, user.nickname, send)
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "tp.join":
                try:
                    await racer.join(user_id, user.nickname, send, str(msg.get("code", "")))
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "tp.begin":
                try:
                    await racer.begin(user_id)
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "tp.typing":
                await racer.typing(
                    user_id, idx=int(msg.get("idx", -1)), chars=int(msg.get("chars", 0))
                )
            elif t == "tp.done":
                await racer.done(
                    user_id,
                    idx=int(msg.get("idx", -1)),
                    chars=int(msg.get("chars", 0)),
                    errors=int(msg.get("errors", 0)),
                )
            elif t == "tp.leave":
                racer.detach(user_id)
            # --- 학습 관전 (승인제 릴레이 — docs/specs/study-spectate.md) ---
            elif t == "st.host":
                await spectate_hub.host(user_id, user.nickname, send)
            elif t == "st.request":
                await spectate_hub.request(user_id, user.nickname, send, str(msg.get("code", "")))
            elif t == "st.allow":
                await spectate_hub.allow(
                    user_id,
                    watcher_id=int(msg.get("watcher_id", 0)),
                    allow=bool(msg.get("allow", False)),
                )
            elif t == "st.event":
                payload = msg.get("payload")
                if isinstance(payload, dict):
                    await spectate_hub.event(user_id, payload)
            elif t == "st.chat":
                await spectate_hub.chat(user_id, str(msg.get("text", "")))
            elif t == "st.cheer":
                await spectate_hub.cheer(user_id, str(msg.get("kind", "")))
            elif t == "st.leave":
                await spectate_hub.detach(user_id)
            # --- 친구 게임 초대 (P2 경쟁 루프) ---
            elif t == "iv.invite":
                to_user_id = int(msg.get("to_user_id", 0))
                game = str(msg.get("game", ""))
                code = str(msg.get("code", ""))
                via: str | None = None
                # 수락된 친구에게만 — 임의 user_id 초대(스팸 푸시) 차단
                async with get_session_factory()() as invite_db:
                    if await are_friends(invite_db, user_id, to_user_id):
                        if await invite_hub.invite(
                            user_id, to_user_id=to_user_id, game=game, code=code
                        ):
                            via = "ws"
                        elif game in GAMES and await push_service.send_to_user(
                            invite_db,
                            to_user_id,
                            invite_push_payload(user.nickname, game, code),
                        ):
                            # 접속 중이 아니면 웹 푸시 초대장 — 클릭 시 자동 입장
                            via = "push"
                        await invite_db.commit()
                await send({"t": "iv.sent", "ok": via is not None, "via": via})
            else:
                await send({"t": "error", "code": "unknown_message"})
    except WebSocketDisconnect:
        invite_hub.detach(user_id, send)
        manager.detach(user_id)
        royale.detach(user_id)
        racer.detach(user_id)
        scrambler.detach(user_id)
        dictator.detach(user_id)
        await spectate_hub.detach(user_id)
    except Exception:
        logger.exception("ws error user=%s", user_id)
        invite_hub.detach(user_id, send)
        manager.detach(user_id)
        royale.detach(user_id)
        racer.detach(user_id)
        scrambler.detach(user_id)
        dictator.detach(user_id)
        await spectate_hub.detach(user_id)
