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
from app.models import GameMatch, User
from app.services.game.manager import WordPoolError, manager

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
    return {"played": played, "wins": wins, "losses": played - wins, "best_score": best_score or 0}


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

    # 진행 중이던 매치가 있으면 자동 복귀
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
            else:
                await send({"t": "error", "code": "unknown_message"})
    except WebSocketDisconnect:
        manager.detach(user_id)
    except Exception:
        logger.exception("ws error user=%s", user_id)
        manager.detach(user_id)
