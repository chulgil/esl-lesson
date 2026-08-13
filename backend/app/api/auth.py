"""Google OAuth 2.0 Authorization Code 흐름 (docs/specs/auth.md)."""

import logging
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.security import (
    SESSION_COOKIE,
    STATE_COOKIE,
    create_session_token,
    create_state_token,
    get_current_user,
    safe_next_path,
    verify_state_token,
)
from app.models import (
    Content,
    ContentSubscription,
    ItemGrant,
    Notification,
    Purchase,
    PushSubscription,
    ReviewCard,
    ReviewLog,
    ThemeGrant,
    XpSpend,
)
from app.models.user import ROLE_ADMIN, User, UserSettings
from app.services.content_service import delete_content_row
from app.services.nicknames import normalize_nickname, random_nickname

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def request_origin(request: Request, settings: Settings) -> str:
    """요청이 들어온 도메인 기준으로 콜백 origin 구성 (허용 목록 검증)."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    origin = f"{proto}://{host}"
    allowed = {
        settings.public_service_url.rstrip("/"),
        settings.public_admin_url.rstrip("/"),
        "http://localhost:3000",
        "http://localhost:8000",
    }
    if origin not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown origin")
    return origin


def set_session_cookie(response: RedirectResponse, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.jwt_expires_hours * 3600,
        domain=settings.cookie_domain or None,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.get("/login")
async def login(
    request: Request,
    next: str = Query(default="/"),
) -> RedirectResponse:
    settings = get_settings()
    origin = request_origin(request, settings)
    state_token, nonce = create_state_token(safe_next_path(next))
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": f"{origin}/api/auth/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": nonce,
        "prompt": "select_account",
    }
    response = RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")
    response.set_cookie(
        STATE_COOKIE,
        state_token,
        max_age=600,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/callback")
async def callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    code: str = Query(default=""),
    state: str = Query(default=""),
    els_oauth_state: Annotated[str | None, Cookie()] = None,
) -> RedirectResponse:
    settings = get_settings()
    origin = request_origin(request, settings)
    if not code or not els_oauth_state:
        return RedirectResponse(f"{origin}/login?error=oauth")
    next_path = verify_state_token(els_oauth_state, state)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_res = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": f"{origin}/api/auth/callback",
                    "grant_type": "authorization_code",
                },
            )
            token_res.raise_for_status()
            access_token = token_res.json()["access_token"]
            userinfo_res = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_res.raise_for_status()
            info = userinfo_res.json()
    except (httpx.HTTPError, KeyError):
        logger.exception("google oauth exchange failed")
        return RedirectResponse(f"{origin}/login?error=oauth")

    if not info.get("email_verified", False):
        return RedirectResponse(f"{origin}/login?error=unverified")

    user = await upsert_google_user(db, info, settings)
    response = RedirectResponse(f"{origin}{next_path}")
    response.delete_cookie(STATE_COOKIE)
    set_session_cookie(response, create_session_token(user), settings)
    return response


async def upsert_google_user(db: AsyncSession, info: dict, settings: Settings) -> User:
    """google_sub 기준 upsert + ADMIN_EMAILS 승격 + last_login 갱신."""
    result = await db.execute(select(User).where(User.google_sub == info["sub"]))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            google_sub=info["sub"],
            email=info["email"],
            name=info.get("name") or info["email"],
            # 타인에게 보이는 이름은 랜덤 닉네임 — 구글 이름을 초기값으로 쓰지 않는다
            nickname=random_nickname(),
            avatar_url=info.get("picture"),
        )
        db.add(user)
        await db.flush()
        db.add(UserSettings(user_id=user.id))
    if not user.nickname:  # 마이그레이션 이전 세션 등 방어적 채움
        user.nickname = random_nickname()
    if user.email.lower() in settings.admin_email_set:
        user.role = ROLE_ADMIN
    user.last_login_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/logout")
async def logout() -> RedirectResponse:
    settings = get_settings()
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE, domain=settings.cookie_domain or None)
    return response


me_router = APIRouter(tags=["auth"])


def _me_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "role": user.role,
        # 가입일 — 온보딩 체크리스트 조건부 노출(가입 3일 이내) 판정 (ux-redesign #8)
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@me_router.get("/me")
async def me(user: Annotated[User, Depends(get_current_user)]) -> dict:
    return _me_dict(user)


class MePatch(BaseModel):
    nickname: str


@me_router.patch("/me")
async def update_me(
    body: MePatch,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """닉네임 변경 — 다른 사용자에게 보이는 유일한 이름."""
    try:
        user.nickname = normalize_nickname(body.nickname)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    await db.commit()
    return _me_dict(user)


@me_router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """회원탈퇴 — 개인정보·학습 기록 즉시 파기 (개인정보처리방침의 파기 조항 구현).

    유저 행 삭제로 설정/카드/로그/구독이 CASCADE 되고, 공용 콘텐츠·타인과
    공유 중인 콘텐츠는 유지된다. 내가 마지막 구독자인 개인 콘텐츠만 본체 삭제.
    """
    settings = get_settings()
    my_private = (
        await db.execute(
            select(Content)
            .join(ContentSubscription, ContentSubscription.content_id == Content.id)
            .where(
                ContentSubscription.user_id == user.id,
                Content.visibility == "private",
            )
        )
    ).scalars()
    for content in my_private:
        others = (
            await db.execute(
                select(func.count(ContentSubscription.id)).where(
                    ContentSubscription.content_id == content.id,
                    ContentSubscription.user_id != user.id,
                )
            )
        ).scalar_one()
        if others == 0:
            await delete_content_row(db, content)

    # 파기 범위를 명시적으로 — DB CASCADE 에만 맡기지 않아 어떤 DB 에서도 동일 동작
    for table, col in (
        (ReviewLog.__table__, ReviewLog.user_id),
        (ReviewCard.__table__, ReviewCard.user_id),
        (ContentSubscription.__table__, ContentSubscription.user_id),
        (PushSubscription.__table__, PushSubscription.user_id),
        (Notification.__table__, Notification.user_id),
        (ThemeGrant.__table__, ThemeGrant.user_id),
        (UserSettings.__table__, UserSettings.user_id),
        (ItemGrant.__table__, ItemGrant.user_id),
        (Purchase.__table__, Purchase.user_id),
        (XpSpend.__table__, XpSpend.user_id),
    ):
        await db.execute(table.delete().where(col == user.id))
    await db.delete(user)
    await db.commit()
    response.delete_cookie(SESSION_COOKIE, domain=settings.cookie_domain or None)
