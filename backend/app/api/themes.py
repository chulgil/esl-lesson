"""사용자 테마 카탈로그 API (docs/specs/theme-mall.md)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import ThemeRewardRule, User
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
    titles = {d[0]: d[1] for d in DEFINITIONS}
    rules = (await db.execute(select(ThemeRewardRule))).scalars().all()
    unlock_by_theme = {r.theme_key: titles.get(r.achievement_key) for r in rules}

    return {
        "items": [
            {
                "key": key,
                "access": access,
                "allowed": key in allowed,
                "unlock": unlock_by_theme.get(key),
            }
            for key, access in access_map.items()
        ]
    }
