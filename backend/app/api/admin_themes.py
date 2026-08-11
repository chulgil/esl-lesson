"""백오피스 테마 몰 — 무료/제한 전환 + 제한 테마 수동 지급/회수 (docs/specs/theme-mall.md)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import require_admin
from app.models import ThemeGrant, ThemeRewardRule, ThemeSetting, User
from app.services.achievements import DEFINITIONS
from app.services.notifications import notify
from app.services.themes import FALLBACK_THEME, THEME_ACCESS, effective_theme_access

router = APIRouter(prefix="/admin/themes", tags=["admin"], dependencies=[Depends(require_admin)])


def _grant_dict(grant: ThemeGrant, email: str, nickname: str) -> dict:
    return {
        "id": grant.id,
        "email": email,
        "nickname": nickname,
        "note": grant.note,
        "created_at": grant.created_at,
    }


async def restricted_or_raise(db: AsyncSession, theme_key: str) -> None:
    access = (await effective_theme_access(db)).get(theme_key)
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
    access_map = await effective_theme_access(db)
    prices = dict((await db.execute(select(ThemeSetting.theme_key, ThemeSetting.price_xp))).all())
    return {
        "items": [
            {
                "key": key,
                "access": access,
                "grants": counts.get(key, 0),
                "price_xp": prices.get(key),
            }
            for key, access in access_map.items()
        ]
    }


class AccessPatch(BaseModel):
    access: Literal["free", "restricted"]


@router.patch("/{theme_key}")
async def set_theme_access(
    theme_key: str, body: AccessPatch, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    """무료/제한 전환 — 제한 전환 시 grant 없는 사용자는 다음 조회부터 잠기고
    클라 가드가 note 로 복귀시킨다. grants 행은 보존 (재제한 시 다시 유효)."""
    if theme_key not in THEME_ACCESS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "theme_not_found")
    if theme_key == FALLBACK_THEME and body.access == "restricted":
        # note 는 잠금 복귀 목적지 — 제한하면 복귀 루프가 생긴다
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "fallback_theme_locked")

    setting = await db.get(ThemeSetting, theme_key)
    if setting is None:
        db.add(ThemeSetting(theme_key=theme_key, access=body.access))
    else:
        setting.access = body.access
    await db.commit()
    return {"key": theme_key, "access": body.access}


class PricePatch(BaseModel):
    # null = 판매 중단 (XP 상점에서 내려감)
    price_xp: int | None = Field(default=None, ge=1, le=1_000_000)


@router.patch("/{theme_key}/price")
async def set_theme_price(
    theme_key: str, body: PricePatch, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    """XP 상점 가격 설정 (theme-mall.md XP 상점) — restricted 테마만.

    업적 보상 규칙과 독립 — 같은 테마를 업적으로도 얻고 XP 로도 살 수 있다
    (2026-08-05 사용자 결정). 보상 전용으로 두려면 가격을 비워두면 된다.
    """
    await restricted_or_raise(db, theme_key)
    setting = await db.get(ThemeSetting, theme_key)
    if setting is None:
        # 행 없음 = 카탈로그 기본값 사용 중 — 기본 access 를 그대로 물려받아 생성
        db.add(
            ThemeSetting(
                theme_key=theme_key, access=THEME_ACCESS[theme_key], price_xp=body.price_xp
            )
        )
    else:
        setting.price_xp = body.price_xp
    await db.commit()
    return {"key": theme_key, "price_xp": body.price_xp}


class RewardRuleCreate(BaseModel):
    achievement_key: str
    theme_key: str


@router.get("/rewards")
async def list_reward_rules(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    """업적→테마 보상 규칙 + 업적 카탈로그 (폼 셀렉트용)."""
    titles = {d[0]: d[1] for d in DEFINITIONS}
    rows = (await db.execute(select(ThemeRewardRule).order_by(ThemeRewardRule.id))).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "achievement_key": r.achievement_key,
                "achievement_title": titles.get(r.achievement_key, r.achievement_key),
                "theme_key": r.theme_key,
                "created_at": r.created_at,
            }
            for r in rows
        ],
        "achievements": [{"key": d[0], "title": d[1]} for d in DEFINITIONS],
    }


@router.post("/rewards")
async def create_reward_rule(
    body: RewardRuleCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    """규칙 추가 — 이후 해당 업적 달성자(과거 달성 포함, 소급)에게 테마 지급."""
    titles = {d[0]: d[1] for d in DEFINITIONS}
    if body.achievement_key not in titles:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "achievement_not_found")
    await restricted_or_raise(db, body.theme_key)
    duplicate = (
        await db.execute(
            select(ThemeRewardRule.id).where(
                ThemeRewardRule.achievement_key == body.achievement_key,
                ThemeRewardRule.theme_key == body.theme_key,
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_mapped")

    rule = ThemeRewardRule(achievement_key=body.achievement_key, theme_key=body.theme_key)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {
        "id": rule.id,
        "achievement_key": rule.achievement_key,
        "achievement_title": titles[rule.achievement_key],
        "theme_key": rule.theme_key,
        "created_at": rule.created_at,
    }


@router.delete("/rewards/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reward_rule(rule_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    """규칙 삭제 — 이후 지급만 중단. 이미 지급된 theme_grants 는 유지 (보유 보장)."""
    rule = await db.get(ThemeRewardRule, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rule_not_found")
    await db.delete(rule)
    await db.commit()


@router.get("/{theme_key}/grants")
async def list_grants(theme_key: str, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    await restricted_or_raise(db, theme_key)
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


async def _duplicate_theme_grant(db: AsyncSession, user_id: int, theme_key: str) -> bool:
    row = (
        await db.execute(
            select(ThemeGrant.id).where(
                ThemeGrant.user_id == user_id, ThemeGrant.theme_key == theme_key
            )
        )
    ).scalar_one_or_none()
    return row is not None


@router.post("/{theme_key}/grants")
async def create_grant(
    theme_key: str,
    body: GrantCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    await restricted_or_raise(db, theme_key)
    user = (
        await db.execute(select(User).where(func.lower(User.email) == body.email.strip().lower()))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
    if await _duplicate_theme_grant(db, user.id, theme_key):
        raise HTTPException(status.HTTP_409_CONFLICT, "already_granted")

    grant = ThemeGrant(user_id=user.id, theme_key=theme_key, note=body.note, granted_by=admin.id)
    db.add(grant)
    try:
        await db.flush()
    except IntegrityError:
        # 동시 지급 경합 (uq_theme_grants_user_theme) — 이미 지급됨
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "already_granted") from None
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
