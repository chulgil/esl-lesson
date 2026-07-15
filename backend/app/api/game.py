"""게임 API — WS 대전 + REST 전적 (docs/specs/word-tetris.md)."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt as pyjwt
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db, get_session_factory
from app.core.security import SESSION_COOKIE, decode_session_token, get_current_user
from app.models import GameMatch, QuizRoyaleMatch, TypingRace, User
from app.services.game import records
from app.services.game.invites import invite_hub
from app.services.game.manager import WordPoolError, manager
from app.services.game.quiz_royale import royale
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

    quiz_best = 0
    quiz_rows = (
        (
            await db.execute(
                select(QuizRoyaleMatch.players).where(QuizRoyaleMatch.status == "finished")
            )
        )
        .scalars()
        .all()
    )
    for payload in quiz_rows:
        for p in (payload or {}).get("players", []):
            if p.get("user_id") == user.id:
                quiz_best = max(quiz_best, int(p.get("score") or 0))

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

    return {
        "tetris_best_score": tetris or 0,
        "quiz_best_score": quiz_best,
        "typing_best_cpm": typing_best,
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
            select(User.name, func.sum(union.c.score).label("total"))
            .join(User, User.id == union.c.uid)
            .group_by(User.id, User.name)
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

    # 퀴즈 로얄: players JSON 에서 유저별 최고 점수 (봇=user_id None 제외)
    quiz_best: dict[int, int] = {}
    for payload in (
        (
            await db.execute(
                select(QuizRoyaleMatch.players).where(
                    QuizRoyaleMatch.status == "finished", QuizRoyaleMatch.ended_at >= since
                )
            )
        )
        .scalars()
        .all()
    ):
        for p in (payload or {}).get("players", []):
            uid = p.get("user_id")
            if uid is None:
                continue
            quiz_best[uid] = max(quiz_best.get(uid, 0), int(p.get("score") or 0))

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

    all_ids = set(tetris_best) | set(quiz_best) | set(typing_best)
    names: dict[int, str] = {}
    if all_ids:
        names = dict(
            (await db.execute(select(User.id, User.name).where(User.id.in_(all_ids)))).all()
        )

    def top(best: dict[int, int]) -> list[dict]:
        ranked = sorted(best.items(), key=lambda kv: (-kv[1], names.get(kv[0], "")))
        return [
            {"name": names.get(uid, "?"), "value": value, "me": uid == user.id}
            for uid, value in ranked[:LEADERBOARD_TOP]
            if value > 0
        ]

    return {"tetris": top(tetris_best), "quiz": top(quiz_best), "typing": top(typing_best)}


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
    invite_hub.attach(user_id, user.name, send)
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
                            user.name,
                            quiz,
                            int(msg.get("bot_level", 3)),
                            send,
                            content_ids=_parse_content_ids(msg),
                        )
                    except WordPoolError as exc:
                        await send({"t": "error", "code": str(exc)})
                else:
                    await manager.join_pvp_queue(user_id, user.name, quiz, send)
            elif t == "queue.leave":
                manager.leave_queue(user_id)
            elif t == "room.create":
                try:
                    await manager.create_room(
                        user_id,
                        user.name,
                        msg.get("quiz", "en"),
                        send,
                        content_ids=_parse_content_ids(msg),
                    )
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "room.join":
                try:
                    await manager.join_room(user_id, user.name, str(msg.get("code", "")), send)
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
                        user.name,
                        send,
                        bot_level=int(msg.get("bot_level", 3)),
                        bots=int(msg.get("bots", 1)),
                        content_ids=_parse_content_ids(msg),
                    )
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "qr.create":
                try:
                    await royale.create(
                        user_id, user.name, send, content_ids=_parse_content_ids(msg)
                    )
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "qr.join":
                await royale.join(user_id, user.name, send, str(msg.get("code", "")))
            elif t == "qr.start":
                try:
                    await royale.start(user_id)
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "qr.answer":
                await royale.answer(user_id, str(msg.get("answer", "")))
            elif t == "qr.leave":
                royale.detach(user_id)
            # --- 영문 타자연습 (docs/specs/typing-race.md) ---
            elif t == "tp.solo":
                try:
                    await racer.solo(user_id, user.name, send)
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "tp.create":
                try:
                    await racer.create(user_id, user.name, send)
                except WordPoolError as exc:
                    await send({"t": "error", "code": str(exc)})
            elif t == "tp.join":
                try:
                    await racer.join(user_id, user.name, send, str(msg.get("code", "")))
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
                await spectate_hub.host(user_id, user.name, send)
            elif t == "st.request":
                await spectate_hub.request(user_id, user.name, send, str(msg.get("code", "")))
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
            elif t == "st.leave":
                await spectate_hub.detach(user_id)
            # --- 친구 게임 초대 (P2 경쟁 루프) ---
            elif t == "iv.invite":
                delivered = await invite_hub.invite(
                    user_id,
                    to_user_id=int(msg.get("to_user_id", 0)),
                    game=str(msg.get("game", "")),
                    code=str(msg.get("code", "")),
                )
                await send({"t": "iv.sent", "ok": delivered})
            else:
                await send({"t": "error", "code": "unknown_message"})
    except WebSocketDisconnect:
        invite_hub.detach(user_id, send)
        manager.detach(user_id)
        royale.detach(user_id)
        racer.detach(user_id)
        await spectate_hub.detach(user_id)
    except Exception:
        logger.exception("ws error user=%s", user_id)
        invite_hub.detach(user_id, send)
        manager.detach(user_id)
        royale.detach(user_id)
        racer.detach(user_id)
        await spectate_hub.detach(user_id)
