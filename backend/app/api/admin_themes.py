"""백오피스 테마 몰 — 제한 테마 수동 지급/회수 (docs/specs/theme-mall.md)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import require_admin
from app.models import ThemeGrant, User
from app.services.notifications import notify
from app.services.themes import THEME_ACCESS

router = APIRouter(prefix="/admin/themes", tags=["admin"], dependencies=[Depends(require_admin)])


def _grant_dict(grant: ThemeGrant, email: str, nickname: str) -> dict:
    return {
        "id": grant.id,
        "email": email,
        "nickname": nickname,
        "note": grant.note,
        "created_at": grant.created_at,
    }


def restricted_or_raise(theme_key: str) -> None:
    access = THEME_ACCESS.get(theme_key)
    if access is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "theme_not_found")
    if access != "restricted":
        # free 는 전원 사용 가능이라 지급 자체가 무의미 — 실수 방지 게이트
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "theme_not_restricted")


@router.get("")
async def theme_stats(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    """카탈로그 + 테마별 보유자 수 — 몰 첫 화면."""
    counts = dict(
        (
            await db.execute(
                select(ThemeGrant.theme_key, func.count(ThemeGrant.id)).group_by(
                    ThemeGrant.theme_key
                )
            )
        ).all()
    )
    return {
        "items": [
            {"key": key, "access": access, "grants": counts.get(key, 0)}
            for key, access in THEME_ACCESS.items()
        ]
    }


@router.get("/{theme_key}/grants")
async def list_grants(theme_key: str, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    restricted_or_raise(theme_key)
    rows = (
        await db.execute(
            select(ThemeGrant, User.email, User.nickname)
            .join(User, User.id == ThemeGrant.user_id)
            .where(ThemeGrant.theme_key == theme_key)
            .order_by(ThemeGrant.id.desc())
        )
    ).all()
    return {"items": [_grant_dict(grant, email, nickname) for grant, email, nickname in rows]}


class GrantCreate(BaseModel):
    email: str
    note: str | None = None


@router.post("/{theme_key}/grants")
async def create_grant(
    theme_key: str,
    body: GrantCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    restricted_or_raise(theme_key)
    user = (
        await db.execute(select(User).where(func.lower(User.email) == body.email.strip().lower()))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
    duplicate = (
        await db.execute(
            select(ThemeGrant.id).where(
                ThemeGrant.user_id == user.id, ThemeGrant.theme_key == theme_key
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_granted")

    grant = ThemeGrant(user_id=user.id, theme_key=theme_key, note=body.note, granted_by=admin.id)
    db.add(grant)
    await db.flush()
    # 지급 알림 — 벨에서 "새 테마가 열렸어요". payload 는 지급 시점 스냅샷
    await notify(db, user.id, "theme_granted", {"theme_key": theme_key, "note": body.note})
    await db.commit()
    # created_at 은 server default — INSERT 후 미로딩 상태라 명시 refresh
    await db.refresh(grant)
    return _grant_dict(grant, user.email, user.nickname)


@router.delete("/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_grant(grant_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    """회수 — 다음 카탈로그 조회부터 잠김. 클라 가드가 note 로 자동 복귀시킨다."""
    grant = await db.get(ThemeGrant, grant_id)
    if grant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "grant_not_found")
    await db.delete(grant)
    await db.commit()
