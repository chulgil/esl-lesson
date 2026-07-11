"""세션 JWT 발급/검증 + FastAPI 인증 의존성 (docs/specs/auth.md)."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.models.user import ROLE_ADMIN, User

SESSION_COOKIE = "els_session"
STATE_COOKIE = "els_oauth_state"
ALGORITHM = "HS256"


def create_session_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expires_hours),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


def decode_session_token(token: str) -> dict:
    """만료/변조 시 jwt 예외를 그대로 올린다 — 호출부에서 401 변환."""
    return jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])


def create_state_token(next_path: str) -> tuple[str, str]:
    """OAuth CSRF state. (쿠키용 서명 토큰, 쿼리용 nonce) 쌍을 만든다."""
    settings = get_settings()
    nonce = secrets.token_urlsafe(24)
    token = jwt.encode(
        {
            "nonce": nonce,
            "next": next_path,
            "exp": datetime.now(UTC) + timedelta(minutes=10),
        },
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )
    return token, nonce


def verify_state_token(token: str, nonce: str) -> str:
    """state 검증 후 next 경로 반환. 실패 시 400."""
    try:
        claims = decode_session_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid oauth state") from exc
    if not secrets.compare_digest(claims.get("nonce", ""), nonce):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "oauth state mismatch")
    return safe_next_path(claims.get("next", "/"))


def safe_next_path(next_path: str) -> str:
    """오픈 리다이렉트 방지: 자체 도메인 상대경로만 허용."""
    if not next_path.startswith("/") or next_path.startswith("//"):
        return "/"
    return next_path


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    els_session: Annotated[str | None, Cookie()] = None,
) -> User:
    if not els_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    try:
        claims = decode_session_token(els_session)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session") from exc
    user = await db.get(User, int(claims["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
    return user


async def require_admin(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """admin 가드 — 강등 즉시 반영을 위해 DB에서 role 재확인 (docs/specs/auth.md)."""
    result = await db.execute(select(User.role).where(User.id == user.id))
    role = result.scalar_one_or_none()
    if role != ROLE_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")
    return user
