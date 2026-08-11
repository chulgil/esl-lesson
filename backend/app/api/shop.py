"""XP 상점 — 마스코트·악세사리·책갈피 구매 (docs/specs/mascot-shop.md).

테마 구매(api/themes.py)와 같은 원칙: 가용 XP(누적-소비)에서 차감, 레벨 불변,
보유 = 원장 행 존재, 동시 구매 경합은 uq 로 409.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import ItemGrant, XpSpend
from app.models.user import User, UserSettings
from app.services import progress
from app.services.mascots import MASCOTS, OUTFITS, STREAK_SAVER_PRICE_XP, item_price
from app.services.retention import SAVER_MAX

router = APIRouter(prefix="/shop", tags=["shop"])


async def _settings_of(db: AsyncSession, user_id: int) -> UserSettings:
    settings = await db.get(UserSettings, user_id)
    if settings is None:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        await db.flush()
    return settings


async def _owned_keys(db: AsyncSession, user_id: int) -> set[str]:
    rows = (
        await db.execute(select(ItemGrant.item_key).where(ItemGrant.user_id == user_id))
    ).scalars()
    return set(rows)


@router.get("")
async def shop_catalog(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """카탈로그 + 지갑 + 보유·활성 상태 — 설정 화면 상점 섹션과 마스코트 렌더러 공용."""
    owned = await _owned_keys(db, user.id)
    settings = await _settings_of(db, user.id)
    available = await progress.available_xp(db, user.id)
    return {
        "available_xp": available,
        "active_mascot": settings.mascot_key,
        "mascots": [
            {
                "key": key,
                "label": meta["label"],
                "price_xp": meta["price_xp"],
                "owned": f"mascot:{key}" in owned,
            }
            for key, meta in MASCOTS.items()
        ],
        # 악세는 all-on — 보유하면 활성 마스코트에 전부 착용 (2026-08-11 사용자 결정)
        "outfits": [
            {
                "key": key,
                "label": meta["label"],
                "price_xp": meta["price_xp"],
                "owned": f"outfit:{key}" in owned,
            }
            for key, meta in OUTFITS.items()
        ],
        "streak_saver": {
            "price_xp": STREAK_SAVER_PRICE_XP,
            "count": settings.streak_savers,
            "max": SAVER_MAX,
        },
    }


class PurchaseIn(BaseModel):
    item_key: str  # "mascot:henyang" | "outfit:ribbon"


@router.post("/purchase")
async def purchase_item(
    body: PurchaseIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    price = item_price(body.item_key)
    if price is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item_not_found")
    owned = await _owned_keys(db, user.id)
    if body.item_key in owned:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_owned")
    available = await progress.available_xp(db, user.id)
    if available < price:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "insufficient_xp")

    db.add(XpSpend(user_id=user.id, amount=price, reason=body.item_key))
    db.add(ItemGrant(user_id=user.id, item_key=body.item_key, note="XP 구매"))
    settings = await _settings_of(db, user.id)
    kind, _, key = body.item_key.partition(":")
    if kind == "mascot":
        # 산 캐릭터는 즉시 화면에 — 활성 마스코트로 자동 전환 (2026-08-11 기획)
        settings.mascot_key = key
    try:
        await db.commit()
    except IntegrityError as exc:  # 동시 구매 경합 (uq_item_grants_user_key)
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "already_owned") from exc
    return {
        "item_key": body.item_key,
        "available_xp": available - price,
        "active_mascot": settings.mascot_key,
    }


class MascotIn(BaseModel):
    key: str | None  # null = 마스코트 끄기


@router.patch("/mascot")
async def set_active_mascot(
    body: MascotIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if body.key is not None:
        if body.key not in MASCOTS:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "mascot_not_found")
        owned = await _owned_keys(db, user.id)
        if f"mascot:{body.key}" not in owned:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "not_owned")
    settings = await _settings_of(db, user.id)
    settings.mascot_key = body.key
    await db.commit()
    return {"active_mascot": settings.mascot_key}


@router.post("/streak-saver/purchase")
async def purchase_streak_saver(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """책갈피 충전 — 주 1회 무료 지급과 별개의 XP 구매 (최대 보유 SAVER_MAX 동일)."""
    settings = await _settings_of(db, user.id)
    if settings.streak_savers >= SAVER_MAX:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "saver_full")
    available = await progress.available_xp(db, user.id)
    if available < STREAK_SAVER_PRICE_XP:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "insufficient_xp")
    db.add(XpSpend(user_id=user.id, amount=STREAK_SAVER_PRICE_XP, reason="saver:streak"))
    settings.streak_savers += 1
    await db.commit()
    return {
        "count": settings.streak_savers,
        "available_xp": available - STREAK_SAVER_PRICE_XP,
    }
