"""백오피스 캐릭터 상점 — 가격 오버라이드·이벤트 한정·수동 지급 (mascot-shop.md).

테마 몰(admin_themes.py)과 같은 관리 모델: 카탈로그는 코드가 단일 근거,
판매 정책은 item_settings 오버라이드, 지급/회수는 item_grants 행.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import require_admin
from app.models import ItemGrant, ItemSetting, User
from app.services.mascots import MASCOTS, OUTFITS, item_policies, item_price
from app.services.notifications import notify

router = APIRouter(prefix="/admin/shop", tags=["admin"], dependencies=[Depends(require_admin)])


def _known_or_raise(item_key: str) -> None:
    if item_price(item_key) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item_not_found")


@router.get("")
async def item_stats(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    """카탈로그 + 판매 정책 + 아이템별 보유자 수 — 상점 관리 첫 화면."""
    counts = dict(
        (
            await db.execute(
                select(ItemGrant.item_key, func.count(ItemGrant.id)).group_by(ItemGrant.item_key)
            )
        ).all()
    )
    policies = await item_policies(db)
    return {
        "items": [
            {
                "key": f"{kind}:{key}",
                "kind": kind,
                "label": meta["label"],
                "default_price_xp": meta["price_xp"],
                "price_xp": policies[f"{kind}:{key}"]["price_xp"],
                "sale": policies[f"{kind}:{key}"]["sale"],
                "grants": counts.get(f"{kind}:{key}", 0),
            }
            for kind, catalog in (("mascot", MASCOTS), ("outfit", OUTFITS))
            for key, meta in catalog.items()
        ]
    }


class ItemPatch(BaseModel):
    # price_xp: null = 카탈로그 기본가 복귀 / sale: "event" = XP 구매 차단(지급 전용)
    price_xp: int | None = Field(default=None, ge=1, le=1_000_000)
    sale: Literal["xp", "event"] | None = None


@router.patch("/{item_key}")
async def set_item_policy(
    item_key: str, body: ItemPatch, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    """판매 정책 변경 — 보낸 필드만 갱신 (가격·판매 방식 독립 설정)."""
    _known_or_raise(item_key)
    setting = await db.get(ItemSetting, item_key)
    if setting is None:
        setting = ItemSetting(item_key=item_key)
        db.add(setting)
    if "price_xp" in body.model_fields_set:
        setting.price_xp = body.price_xp
    if body.sale is not None:
        setting.sale = body.sale
    await db.commit()
    policy = (await item_policies(db))[item_key]
    return {"key": item_key, "price_xp": policy["price_xp"], "sale": policy["sale"]}


def _grant_dict(grant: ItemGrant, email: str, nickname: str) -> dict:
    return {
        "id": grant.id,
        "email": email,
        "nickname": nickname,
        "note": grant.note,
        "created_at": grant.created_at,
    }


@router.get("/{item_key}/grants")
async def list_grants(item_key: str, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    _known_or_raise(item_key)
    rows = (
        await db.execute(
            select(ItemGrant, User.email, User.nickname)
            .join(User, User.id == ItemGrant.user_id)
            .where(ItemGrant.item_key == item_key)
            .order_by(ItemGrant.id.desc())
        )
    ).all()
    return {"items": [_grant_dict(grant, email, nickname) for grant, email, nickname in rows]}


class GrantCreate(BaseModel):
    email: str
    note: str | None = None


@router.post("/{item_key}/grants")
async def create_grant(
    item_key: str,
    body: GrantCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """이벤트 지급 — 구매가 아니므로 purchases 이력에는 남기지 않는다 (지갑 무변동)."""
    _known_or_raise(item_key)
    user = (
        await db.execute(select(User).where(func.lower(User.email) == body.email.strip().lower()))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
    duplicate = (
        await db.execute(
            select(ItemGrant.id).where(ItemGrant.user_id == user.id, ItemGrant.item_key == item_key)
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_granted")

    grant = ItemGrant(user_id=user.id, item_key=item_key, note=body.note or "이벤트 지급")
    db.add(grant)
    await db.flush()
    # 벨 알림 — "'브리키' 캐릭터를 받았어요" (payload 는 지급 시점 스냅샷)
    await notify(db, user.id, "item_granted", {"item_key": item_key, "note": body.note})
    await db.commit()
    await db.refresh(grant)
    return _grant_dict(grant, user.email, user.nickname)


@router.delete("/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_grant(grant_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    """회수 — 다음 카탈로그 조회부터 미보유. 활성 마스코트였다면 렌더러가 자연 소멸."""
    grant = await db.get(ItemGrant, grant_id)
    if grant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "grant_not_found")
    await db.delete(grant)
    await db.commit()
