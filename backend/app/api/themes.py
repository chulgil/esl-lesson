"""사용자 테마 카탈로그 + XP 상점 API (docs/specs/theme-mall.md)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import Purchase, ThemeGrant, ThemeRewardRule, ThemeSetting, User, XpSpend
from app.services import progress
from app.services.achievements import DEFINITIONS
from app.services.theme_rewards import sync_theme_rewards
from app.services.themes import allowed_theme_keys, effective_theme_access

router = APIRouter(prefix="/themes", tags=["themes"])


@router.get("")
async def list_themes(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """카탈로그 전체 + 내 사용 가능 여부 — 표시 순서·라벨은 프론트 APP_THEMES 가 결정.

    보상 동기화를 allowed 판정보다 먼저 실행 — AppNav 가드가 달성 테마를
    잠김으로 오판해 note 로 되돌리는 일이 없다."""
    await sync_theme_rewards(db, user.id)
    allowed = set(await allowed_theme_keys(db, user.id, user.role))
    access_map = await effective_theme_access(db)

    # 잠긴 테마의 해금 업적 힌트 — 설정 화면 배지 문구 ("'첫 친구' 달성 시")
    # unlock_key 는 설정 화면이 업적 진행률(current/target)과 조인하는 키
    titles = {d[0]: d[1] for d in DEFINITIONS}
    rules = (await db.execute(select(ThemeRewardRule))).scalars().all()
    unlock_by_theme = {r.theme_key: r.achievement_key for r in rules}

    # XP 상점 — restricted 테마의 가격 (보상 규칙과 독립, theme-mall.md)
    prices = dict((await db.execute(select(ThemeSetting.theme_key, ThemeSetting.price_xp))).all())
    available = await progress.available_xp(db, user.id)

    return {
        "available_xp": available,
        "items": [
            {
                "key": key,
                "access": access,
                "allowed": key in allowed,
                "unlock": titles.get(unlock_by_theme.get(key, ""), None)
                if key in unlock_by_theme
                else None,
                "unlock_key": unlock_by_theme.get(key),
                # 업적 보상과 XP 판매는 독립 — 동시 설정 가능 (2026-08-05 결정)
                "price_xp": prices.get(key) if access == "restricted" else None,
            }
            for key, access in access_map.items()
        ],
    }


@router.post("/{theme_key}/purchase")
async def purchase_theme(
    theme_key: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """XP 로 테마 구매 — 가용 XP(누적-소비)에서 차감, 레벨은 불변.

    업적 보상 규칙과 XP 판매는 독립 설정 — 동시 사용 가능 (2026-08-05 결정:
    업적으로도 얻고 XP 로도 살 수 있다). 가격은 백오피스가
    theme_settings.price_xp 로 설정하며 NULL 은 미판매다. 기간 한정
    이벤트 판매는 후속(theme-mall.md XP 상점 P2).
    """
    access = (await effective_theme_access(db)).get(theme_key)
    if access is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "theme_not_found")
    if access != "restricted":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "theme_not_restricted")
    setting = await db.get(ThemeSetting, theme_key)
    price = setting.price_xp if setting else None
    if price is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "theme_not_for_sale")

    owned = (
        await db.execute(
            select(ThemeGrant.id).where(
                ThemeGrant.user_id == user.id, ThemeGrant.theme_key == theme_key
            )
        )
    ).first()
    if owned:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_owned")

    available = await progress.available_xp(db, user.id)
    if available < price:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "insufficient_xp")

    db.add(XpSpend(user_id=user.id, amount=price, reason=f"theme:{theme_key}"))
    db.add(Purchase(user_id=user.id, item_key=f"theme:{theme_key}", method="xp", amount=price))
    db.add(ThemeGrant(user_id=user.id, theme_key=theme_key, note="XP 구매", granted_by=None))
    try:
        await db.commit()
    except IntegrityError as exc:  # 동시 구매 경합 (uq_theme_grants_user_theme)
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "already_owned") from exc
    return {"key": theme_key, "allowed": True, "available_xp": available - price}
