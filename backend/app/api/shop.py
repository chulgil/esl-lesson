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
from app.models import ItemGrant, Purchase, XpSpend
from app.models.user import User, UserSettings
from app.services import progress
from app.services.mascots import (
    MASCOTS,
    OUTFITS,
    STREAK_SAVER_PRICE_XP,
    item_policies,
    item_price,
)
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
    policies = await item_policies(db)
    return {
        "available_xp": available,
        "active_mascot": settings.mascot_key,
        "mascots": [
            {
                "key": key,
                "label": meta["label"],
                "price_xp": policies[f"mascot:{key}"]["price_xp"],
                "sale": policies[f"mascot:{key}"]["sale"],
                "owned": f"mascot:{key}" in owned,
            }
            for key, meta in MASCOTS.items()
        ],
        # 악세 착용: NULL=보유분 전부 착용(구 all-on), 목록=그것만 착용
        # (2026-08-21 착용해제 토글 — 사용자 요청으로 all-on 정책 개정)
        "outfits": [
            {
                "key": key,
                "label": meta["label"],
                "price_xp": policies[f"outfit:{key}"]["price_xp"],
                "sale": policies[f"outfit:{key}"]["sale"],
                "owned": f"outfit:{key}" in owned,
                "worn": f"outfit:{key}" in owned
                and (settings.mascot_outfits is None or key in settings.mascot_outfits),
            }
            for key, meta in OUTFITS.items()
        ],
        "streak_saver": {
            "price_xp": STREAK_SAVER_PRICE_XP,
            "count": settings.streak_savers,
            "max": SAVER_MAX,
        },
    }


PURCHASE_HISTORY_LIMIT = 50


@router.get("/purchases")
async def purchase_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """내 구매 이력 — 품목·결제수단·금액·시각 (최신순). 라벨은 프론트가 결정."""
    rows = (
        (
            await db.execute(
                select(Purchase)
                .where(Purchase.user_id == user.id)
                .order_by(Purchase.id.desc())
                .limit(PURCHASE_HISTORY_LIMIT)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "item_key": p.item_key,
                "method": p.method,
                "amount": p.amount,
                "currency": p.currency,
                "created_at": p.created_at.isoformat(),
            }
            for p in rows
        ]
    }


class PurchaseIn(BaseModel):
    item_key: str  # "mascot:henyang" | "outfit:ribbon"


@router.post("/purchase")
async def purchase_item(
    body: PurchaseIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if item_price(body.item_key) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item_not_found")
    policy = (await item_policies(db))[body.item_key]
    if policy["sale"] == "event":
        # 이벤트 지급 전용 — 잔액과 무관하게 XP 구매 차단 (백오피스 설정)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "event_only_item")
    price = policy["price_xp"]
    owned = await _owned_keys(db, user.id)
    if body.item_key in owned:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_owned")
    available = await progress.available_xp(db, user.id)
    if available < price:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "insufficient_xp")

    xp_spend = XpSpend(user_id=user.id, amount=price, reason=body.item_key)
    purchase = Purchase(user_id=user.id, item_key=body.item_key, method="xp", amount=price)
    grant = ItemGrant(user_id=user.id, item_key=body.item_key, note="XP 구매")
    db.add(xp_spend)
    db.add(purchase)
    db.add(grant)
    settings = await _settings_of(db, user.id)
    prev_mascot_key = settings.mascot_key
    kind, _, key = body.item_key.partition(":")
    if kind == "mascot":
        # 산 캐릭터는 즉시 화면에 — 활성 마스코트로 자동 전환 (2026-08-11 기획)
        settings.mascot_key = key
    if kind == "outfit" and settings.mascot_outfits is not None:
        # 착용 목록 관리 중이면 새 악세도 즉시 착용 (구매 보상 체감)
        settings.mascot_outfits = [*settings.mascot_outfits, key]
    try:
        await db.commit()
    except IntegrityError as exc:  # 동시 구매 경합 (uq_item_grants_user_key)
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "already_owned") from exc

    # 사전 검증(above)과 커밋 사이 다른 구매가 끼는 TOCTOU 경합 — 커밋 후
    # 재검증으로 가용 XP 음수를 잡아내고 방금 산 아이템을 되돌린다 (2026-08-11)
    if await progress.revert_if_overdrawn(
        db,
        user.id,
        [xp_spend, purchase, grant],
        extra_revert=lambda: setattr(settings, "mascot_key", prev_mascot_key),
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "insufficient_xp")

    return {
        "item_key": body.item_key,
        "available_xp": available - price,
        "active_mascot": settings.mascot_key,
    }


class OutfitIn(BaseModel):
    key: str
    worn: bool


@router.patch("/outfit")
async def set_outfit_worn(
    body: OutfitIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """악세사리 착용/해제 토글 (2026-08-21 사용자 요청 — 구 all-on 정책 개정).

    첫 토글 시 NULL(전부 착용)을 보유 목록으로 구체화한 뒤 반영한다."""
    if body.key not in OUTFITS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "outfit_not_found")
    owned = await _owned_keys(db, user.id)
    if f"outfit:{body.key}" not in owned:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_owned")
    settings = await _settings_of(db, user.id)
    worn_now = (
        [k for k in OUTFITS if f"outfit:{k}" in owned]
        if settings.mascot_outfits is None
        else list(settings.mascot_outfits)
    )
    if body.worn and body.key not in worn_now:
        worn_now.append(body.key)
    if not body.worn and body.key in worn_now:
        worn_now.remove(body.key)
    settings.mascot_outfits = worn_now
    await db.commit()
    return {"outfits_worn": worn_now}


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
    xp_spend = XpSpend(user_id=user.id, amount=STREAK_SAVER_PRICE_XP, reason="saver:streak")
    purchase = Purchase(
        user_id=user.id, item_key="saver:streak", method="xp", amount=STREAK_SAVER_PRICE_XP
    )
    db.add(xp_spend)
    db.add(purchase)
    prev_savers = settings.streak_savers
    settings.streak_savers = prev_savers + 1
    await db.commit()

    # 사전 검증과 커밋 사이 다른 구매가 끼는 TOCTOU 경합 — 커밋 후 재검증으로
    # 가용 XP 음수를 잡아내고 방금 늘린 책갈피 개수를 되돌린다 (2026-08-11)
    if await progress.revert_if_overdrawn(
        db,
        user.id,
        [xp_spend, purchase],
        extra_revert=lambda: setattr(settings, "streak_savers", prev_savers),
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "insufficient_xp")

    return {
        "count": settings.streak_savers,
        "available_xp": available - STREAK_SAVER_PRICE_XP,
    }
